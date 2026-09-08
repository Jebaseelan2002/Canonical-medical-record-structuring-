from datetime import datetime, timezone

def make_provenance(filename, pages):
    return {"source_file": filename, "created_at": datetime.now(timezone.utc).isoformat(), "pages": pages, "pipeline": ["PDF extraction", "OCR fallback", "page classification", "medical extraction", "normalization", "FHIR generation", "HAPI validation"]}
