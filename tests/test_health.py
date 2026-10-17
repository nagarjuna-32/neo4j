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
