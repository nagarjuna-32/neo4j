import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_decision_memory(client):
    payload = {
        "memory_type": "decision",
        "project_id": "PRJ-SENTINEL",
        "title": "Adopt Redis Cache for Users API",
        "affected_component": "Users API",
        "description": "Cache frequent user profile reads in Redis cluster to reduce database load.",
        "reason": "Reduce DB query latency by 60% during high traffic peaks.",
        "author": "Backend Lead",
    }
    response = client.post("/api/memory", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["entity_type"] == "Decision"
    assert data["entity_id"].startswith("DEC-")
    assert len(data["connected_paths"]) >= 1

    # Verify decision is now in the graph
    graph_res = client.get("/api/graph?project_id=PRJ-SENTINEL")
    assert graph_res.status_code == 200
    node_ids = [n["id"] for n in graph_res.json()["nodes"]]
    assert data["entity_id"] in node_ids


def test_create_bug_memory(client):
    payload = {
        "memory_type": "bug",
        "project_id": "PRJ-SENTINEL",
        "title": "Cache invalidation fails on user email update",
        "affected_component": "Users API",
        "symptom": "Stale email returned after profile update",
        "root_cause": "Missing Redis key eviction call on PUT /users/me endpoint",
        "resolution": "Evict user cache key inside transaction post-commit hook",
        "verification": "Regression test test_profile_update_cache_invalidation passed",
    }
    response = client.post("/api/memory", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["entity_type"] == "Bug"
    assert data["entity_id"].startswith("BUG-")

    # Verify bug is now in the graph
    graph_res = client.get("/api/graph?project_id=PRJ-SENTINEL")
    assert graph_res.status_code == 200
    node_ids = [n["id"] for n in graph_res.json()["nodes"]]
    assert data["entity_id"] in node_ids
