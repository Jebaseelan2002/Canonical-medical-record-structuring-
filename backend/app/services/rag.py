import hashlib
import json
import math
import re

import httpx

from ..config import settings
from ..database import get_records_by_ids, list_record_vectors, save_record_vector

_VECTOR_SIZE = 256
_LLM_MAX_MATCHES = 1
_MIN_LEXICAL_SCORE = 0.05
_STOP_WORDS = {
    "a", "about", "an", "and", "are", "can", "does", "for", "how", "i",
    "is", "me", "of", "on", "please", "show", "tell", "the", "to", "what",
    "which", "who", "with",
}


def _record_text(record: dict) -> str:
    raw_record = {
        "filename": record.get("filename"),
        "pages": record.get("pages"),
        "page_types": record.get("page_types"),
        "full_text": record.get("full_text"),
        "patient": record.get("patient"),
        "data": record.get("data"),
        "fhir": record.get("fhir"),
        "validation": record.get("validation"),
        "provenance": record.get("provenance"),
    }
    return json.dumps(raw_record, default=str, ensure_ascii=True)


def _local_embedding(text: str) -> list[float]:
    vector = [0.0] * _VECTOR_SIZE
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % _VECTOR_SIZE
        vector[index] += 1.0 if digest[4] % 2 else -1.0
    magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / magnitude for value in vector]


def _gemini_embedding(text: str) -> list[float] | None:
    if not settings.llm_api_key:
        return None
    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.embedding_model}:embedContent",
        params={"key": settings.llm_api_key},
        json={"model": f"models/{settings.embedding_model}", "content": {"parts": [{"text": text}]}},
        timeout=settings.llm_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()["embedding"]["values"]


def _openai_embedding(text: str) -> list[float] | None:
    if not settings.llm_api_key:
        return None
    response = httpx.post(
        f"{settings.llm_base_url.rstrip('/')}/embeddings",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={"model": settings.embedding_model, "input": text},
        timeout=settings.llm_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def embed(text: str) -> list[float]:
    try:
        if "generativelanguage.googleapis.com" in settings.llm_base_url:
            return _gemini_embedding(text) or _local_embedding(text)
        return _openai_embedding(text) or _local_embedding(text)
    except (httpx.HTTPError, KeyError, IndexError):
        return _local_embedding(text)


def index_record(record_id: str, record: dict) -> str:
    text = str(record.get("raw_pdf_text") or record.get("full_text") or "").strip()
    save_record_vector(record_id, text, embed(text))
    return "mongodb"


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _search_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _STOP_WORDS and len(token) > 1
    }


def _lexical_score(query_tokens: set[str], document_tokens: set[str], document_frequency: dict[str, int], document_count: int) -> float:
    if not query_tokens or not document_tokens:
        return 0.0
    score = 0.0
    for token in query_tokens & document_tokens:
        inverse_frequency = math.log((document_count + 1) / (document_frequency.get(token, 0) + 1)) + 1
        score += inverse_frequency
    return score / sum(math.log((document_count + 1) / (document_frequency.get(token, 0) + 1)) + 1 for token in query_tokens)


def retrieve(question: str, top_k: int | None = None, record_id: str | None = None) -> list[dict]:
    question_vector = embed(question)
    items = list_record_vectors()
    if record_id:
        items = [item for item in items if item.get("record_id") == record_id]
    query_tokens = _search_tokens(question)
    document_tokens = [_search_tokens(item.get("text", "")) for item in items]
    document_frequency = {
        token: sum(token in tokens for tokens in document_tokens)
        for token in query_tokens
    }
    ranked = []
    for item, tokens in zip(items, document_tokens):
        semantic_score = _cosine(question_vector, item.get("embedding", []))
        lexical_score = _lexical_score(query_tokens, tokens, document_frequency, len(items))
        if query_tokens and lexical_score < _MIN_LEXICAL_SCORE:
            continue
        ranked.append({
            "record_id": item["record_id"],
            "text": item.get("text", ""),
            "score": lexical_score + max(semantic_score, 0.0) * 0.15,
        })
    ranked.sort(key=lambda item: item["score"], reverse=True)
    selected = ranked[: top_k if top_k is not None else settings.rag_top_k]
    records = {str(record["_id"]): record for record in get_records_by_ids([item["record_id"] for item in selected])}
    unique_records = {}
    for item in selected:
        record = records.get(item["record_id"])
        if record is None:
            continue
        current = unique_records.get(item["record_id"])
        if current is None or item["score"] > current["score"]:
            unique_records[item["record_id"]] = {**item, "record": record}
    return sorted(unique_records.values(), key=lambda item: item["score"], reverse=True)


def _fallback_answer(question: str, matches: list[dict]) -> str:
    if not matches:
        return "I could not find a stored medical record relevant to that question."
    best = matches[0]["record"]
    patient = best.get("patient", {})
    data = best.get("data", {})
    def value(item: object, *keys: str) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return next((str(item[key]) for key in keys if item.get(key)), "")
        return str(item)

    def items(field: object) -> list[object]:
        if isinstance(field, list):
            return field
        return [field] if field else []

    def unique_values(field: object, *keys: str) -> list[str]:
        values = []
        seen = set()
        for item in items(field):
            text = value(item, *keys).strip()
            normalized = text.casefold()
            if text and normalized not in seen:
                values.append(text)
                seen.add(normalized)
        return values

    conditions = ", ".join(unique_values(data.get("conditions"), "display", "code")) or "none recorded"
    medications = ", ".join(unique_values(data.get("medications"), "name", "display", "code")) or "none recorded"
    observation_items = [item for item in items(data.get("observations")) if isinstance(item, dict)]
    question_text = question.lower()
    condition_values = unique_values(data.get("conditions"), "display", "code")
    medication_values = unique_values(data.get("medications"), "name", "display", "code")
    patient_name = str(patient.get("name") or "").strip()
    question_tokens = _search_tokens(question)
    patient_tokens = _search_tokens(patient_name)
    observation_terms = ("observation", "vital", "heart rate", "blood pressure", "temperature", "oxygen", "saturation", "weight", "height")
    asks_about_observation = any(term in question_text for term in observation_terms)
    asks_about_medication = any(term in question_text for term in ("medication", "medicine", "drug", "prescription", "prescribed", "taking"))
    asks_about_condition = any(term in question_text for term in ("condition", "diagnosis", "disease")) or any(value.lower() in question_text for value in condition_values)
    asks_about_patient = any(term in question_text for term in ("patient", "name", "who")) or bool(patient_tokens & question_tokens)

    if asks_about_observation:
        specific_observations = [
            item for item in observation_items
            if item.get("name", "").lower() in question_text
        ]
        selected_observations = specific_observations or observation_items
        formatted = []
        seen = set()
        for item in selected_observations:
            name = str(item.get("name") or "Unknown")
            value_text = str(item.get("value") or "")
            if value_text.endswith(".0"):
                value_text = value_text[:-2]
            unit = str(item.get("unit") or "")
            entry = f"{name}: {value_text} {unit}".strip()
            if entry.casefold() not in seen:
                formatted.append(entry)
                seen.add(entry.casefold())
        return f"Observations: {', '.join(formatted) or 'none recorded'}."
    if asks_about_medication or any(value.lower() in question_text for value in medication_values):
        return f"Medications: {medications}."
    if asks_about_condition:
        return f"Conditions: {conditions}."
    if asks_about_patient:
        return f"Patient: {(patient_name or 'not recorded').rstrip('.')}."

    full_text = str(best.get("full_text") or best.get("content") or "").strip()
    if full_text:
        segments = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+|\n+", full_text) if segment.strip()]
        scored_segments = []
        for segment in segments:
            segment_tokens = _search_tokens(segment)
            score = len(question_tokens & segment_tokens)
            segment_lower = segment.casefold()
            if asks_about_condition and any(term in segment_lower for term in ("pain", "diagnosis", "history", "condition", "disease", "symptom", "problem", "injury")):
                score += 8
            if asks_about_medication and any(term in segment_lower for term in ("medication", "medicine", "prescription", "drug", "take", "taking")):
                score += 6
            if asks_about_condition and any(item.casefold() in segment.casefold() for item in condition_values):
                score += 5
            if asks_about_medication and any(item.casefold() in segment.casefold() for item in medication_values):
                score += 5
            if asks_about_observation and any(term in segment.casefold() for term in observation_terms):
                score += 5
            if score > 0:
                scored_segments.append((score, segment))

        if scored_segments:
            best_segment = max(scored_segments, key=lambda item: item[0])[1]
            return best_segment.rstrip(". ") + "."

    return "I found a relevant stored medical record, but it does not contain a direct answer to that question."


def _context_excerpt(question: str, match: dict) -> str:
    record = match["record"]
    full_text = str(record.get("full_text") or "").strip()
    if not full_text:
        return ""
    question_tokens = _search_tokens(question)
    segments = [segment.strip() for segment in re.split(r"(?<=[.!?])\s+|\n+", full_text) if segment.strip()]
    ranked_segments = sorted(
        segments,
        key=lambda segment: len(question_tokens & _search_tokens(segment)),
        reverse=True,
    )
    selected = []
    total_length = 0
    for segment in ranked_segments:
        if not (question_tokens & _search_tokens(segment)) and selected:
            continue
        if total_length + len(segment) > 2500:
            continue
        selected.append(segment)
        total_length += len(segment)
        if total_length >= 2000:
            break
    return "\n".join(selected) or full_text[:2500]


def _llm_answer(question: str, matches: list[dict]) -> str | None:
    if not settings.llm_api_key or not matches:
        return None
    context_parts = []
    for index, match in enumerate(matches[:_LLM_MAX_MATCHES]):
        excerpt = _context_excerpt(question, match)
        if excerpt:
            context_parts.append(f"Source {index + 1}: {excerpt}")
    context = "\n\n".join(context_parts)
    if not context:
        return None
    system_prompt = "Answer only the user's exact question using the supplied medical record context. Be concise and include only directly relevant facts. Do not summarize unrelated fields, add unsolicited advice, or invent clinical facts. If the context does not contain the answer, say so."
    if "generativelanguage.googleapis.com" in settings.llm_base_url:
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{settings.llm_model}:generateContent",
            params={"key": settings.llm_api_key},
            json={
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": f"Question: {question}\n\nMedical record context:\n{context}"}]}],
                "generationConfig": {"temperature": 0},
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    response = httpx.post(
        f"{settings.llm_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={
            "model": settings.llm_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Question: {question}\n\nMedical record context:\n{context}"},
            ],
        },
        timeout=settings.llm_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def answer_question(question: str, record_id: str | None = None) -> dict:
    matches = retrieve(question, record_id=record_id)
    llm_error = None
    try:
        answer = _llm_answer(question, matches)
    except (httpx.HTTPError, KeyError, IndexError) as error:
        answer = None
        llm_error = str(error)
    return {
        "answer": answer or _fallback_answer(question, matches),
        "sources": [
            {
                "record_id": item["record_id"],
                "pages": [page.get("page") for page in item["record"].get("page_types", [])],
            }
            for item in matches
        ],
        "retrieved": len(matches),
        "llm_used": bool(answer),
        "llm_error": llm_error,
    }