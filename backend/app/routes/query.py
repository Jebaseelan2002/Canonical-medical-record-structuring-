from fastapi import APIRouter, HTTPException, Query
from ..database import get_records_by_ids, list_records, get_record
from ..services.rag import answer_question

router = APIRouter(prefix="/api/query", tags=["query"])

@router.get("/records")
def records(
    limit: int = Query(50, ge=1, le=200),
    q: str | None = Query(None, description="Search patient data, file names, and embedded FHIR content"),
    record_id: str | None = Query(None, description="Restrict RAG search to one uploaded record")
):
    if q and q.strip():
        rag = answer_question(q.strip(), record_id=record_id)
        source_ids = [source["record_id"] for source in rag["sources"]]
        results = get_records_by_ids(source_ids)[:limit]
        return {"results": results, **rag}
    return {"results": list_records(limit, q), "answer": None, "sources": [], "retrieved": 0, "llm_used": False}

@router.get("/records/{record_id}")
def record(record_id: str):
    result = get_record(record_id)
    if not result: raise HTTPException(404, "Record not found")
    return result
