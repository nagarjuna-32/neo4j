import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_memory_validation_empty_body(client):
    response = client.post("/api/memory", json={})
    assert response.status_code == 422  # Pydantic validation error


def test_memory_validation_invalid_type(client):
    response = client.post("/api/memory", json={
        "memory_type": "invalid_type",
        "title": "Invalid Title",
        "affected_component": "Authentication",
    })
    assert response.status_code == 422


def test_analyze_validation_short_question(client):
    response = client.post("/api/analyze", json={
        "question": "ab",  # min_length is 5
        "project_id": "PRJ-SENTINEL",
    })
    assert response.status_code == 422


def test_impact_validation_empty_components(client):
    response = client.post("/api/impact", json={
        "project_id": "PRJ-SENTINEL",
        "changed_components": [],
    })
    assert response.status_code == 400 or response.status_code == 422
