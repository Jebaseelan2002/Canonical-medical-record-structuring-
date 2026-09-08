import os

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "canonical_medical_fhir"
    hapi_fhir_url: str = "http://localhost:8080/fhir"
    upload_dir: str = os.getenv("UPLOAD_DIR", "/tmp/uploads" if os.getenv("VERCEL") else "uploads")
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    rag_top_k: int = 5
    llm_timeout_seconds: float = 45
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
