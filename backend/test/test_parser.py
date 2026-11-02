import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.fhir.parser import build_bp_report, find_overdue_patients


def observation(observation_id, patient_reference, observed_on, systolic, diastolic):
    return {
        "resourceType": "Observation",
        "id": observation_id,
        "status": "final",
        "effectiveDateTime": f"{observed_on}T12:00:00Z",
        "subject": {"reference": patient_reference},
        "code": {"coding": [{"code": "85354-9"}]},
        "component": [
            {
                "code": {"coding": [{"code": "8480-6"}]},
                "valueQuantity": {"value": systolic},
            },
            {
                "code": {"coding": [{"code": "8462-4"}]},
                "valueQuantity": {"value": diastolic},
            },
        ],
    }


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.fhir_dir = Path(self.temp_dir.name)
        self.patient_id = "patient-1"
        self.bundle_path = self.fhir_dir / "bundle.json"
        self.write_bundle([
            {
                "resourceType": "Patient",
                "id": self.patient_id,
                "name": [{"given": ["Alex"], "family": "Example"}],
            },
            observation(
                "older", f"urn:uuid:{self.patient_id}", "2020-01-01", 120, 80
            ),
            observation(
                "latest", f"urn:uuid:{self.patient_id}", "2022-01-01", 130, 85
            ),
        ])

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_bundle(self, resources):
        self.bundle_path.write_text(json.dumps({
            "resourceType": "Bundle",
            "entry": [{"resource": resource} for resource in resources],
        }))

    def test_builds_report_from_latest_component_reading(self):
        self.assertEqual(
            build_bp_report(self.fhir_dir, today=date(2023, 1, 1)),
            [{
                "patient_id": self.patient_id,
                "name": "Alex Example",
                "last_bp_date": "2022-01-01",
                "systolic": 130,
                "diastolic": 85,
            }],
        )

    def test_finds_overdue_patients_from_urn_uuid_references(self):
        overdue = find_overdue_patients(
            self.fhir_dir, today=date(2023, 1, 2)
        )
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0]["patient_id"], self.patient_id)
        self.assertEqual(overdue[0]["status"], "Overdue")
        self.assertEqual(overdue[0]["last_bp_date"], "2022-01-01")

    def test_does_not_mark_reading_on_cutoff_as_overdue(self):
        self.write_bundle([
            {"resourceType": "Patient", "id": self.patient_id},
            observation(
                "cutoff",
                f"Patient/{self.patient_id}",
                "2022-01-01",
                120,
                80,
            ),
        ])
        self.assertEqual(
            find_overdue_patients(self.fhir_dir, today=date(2022, 12, 31)),
            [],
        )

    def test_reports_patient_without_recorded_bp(self):
        self.write_bundle([
            {"resourceType": "Patient", "id": self.patient_id},
        ])
        overdue = find_overdue_patients(
            self.fhir_dir, today=date(2023, 1, 1)
        )
        self.assertEqual(overdue[0]["status"], "No recorded blood pressure")
        self.assertIsNone(overdue[0]["last_bp_date"])

    def test_invalid_json_identifies_file_in_error(self):
        self.bundle_path.write_text("{")
        with self.assertRaisesRegex(ValueError, "bundle.json"):
            find_overdue_patients(self.fhir_dir, today=date(2023, 1, 1))


if __name__ == "__main__":
    unittest.main()
