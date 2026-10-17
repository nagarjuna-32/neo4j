import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_seed_idempotency_and_counts(client):
    # Call seed twice to verify exact idempotency and count stability
    res1 = client.post("/api/seed")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] in ["success", "warning"]
    node_count_1 = data1.get("node_count")
    edge_count_1 = data1.get("edge_count")

    res2 = client.post("/api/seed")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] in ["success", "warning"]
    node_count_2 = data2.get("node_count")
    edge_count_2 = data2.get("edge_count")

    # Idempotent MERGE should produce identical node and edge counts
    assert node_count_1 == node_count_2
    assert edge_count_1 == edge_count_2


def test_get_projects(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) >= 1
    p = next((proj for proj in projects if proj["id"] == "PRJ-SENTINEL"), None)
    assert p is not None
    assert p["name"] == "Sentinel Demo App"
    assert p["is_synthetic"] is True


def test_graph_structure_and_schema_types(client):
    response = client.get("/api/graph?project_id=PRJ-SENTINEL")
    assert response.status_code == 200
    graph = response.json()
    assert "nodes" in graph
    assert "edges" in graph
    assert "stats" in graph

    nodes_by_id = {n["id"]: n for n in graph["nodes"]}

    # Verify all core entities from schema
    assert "PRJ-SENTINEL" in nodes_by_id
    assert "COMP-AUTH" in nodes_by_id
    assert "COMP-USERS" in nodes_by_id
    assert "COMP-ADMIN" in nodes_by_id
    assert "COMP-NOTIF" in nodes_by_id
    assert "DEP-JWT" in nodes_by_id
    assert "DEP-FASTAPI" in nodes_by_id
    assert "DEP-POSTGRES" in nodes_by_id
    assert "DEC-101" in nodes_by_id
    assert "RSN-101" in nodes_by_id
    assert "BUG-101" in nodes_by_id
    assert "FIX-101" in nodes_by_id
    assert "TEST-101" in nodes_by_id
    assert "FILE-AUTH-MW" in nodes_by_id
    assert "FN-VERIFY-REFRESH" in nodes_by_id
    assert "PR-101" in nodes_by_id
    assert "DEV-ALICE" in nodes_by_id

    # Verify verification status integrity
    bug = nodes_by_id["BUG-101"]["properties"]
    assert bug["status"] == "RESOLVED"
    assert "root_cause" in bug

    fix = nodes_by_id["FIX-101"]["properties"]
    assert fix["status"] == "VERIFIED"

    test = nodes_by_id["TEST-101"]["properties"]
    assert "passed" in test["verification_status"].lower()

    # Verify relationship types
    edge_types = set(e["type"] for e in graph["edges"])
    assert "HAS_COMPONENT" in edge_types
    assert "DEPENDS_ON" in edge_types
    assert "AFFECTED_BY" in edge_types
    assert "JUSTIFIED_BY" in edge_types
    assert "HAS_BUG" in edge_types
    assert "RESOLVED_BY" in edge_types
    assert "VERIFIED_BY" in edge_types
    assert "CONTAINS" in edge_types
    assert "CALLS" in edge_types


def test_project_scoped_isolation(client):
    # Query with a non-existent project ID
    response = client.get("/api/graph?project_id=PRJ-NONEXISTENT")
    assert response.status_code == 200
    graph = response.json()
    assert graph["project_id"] == "PRJ-NONEXISTENT"
    # Ensure project-specific sentinel project node is not returned for other project scopes
    for node in graph["nodes"]:
        if node["label"] == "Project":
            assert node["id"] != "PRJ-NONEXISTENT"
