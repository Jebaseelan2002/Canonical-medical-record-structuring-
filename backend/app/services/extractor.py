import re
from collections import OrderedDict


def _normalize_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def first(patterns, text):
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return m.group(1).strip()
    return None


def _extract_named_value(text, label_aliases, stop_labels=None, max_length=120):
    aliases = "|".join(re.escape(alias) for alias in label_aliases)
    stop = "|".join(re.escape(label) for label in (stop_labels or [])) if stop_labels else ""
    patterns = [
        rf"(?is)\b(?:{aliases})\b\s*(?:[:\-]|\s)\s*([A-Z][A-Za-z0-9,.'()\-/\s]{{1,{max_length}}})",
        rf"(?is)\b(?:{aliases})\b\s*(?:[:\-]|\s)\s*([A-Z][A-Za-z0-9,.'()\-/\s]{{1,{max_length}}})(?=\s*(?:\b(?:{stop})\b|$))",
        rf"(?is)\b(?:{aliases})\b\s*\n\s*([A-Z][A-Za-z0-9,.'()\-/\s]{{1,{max_length}}})(?=\s*(?:\b(?:{stop})\b|$))",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            value = m.group(1).strip()
            if value and value.lower() not in {"patient", "name"}:
                cleaned = re.split(r"\s+(?:Date of Birth|DOB|MRN|Sex|Gender|Account|Encounter|Date of Service|Date of Surgery|Date of Procedure)\b", value, flags=re.I)[0].strip()
                if cleaned:
                    return _normalize_space(cleaned)
    return None


def _extract_dob(text):
    value = first([r"(?i)\b(?:date of birth|dob)\b\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})", r"(?i)\b(?:birth date)\b\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})"], text)
    if value:
        try:
            from datetime import datetime
            dt = datetime.strptime(value, "%m/%d/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            try:
                from datetime import datetime
                dt = datetime.strptime(value, "%m-%d-%Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                return value
    return None


def _extract_mrn(text):
    return first([r"(?i)\b(?:mrn|medical record(?: number)?|medical record #)\b\s*[:#\-]?\s*([A-Za-z0-9-]+)", r"(?i)\b(?:account\s*/\s*encounter|encounter)\b\s*[:\-]?\s*([A-Za-z0-9-]+)"], text)


def _extract_gender(text):
    gender = first([r"(?i)\b(?:gender|sex)\b\s*[:\-]?\s*(male|female|other|unknown)"], text)
    if gender:
        return gender.title()
    return None


def _extract_observations(pages):
    observations = []
    for p in pages:
        page_text = p["text"]
        for label, value_pattern, unit_pattern in [
            ("Heart rate", r"(?i)\b(?:heart rate|hr)\b\s*[:=]?\s*(\d{2,3})\s*(?:bpm|/min)?", "bpm"),
            ("Blood pressure", r"(?i)\b(?:blood pressure|bp)\b\s*[:=]?\s*(\d{2,3}/\d{2,3})", "mmHg"),
            ("Temperature", r"(?i)\b(?:temperature|temp)\b\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)\s*(?:°f|f|c|°c)?", "°F"),
            ("Oxygen saturation", r"(?i)\b(?:spo2|oxygen saturation|o2 sat)\b\s*[:=]?\s*(\d{2,3})\s*%", "%"),
            ("Weight", r"(?i)\b(?:weight)\b\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)\s*(lb|lbs|kg)", "unit"),
            ("Height", r"(?i)\b(?:height)\b\s*[:=]?\s*(\d{1,2}(?:\.\d+)?)\s*(in|ft|cm)", "unit"),
        ]:
            for m in re.finditer(value_pattern, page_text):
                value = m.group(1)
                if label == "Weight" or label == "Height":
                    unit = m.group(2).lower()
                    value_float = float(value)
                elif label == "Blood pressure":
                    unit = "mmHg"
                    value_float = float(value.split('/')[0])
                elif label == "Temperature":
                    unit = "°F"
                    value_float = float(value)
                else:
                    unit = unit_pattern
                    value_float = float(value)
                observations.append({"name": label, "value": value_float, "unit": unit, "page": p["page"]})
    deduped = []
    seen = set()
    for obs in observations:
        key = (obs["name"], obs["page"], obs["value"], obs["unit"])
        if key not in seen:
            deduped.append(obs)
            seen.add(key)
    return deduped


def _extract_conditions(full_text):
    condition_map = OrderedDict([
        ("Lumbar radiculopathy", [r"\b(?:left|right)?\s*l[45]\s*radiculopathy\b", r"\blumbar radiculopathy\b"]),
        ("Herniated disc", [r"\bherniated\s+nucleus\s+pulposus\b", r"\bdisc\s+protrusion\b", r"\bdisc\s+herniation\b", r"\bHNP\b"]),
        ("Mechanical low back pain", [r"\bmechanical\s+low\s+back\s+pain\b", r"\blow\s+back\s+pain\b"]),
        ("Sciatica", [r"\bsciatica\b"]),
        ("Cervical strain", [r"\bcervical\s+strain\b", r"\bneck\s+strain\b"]),
        ("Lumbar strain", [r"\blumbar\s+strain\b"]),
    ])
    conditions = []
    for name, patterns in condition_map.items():
        if any(re.search(pattern, full_text, re.I) for pattern in patterns):
            conditions.append(name)
    return conditions


def _extract_medications(full_text):
    medications = []
    noise_words = {"with", "loss", "pain", "plan", "study", "same", "right", "left", "patient", "date", "note", "provider", "level", "history", "assessment", "follow", "visit", "record", "surgery", "procedure", "status", "off", "work"}
    patterns = [
        r"(?i)\b([A-Z][A-Za-z0-9./-]{2,35})\s+(\d{1,3}(?:-\d{1,3})?(?:\.\d+)?)\s*(mg|mcg|g|ml)\b",
        r"(?i)\b([A-Z][A-Za-z0-9./-]{2,35})\s+(\d{1,3}(?:\.\d+)?)\s*(?:tab|tabs|caps|cap|tablet|ml|mg|mcg|g)\b",
    ]
    for pattern in patterns:
        for m in re.finditer(pattern, full_text):
            name = m.group(1).strip()
            if not name or name.lower() in noise_words:
                continue
            dose_text = m.group(2).strip()
            unit = (m.group(3) or "").strip().lower() if len(m.groups()) >= 3 else ""
            numeric_match = re.search(r"(\d+(?:\.\d+)?)", dose_text)
            if not numeric_match:
                continue
            dose_value = float(numeric_match.group(1))
            if unit:
                medications.append({"name": name.title(), "dose": dose_value, "unit": unit})
            else:
                medications.append({"name": name.title(), "dose": dose_value, "unit": "unknown"})
    deduped = []
    seen = set()
    for med in medications:
        key = (med["name"].lower(), med["dose"], med["unit"])
        if key not in seen:
            deduped.append(med)
            seen.add(key)
    return deduped


def extract(pages):
    full = "\n".join(p["text"] for p in pages)
    compact = _normalize_space(full)

    patient_name = _extract_named_value(compact, ["Patient Name", "Patient", "Name"], stop_labels=["Date of Birth", "DOB", "MRN", "Sex", "Gender", "Date of Service", "MRN"]) or "Unknown"
    patient = {
        "name": patient_name,
        "birthDate": _extract_dob(compact),
        "mrn": _extract_mrn(compact),
        "gender": _extract_gender(compact),
    }

    observations = _extract_observations(pages)
    conditions = _extract_conditions(compact)
    medications = _extract_medications(compact)

    return {"patient": patient, "observations": observations, "conditions": conditions, "medications": medications}
