from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_repository():
    response = client.get("/api/repositories/does-not-exist")
    assert response.status_code == 404


def test_repository_history_shape():
    response = client.get("/api/repositories")
    assert response.status_code == 200
    body = response.json()
    assert "repositories" in body
    assert "limit" in body
    assert "offset" in body


def test_readiness_and_deployment_status():
    ready = client.get("/ready")
    assert ready.status_code in {200, 503}
    deployment = client.get("/deployment")
    assert deployment.status_code == 200
    assert "valid" in deployment.json()
