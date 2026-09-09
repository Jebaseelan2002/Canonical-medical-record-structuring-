import asyncio
import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
from datetime import datetime, timezone
import uuid
from bson import ObjectId
from ..config import settings
from ..database import delete_record, save_record
from ..services.rag import index_record
from ..services.pdf_processor import process_pdf
from ..services.classifier import classify
from ..services.extractor import extract
from ..services.normalizer import normalize
from ..services.fhir_builder import build_fhir
from ..services.fhir_validator import validate_resources
from ..services.provenance import make_provenance

router = APIRouter(prefix="/api/records", tags=["records"])

@router.post("/process")
async def process(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")
    upload_dir = Path(settings.upload_dir); upload_dir.mkdir(exist_ok=True)
    path = upload_dir / f"{uuid.uuid4()}_{Path(file.filename).name}"
    path.write_bytes(await file.read())
    pages = process_pdf(str(path))
    raw_pdf_text = "\n\n".join(
        f"Page {page['page']} ({page['source']}):\n{page['text']}" for page in pages
    )

    record_id = str(ObjectId())
    record, _ = await asyncio.to_thread(_build_record, record_id, file.filename, pages, raw_pdf_text)

    # Persist the complete structured pipeline result before creating its RAG vector.
    # This keeps MongoDB as the source of truth and prevents orphan vectors when
    # processing or storage fails partway through an upload.
    try:
        await asyncio.to_thread(save_record, record)
    except Exception as exc:
        raise HTTPException(503, "Unable to store the processed medical record in MongoDB") from exc

    try:
        vector_backend = await asyncio.to_thread(index_record, record_id, record)
    except Exception as exc:
        await asyncio.to_thread(delete_record, record_id)
        raise HTTPException(503, "Unable to index the raw PDF for RAG search") from exc

    return {
        "record_id": record_id,
        "patient": record["patient"],
        "resources": record["fhir"],
        "validation": record["validation"],
        "pages": len(pages),
        "stored": True,
        "storage_backend": "mongodb",
        "vector_backend": vector_backend,
    }


def _build_record(record_id: str, filename: str, pages: list[dict], raw_pdf_text: str) -> tuple[dict, str]:
    page_types = [
        {"page": page["page"], "type": classify(page["text"]), "source": page["source"]}
        for page in pages
    ]
    extracted = normalize(extract(pages))
    resources = build_fhir(extracted)
    validation = validate_resources(resources, settings.hapi_fhir_url)
    structured_text = "\n\n".join(
        [
            f"Patient: {json.dumps(extracted.get('patient', {}), default=str)}",
            f"Conditions: {json.dumps(extracted.get('conditions', []), default=str)}",
            f"Medications: {json.dumps(extracted.get('medications', []), default=str)}",
            f"Observations: {json.dumps(extracted.get('observations', []), default=str)}",
            f"FHIR: {json.dumps(resources, default=str)}",
            f"Validation: {json.dumps(validation, default=str)}",
        ]
    )
    record = {
        "_id": ObjectId(record_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "pages": [{"page": p["page"], "text": p["text"], "source": p["source"]} for p in pages],
        "page_types": page_types,
        "full_text": raw_pdf_text,
        "raw_pdf_text": raw_pdf_text,
        "structured_text": structured_text,
        "patient": extracted["patient"],
        "data": extracted,
        "fhir": resources,
        "validation": validation,
        "provenance": make_provenance(filename, len(pages)),
    }
    return record, "mongodb"
