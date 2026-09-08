from app.database import records_collection
from app.services.rag import index_record


def raw_text(record: dict) -> str:
    return "\n\n".join(
        f"Page {page.get('page')} ({page.get('source')}):\n{page.get('text', '')}"
        for page in record.get("pages", [])
    )


records = list(records_collection.find({}))
for record in records:
    text = raw_text(record)
    records_collection.update_one(
        {"_id": record["_id"]},
        {"$set": {"full_text": text, "raw_pdf_text": text}},
    )
    record["full_text"] = text
    record["raw_pdf_text"] = text
    index_record(str(record["_id"]), record)

print(f"migrated {len(records)} records")