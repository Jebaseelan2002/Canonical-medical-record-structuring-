from app.services.pdf_processor import process_pdf
from app.services.extractor import extract
from app.services.rag import _record_text, _fallback_answer


def test_extracts_patient_and_clinical_details_from_sample_pdf():
    pages = process_pdf(r"uploads\0f3f0139-d517-49a4-8754-b78ae784555d_Synthetic_Medical_Record_Exercise_Whitfield 1.pdf")
    data = extract(pages)

    assert data["patient"]["name"] == "Whitfield, Marcus D."
    assert data["patient"]["mrn"] == "PCG-4471902"
    assert data["patient"]["birthDate"] == "1987-03-14"
    assert "Mechanical low back pain" in data["conditions"]
    assert any(item["name"] == "Naproxen" for item in data["medications"])
    assert any(item["name"] == "Methocarbamol" for item in data["medications"])


def test_record_text_keeps_raw_pages_and_validation_details():
    record = {
        "filename": "sample.pdf",
        "pages": [{"page": 1, "text": "BP 120/80", "source": "text"}],
        "patient": {"name": "Jane Doe"},
        "data": {"conditions": ["Hypertension"]},
        "fhir": [{"resourceType": "Patient", "id": "p-1"}],
        "validation": {"results": [{"resourceType": "Patient", "valid": True}]},
    }

    text = _record_text(record)

    assert "BP 120/80" in text
    assert "Hypertension" in text
    assert "Patient" in text
    assert "valid" in text
    assert "full_text" in text or "BP 120/80" in text


def test_fallback_answer_uses_full_pdf_text_instead_of_patient_name():
    record = {
        "patient": {"name": "Jane Doe"},
        "full_text": "History: Mechanical low back pain. Patient is on Naproxen. Follow-up note: blood pressure 120/80.",
    }

    answer = _fallback_answer("What condition does the patient have?", [{"record": record}])

    assert "Mechanical low back pain" in answer
    assert "Jane Doe" not in answer
