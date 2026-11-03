import json
from datetime import date, datetime, timedelta
from pathlib import Path

FHIR_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "fhir"

OVERDUE_DAYS = 365
BP_PANEL_CODE = "85354-9"
SYSTOLIC_CODE = "8480-6"
DIASTOLIC_CODE = "8462-4"


def get_resource_date(resource):
    value = resource.get("effectiveDateTime") or resource.get("issued")
    if not isinstance(value, str) or not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def is_blood_pressure(resource):
    codes = [
        coding.get("code")
        for coding in resource.get("code", {}).get("coding", [])
    ]
    return BP_PANEL_CODE in codes


def _patient_id_from_reference(reference):
    if not isinstance(reference, str):
        return None
    if reference.startswith("urn:uuid:"):
        return reference.removeprefix("urn:uuid:")

    parts = reference.rstrip("/").split("/")
    if len(parts) >= 2 and parts[-2] == "Patient":
        return parts[-1]
    return None


def _patient_name(patient):
    names = patient.get("name", [])
    if not names or not isinstance(names[0], dict):
        return None

    name = names[0]
    given = name.get("given", [])
    family = name.get("family", "")
    parts = (given if isinstance(given, list) else []) + [family]
    return " ".join(part for part in parts if isinstance(part, str)).strip() or None


def _blood_pressure_values(resource):
    values = {}
    for component in resource.get("component", []):
        component_codes = [
            coding.get("code")
            for coding in component.get("code", {}).get("coding", [])
        ]
        quantity = component.get("valueQuantity", {})
        value = quantity.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue

        if SYSTOLIC_CODE in component_codes:
            values["systolic"] = value
        elif DIASTOLIC_CODE in component_codes:
            values["diastolic"] = value
    return values


def _collect_fhir_data(fhir_dir, today):
    patients = {}
    latest_bp = {}

    for path in Path(fhir_dir).glob("*.json"):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Unable to read FHIR JSON file: {path}") from exc

        if data.get("resourceType") == "Bundle":
            resources = [
                entry.get("resource", {})
                for entry in data.get("entry", [])
                if isinstance(entry, dict)
            ]
        elif data.get("resourceType"):
            resources = [data]
        else:
            continue

        for resource in resources:
            resource_type = resource.get("resourceType")
            resource_id = resource.get("id")

            if resource_type == "Patient" and resource_id:
                patients[resource_id] = resource

            if (
                resource_type != "Observation"
                or resource.get("status") != "final"
                or not is_blood_pressure(resource)
            ):
                continue

            patient_id = _patient_id_from_reference(
                resource.get("subject", {}).get("reference")
            )
            measured_on = get_resource_date(resource)
            if not patient_id or not measured_on or measured_on > today:
                continue

            if (
                patient_id not in latest_bp
                or measured_on > latest_bp[patient_id]["date"]
            ):
                latest_bp[patient_id] = {
                    "date": measured_on,
                    "observation_id": resource_id,
                    **_blood_pressure_values(resource),
                }

    return patients, latest_bp


def build_bp_report(fhir_dir=FHIR_DIR, today=None):
    today = today or date.today()
    patients, latest_bp = _collect_fhir_data(fhir_dir, today)
    report = []

    for patient_id, latest in latest_bp.items():
        if patient_id not in patients:
            continue

        patient = patients[patient_id]
        report.append({
            "patient_id": patient_id,
            "name": _patient_name(patient) or f"Patient {patient_id}",
            "last_bp_date": latest["date"].isoformat(),
            "systolic": latest.get("systolic"),
            "diastolic": latest.get("diastolic"),
        })

    return report


def find_overdue_patients(fhir_dir=FHIR_DIR, today=None):
    today = today or date.today()
    cutoff = today - timedelta(days=OVERDUE_DAYS)
    patients, latest_bp = _collect_fhir_data(fhir_dir, today)
    overdue = []

    for patient_id, patient in patients.items():
        latest = latest_bp.get(patient_id)

        if latest is None:
            status = "No recorded blood pressure"
            last_reading = None
        elif latest["date"] < cutoff:
            status = "Overdue"
            last_reading = latest["date"].isoformat()
        else:
            continue

        overdue.append({
            "patient_id": patient_id,
            "name": _patient_name(patient) or f"Patient {patient_id}",
            "last_bp_date": last_reading,
            "status": status,
        })

    return overdue


if __name__ == "__main__":
    for reading in build_bp_report():
        print(reading)

    for patient in find_overdue_patients():
        print(patient)
