"""
CodeBrain AI — Phase 5 Change Impact Analysis Test Suite
Tests:
- Direct changes and downstream dependency traversal
- Historical bugs and technical decision retrieval
- File path resolution to components
- Graceful handling of unknown components without crashing
- Isolated components yielding LOW heuristic priority
- Empty payload validation (HTTP 400)
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_impact_direct_changes(client):
    payload = {
        "project_id": "PRJ-SENTINEL",
        "changed_components": ["Authentication"],
    }
    res = client.post("/api/impact", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["directly_changed"] == ["Authentication"]
    direct_comps = [c for c in data["affected_components"] if c["tier"] == "direct"]
    assert len(direct_comps) == 1
    assert direct_comps[0]["name"] == "Authentication"
    assert direct_comps[0]["status_label"] == "potential_impact"


def test_impact_downstream_dependencies(client):
    payload = {
        "project_id": "PRJ-SENTINEL",
        "changed_components": ["Authentication"],
    }
    res = client.post("/api/impact", json=payload)
    assert res.status_code == 200
    data = res.json()

    affected_names = [c["name"] for c in data["affected_components"]]
    assert "Authentication" in affected_names
    assert "Users API" in affected_names
    assert "Admin Dashboard" in affected_names

    # Check propagation paths
    assert len(data["graph_paths"]) >= 2
    users_api_item = next(c for c in data["affected_components"] if c["name"] == "Users API")
    assert "downstream" in users_api_item["tier"]
    assert "DEPENDS_ON" in users_api_item["reason"]


def test_impact_historical_bugs_and_decisions(client):
    payload = {
        "project_id": "PRJ-SENTINEL",
        "changed_components": ["Authentication"],
    }
    res = client.post("/api/impact", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Historical bugs on affected components
    bug_ids = [b["bug_id"] for b in data["historical_risks"]]
    assert "BUG-101" in bug_ids

    # Technical decisions on affected components
    decision_ids = [d["decision_id"] for d in data["technical_decisions"]]
    assert "DEC-101" in decision_ids

    # Suggested tests
    test_ids = [t["test_id"] for t in data["suggested_tests"]]
    assert "TEST-101" in test_ids

    # High heuristic priority due to historical regression BUG-101
    assert data["heuristic_priority"] in ["HIGH", "MEDIUM"]


def test_impact_file_path_resolution(client):
    payload = {
        "project_id": "PRJ-SENTINEL",
        "changed_components": [],
        "changed_files": ["backend/app/middleware/auth.py"],
    }
    res = client.post("/api/impact", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Should resolve file to Authentication component
    assert "Authentication" in data["directly_changed"]
    affected_names = [c["name"] for c in data["affected_components"]]
    assert "Users API" in affected_names


def test_impact_unknown_component_handled_gracefully(client):
    payload = {
        "project_id": "PRJ-SENTINEL",
        "changed_components": ["NonExistentMicroservice123"],
    }
    res = client.post("/api/impact", json=payload)
    # Must NOT crash or return 500
    assert res.status_code == 200
    data = res.json()

    assert "NonExistentMicroservice123" in data["unresolved_inputs"]
    unresolved_items = [c for c in data["affected_components"] if c["tier"] == "unresolved"]
    assert len(unresolved_items) == 1
    assert unresolved_items[0]["name"] == "NonExistentMicroservice123"
    assert "not cataloged" in unresolved_items[0]["reason"]
    assert data["heuristic_priority"] == "LOW"


def test_impact_empty_inputs_returns_400(client):
    payload = {
        "project_id": "PRJ-SENTINEL",
        "changed_components": [],
        "changed_files": [],
    }
    res = client.post("/api/impact", json=payload)
    assert res.status_code == 400
    assert "At least one changed component or changed file" in res.json()["detail"]


def test_impact_isolated_component_low_priority(client):
    # Notification Service is a consumer, but no other service depends on it
    payload = {
        "project_id": "PRJ-SENTINEL",
        "changed_components": ["Notification Service"],
    }
    res = client.post("/api/impact", json=payload)
    assert res.status_code == 200
    data = res.json()

    # Should have zero downstream consumers
    downstream_items = [c for c in data["affected_components"] if "downstream" in c["tier"]]
    assert len(downstream_items) == 0
    assert data["heuristic_priority"] == "LOW"
