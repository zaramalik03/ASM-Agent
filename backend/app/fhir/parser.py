import json
from pydoc import text
from pathlib import Path

FHIR_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "fhir"

def parse_resource(text):
    try:
        resource = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON") from exc

    if not isinstance(resource, dict) or not resource.get('resourceType'):
        raise ValueError("Expected resource object")

    return resource


def parse_bundle(text):
    try:
        bundle = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON") from exc

    if not isinstance(bundle, dict) or bundle.get('resourceType') != 'Bundle':
        raise ValueError("Expected Bundle resource")

    entries = bundle.get('entry', [])
    if not isinstance(entries, list):
        raise ValueError("Expected 'entry' to be a list")

    by_type_and_id = {}
    by_full_url = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get('resource')
        if not isinstance(resource, dict) or not resource.get('resourceType'):
            continue
        resource_type = resource['resourceType']
        resource_id = resource.get('id')

        if resource_id:
            by_type_and_id[(resource_type, resource_id)] = resource

        full_url = entry.get('fullUrl')
        if isinstance(full_url, str) and full_url:
            by_full_url[full_url] = resource

    return by_type_and_id, by_full_url


def iter_ndjson(lines):
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            resource = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'Invalid JSON on line {number}') from exc
        if not isinstance(resource, dict) or not resource.get('resourceType'):
            raise ValueError(f'Expected resource object on line {number}')
        yield resource


if __name__ == "__main__":
    resources_by_key, resources_by_full_url = parse_bundle(Path(FHIR_DIR).read_text)
    
    patient = resources_by_key.get(('Patient', 'example'))
    resource = resources_by_full_url.get('urn:uuid:example')
    print("Patient resource:", patient)
    print("Resource by full URL:", resource)
