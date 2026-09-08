from pydantic import BaseModel, Field
from typing import Any

class ProcessResponse(BaseModel):
    record_id: str
    patient: dict[str, Any]
    resources: list[dict[str, Any]]
    validation: dict[str, Any]
    pages: int
    stored: bool
    storage_backend: str
    vector_backend: str

class QueryResponse(BaseModel):
    results: list[dict[str, Any]]
