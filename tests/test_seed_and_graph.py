import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_seed_idempotency(client):
    # Call seed twice to verify idempotency
    res1 = client.post("/api/seed")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] in ["success", "warning"]

    res2 = client.post("/api/seed")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] in ["success", "warning"]


def test_get_projects(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) >= 1
    p = next((proj for proj in projects if proj["id"] == "PRJ-SENTINEL"), None)
    assert p is not None
    assert p["name"] == "Sentinel Demo App"


def test_graph_structure(client):
    response = client.get("/api/graph?project_id=PRJ-SENTINEL")
    assert response.status_code == 200
    graph = response.json()
    assert "nodes" in graph
    assert "edges" in graph
    assert "stats" in graph

    # Verify key nodes are present
    node_ids = [n["id"] for n in graph["nodes"]]
    assert "PRJ-SENTINEL" in node_ids
    assert "COMP-AUTH" in node_ids
    assert "COMP-USERS" in node_ids
    assert "DEC-101" in node_ids
    assert "BUG-101" in node_ids
    assert "FIX-101" in node_ids
    assert "TEST-101" in node_ids

    # Verify key edges exist
    edge_types = [e["type"] for e in graph["edges"]]
    assert "HAS_COMPONENT" in edge_types
    assert "DEPENDS_ON" in edge_types
    assert "AFFECTED_BY" in edge_types
    assert "HAS_BUG" in edge_types
    assert "RESOLVED_BY" in edge_types
    assert "VERIFIED_BY" in edge_types
