import re

ALIASES = {
    "hgb": "Hemoglobin",
    "hb": "Hemoglobin",
    "glucose": "Glucose",
    "wbc": "Leukocytes",
    "platelet": "Platelet Count",
    "heart rate": "Heart rate",
    "hr": "Heart rate",
    "bp": "Blood Pressure",
    "spo2": "Oxygen Saturation",
    "oxygen saturation": "Oxygen Saturation",
}
UNIT_ALIASES = {
    "bpm": "bpm",
    "/min": "bpm",
    "mmhg": "mmHg",
    "°f": "°F",
    "f": "°F",
    "%": "%",
}


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _canonical_name(value):
    cleaned = _clean_text(value)
    key = cleaned.casefold()
    return ALIASES.get(key, cleaned.title())


def _number(value):
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return value
    return int(parsed) if parsed.is_integer() else parsed


def _unique_texts(values):
    result = []
    seen = set()
    for value in values:
        cleaned = _clean_text(value)
        if cleaned and cleaned.casefold() not in seen:
            result.append(cleaned.title())
            seen.add(cleaned.casefold())
    return result


def normalize(data):
    patient = data.get("patient", {})
    if patient.get("name"):
        patient["name"] = _clean_text(patient["name"])
    if patient.get("gender"):
        patient["gender"] = _clean_text(patient["gender"]).title()

    data["conditions"] = _unique_texts(data.get("conditions", []))
    for obs in data.get("observations", []):
        obs["name"] = _canonical_name(obs.get("name"))
        obs["value"] = _number(obs.get("value"))
        unit = _clean_text(obs.get("unit")).casefold()
        obs["unit"] = UNIT_ALIASES.get(unit, _clean_text(obs.get("unit")))
        if obs.get("page") is not None:
            obs["page"] = _number(obs["page"])

    for medication in data.get("medications", []):
        medication["name"] = _canonical_name(medication.get("name"))
        medication["dose"] = _number(medication.get("dose"))
        medication["unit"] = _clean_text(medication.get("unit")).casefold()
    return data
