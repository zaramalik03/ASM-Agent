from fhir.resources.patient import Patient
from fhir.resources.humanname import HumanName
from fhir.resources.contactpoint import ContactPoint
import requests

base_url = "https://fhir-bootcamp.medblocks.com/fhir"


patient = Patient()
patient.name = [HumanName(family="Malik", given=["Zara"])]

patient.gender = "female"

patient.telecom = [
    ContactPoint(system="email", value="zmmalik418@gmail.com")
]

# print(patient.model_dump_json(indent=2))
patient_json = patient.model_dump()

# response = requests.post(base_url + "/Patient", json=patient_json)
response = requests.get(base_url + "/Patient/")

print(response.status_code)
print(response.content)

parsed_patient = Patient.model_validate_json(response.content)
print(parsed_patient.id)