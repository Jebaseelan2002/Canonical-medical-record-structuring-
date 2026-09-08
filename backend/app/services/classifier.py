KEYWORDS = {
    "lab_report": ["hemoglobin", "glucose", "wbc", "platelet", "laboratory", "reference range"],
    "medication": ["medication", "tablet", "capsule", "mg", "dose", "prescription"],
    "diagnosis": ["diagnosis", "assessment", "impression", "condition"],
    "discharge_summary": ["discharge summary", "hospital course", "discharge diagnosis"],
    "patient_demographics": ["date of birth", "dob", "patient name", "mrn", "medical record number"],
}


def classify(text: str) -> str:
    low = text.lower()
    scores = {k: sum(1 for word in words if word in low) for k, words in KEYWORDS.items()}
    return max(scores, key=scores.get) if max(scores.values(), default=0) else "unknown"
