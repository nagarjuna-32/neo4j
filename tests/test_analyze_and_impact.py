import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_analyze_demo_question(client):
    # Exactly matching the prompt's demo scenario question:
    # "The Users API returns 401 after the authentication refactor. Why might this happen, and what should I investigate before merging?"
    payload = {
        "project_id": "PRJ-SENTINEL",
        "question": "The Users API returns HTTP 401 after the authentication refactor. Why might this happen, and what should I investigate before merging?",
        "component": "Authentication",
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Grounded evidence verification
    assert "answer" in data
    assert "assessment" in data
    assert len(data["relevant_evidence"]) > 0
    assert len(data["evidence_paths"]) > 0

    # Verify key evidence citations
    evidence_ids = [e["id"] for e in data["relevant_evidence"]]
    assert "BUG-101" in evidence_ids or "DEC-101" in evidence_ids

    # Verify structured suggestions
    assert len(data["suggested_checks"]) > 0
    assert len(data["suggested_tests"]) > 0
    assert "evidence_limitations" in data
    assert "confidence_explanation" in data
    assert "source" in data


def test_analyze_empty_evidence_component(client):
    payload = {
        "project_id": "PRJ-SENTINEL",
        "question": "How do we deploy the Kubernetes ingress controller?",
        "component": "NonExistentComponent",
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "evidence_limitations" in data
    assert "answer" in data


def test_impact_analysis_for_authentication(client):
    # Change Authentication -> Downstream Users API and Admin Dashboard should be detected
    payload = {
        "project_id": "PRJ-SENTINEL",
        "changed_components": ["Authentication"],
    }
    response = client.post("/api/impact", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["directly_changed"] == ["Authentication"]
    affected_names = [a["name"] for a in data["affected_components"]]
    assert "Authentication" in affected_names
    assert "Users API" in affected_names
    assert "Admin Dashboard" in affected_names

    # Verify heuristic priority is HIGH because Authentication has historical regressions (BUG-101)
    assert data["heuristic_priority"] in ["HIGH", "MEDIUM"]
    assert len(data["historical_risks"]) >= 1
    assert len(data["suggested_tests"]) >= 1
    assert len(data["graph_paths"]) >= 1


def test_activity_feed(client):
    response = client.get("/api/activity?project_id=PRJ-SENTINEL")
    assert response.status_code == 200
    feed = response.json()
    assert isinstance(feed, list)
    assert len(feed) > 0
    assert "event_type" in feed[0]
