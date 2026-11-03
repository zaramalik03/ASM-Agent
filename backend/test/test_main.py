from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_returns_expected_body():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "synthetic-demo"}


def test_undefined_route_returns_404():
    response = client.get("/not-a-route")
    assert response.status_code == 404
