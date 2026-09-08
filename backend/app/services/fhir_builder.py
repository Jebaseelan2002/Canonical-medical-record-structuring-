from datetime import datetime, timezone
import uuid

LOINC = {"Hemoglobin": "718-7", "Glucose": "2345-7", "Leukocytes": "6690-2", "Platelet Count": "777-3"}
SNOMED = {"Diabetes Mellitus": "73211009", "Hypertension": "38341003", "Asthma": "195967001", "Pneumonia": "233604007", "Hyperlipidemia": "55822004"}


def build_fhir(data):
    patient = data["patient"]
    patient_id = str(uuid.uuid4())
    patient_resource = {"resourceType": "Patient", "id": patient_id, "identifier": ([{"system": "urn:mrn", "value": patient["mrn"]}] if patient.get("mrn") else []), "name": ([{"text": patient["name"]}] if patient.get("name") else [])}
    if patient.get("birthDate"): patient_resource["birthDate"] = patient["birthDate"].replace("/", "-")
    if patient.get("gender"): patient_resource["gender"] = patient["gender"].lower()
    resources = [patient_resource]
    for c in data["conditions"]:
        resources.append({"resourceType": "Condition", "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]}, "code": {"coding": [{"system": "http://snomed.info/sct", "code": SNOMED.get(c), "display": c}]}, "subject": {"reference": f"Patient/{patient_id}"}})
    for o in data["observations"]:
        resources.append({"resourceType": "Observation", "status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": LOINC.get(o["name"]), "display": o["name"]}]}, "valueQuantity": {"value": o["value"], "unit": o["unit"]}, "subject": {"reference": f"Patient/{patient_id}"}, "extension": [{"url": "urn:source-page", "valueInteger": o["page"]}]})
    for m in data["medications"]:
        if not m.get("name") or m.get("dose") is None:
            continue
        resources.append({"resourceType": "MedicationStatement", "status": "active", "medicationCodeableConcept": {"text": m["name"]}, "dosage": [{"text": f'{m["dose"]} {m["unit"]}'}], "subject": {"reference": f"Patient/{patient_id}"}})
    return resources
