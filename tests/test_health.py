import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["api_status"] == "healthy"
    assert "neo4j_status" in data
    assert "ai_status" in data
    assert "storage_backend" in data
    assert isinstance(data["diagnostics"], list)


def test_root_or_frontend(client):
    response = client.get("/")
    assert response.status_code == 200


def test_deployment_health_probes(client):
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["api_status"] == "healthy"

    res_healthz = client.get("/healthz")
    assert res_healthz.status_code == 200
    assert res_healthz.json()["api_status"] == "healthy"


def test_favicon_endpoint(client):
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert "image" in response.headers.get("content-type", "")

