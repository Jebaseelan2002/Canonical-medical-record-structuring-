from pymongo import MongoClient
from .config import settings

client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=2000)
db = client[settings.mongodb_db]
records_collection = db["records"]
vectors_collection = db["record_vectors"]


def ping_db():
    client.admin.command("ping")


def _record_matches_query(record: dict, query: str) -> bool:
    normalized = query.strip().lower()
    if not normalized:
        return True

    def collect(value):
        if isinstance(value, str):
            return [value.lower()]
        if isinstance(value, (int, float, bool)):
            return [str(value).lower()]
        if isinstance(value, dict):
            terms = []
            for child in value.values():
                terms.extend(collect(child))
            return terms
        if isinstance(value, list):
            terms = []
            for child in value:
                terms.extend(collect(child))
            return terms
        return []

    haystack = " ".join(collect(record))
    return normalized in haystack


def save_record(record: dict) -> str:
    result = records_collection.insert_one(record)
    return str(result.inserted_id)


def save_record_vector(record_id: str, text: str, embedding: list[float]) -> None:
    vectors_collection.update_one(
        {"record_id": record_id},
        {"$set": {"record_id": record_id, "text": text, "embedding": embedding}},
        upsert=True,
    )


def list_record_vectors():
    return list(vectors_collection.find({}, {"_id": 0, "record_id": 1, "text": 1, "embedding": 1}))


def get_records_by_ids(record_ids: list[str]) -> list[dict]:
    from bson import ObjectId

    object_ids = []
    for record_id in record_ids:
        try:
            object_ids.append(ObjectId(record_id))
        except Exception:
            continue
    docs_by_id = {}
    for doc in records_collection.find({"_id": {"$in": object_ids}}):
        doc["_id"] = str(doc["_id"])
        docs_by_id[doc["_id"]] = doc
    return [docs_by_id[record_id] for record_id in record_ids if record_id in docs_by_id]


def list_records(limit: int = 50, query: str | None = None):
    normalized_query = (query or "").strip()
    docs = list(records_collection.find({}).sort("created_at", -1).limit(limit if not normalized_query else 200))
    if normalized_query:
        docs = [doc for doc in docs if _record_matches_query(doc, normalized_query)][:limit]
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


def get_record(record_id: str):
    from bson import ObjectId
    doc = records_collection.find_one({"_id": ObjectId(record_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc
