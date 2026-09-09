from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.records import router as records_router
from .routes.query import router as query_router
from .database import ping_db

app = FastAPI(title="Canonical Medical FHIR API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://canonical-medical-record-structurin.vercel.app",
        "https://canonical-medical-record-structuring-bdp76xm6k-jebaseelan.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(records_router)
app.include_router(query_router)

@app.get("/api/health")
def health():
    try:
        ping_db(); mongo = "ok"
    except Exception as exc:
        mongo = f"error: {exc}"
    return {"status": "ok", "mongodb": mongo}
