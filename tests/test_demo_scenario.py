"""
DevGraph Sentinel — Official Demo Scenario End-to-End Test
Validates the exact 9 steps from Section 17 of the Master Prompt.
"""
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_full_demo_scenario_flow(client):
    # Step 1: Seed the synthetic project graph
    seed_res = client.post("/api/seed")
    assert seed_res.status_code == 200
    seed_data = seed_res.json()
    assert seed_data["project_id"] == "PRJ-SENTINEL"
    assert seed_data["node_count"] >= 10

    # Step 2: Display connected components, dependencies, decision, bug, fix, test
    graph_res = client.get("/api/graph?project_id=PRJ-SENTINEL")
    assert graph_res.status_code == 200
    graph = graph_res.json()
    node_ids = {n["id"]: n for n in graph["nodes"]}

    assert "COMP-AUTH" in node_ids
    assert "COMP-USERS" in node_ids
    assert "COMP-ADMIN" in node_ids
    assert "COMP-NOTIF" in node_ids
    assert "DEP-JWT" in node_ids
    assert "DEP-FASTAPI" in node_ids
    assert "DEP-POSTGRES" in node_ids
    assert "DEC-101" in node_ids
    assert "BUG-101" in node_ids
    assert "FIX-101" in node_ids
    assert "TEST-101" in node_ids

    # Step 3: Ask the contextual debugging question
    question = "The Users API returns HTTP 401 after the authentication refactor. Why might this happen, and what should I investigate before merging?"
    analyze_res = client.post("/api/analyze", json={
        "project_id": "PRJ-SENTINEL",
        "question": question,
        "component": "Authentication",
    })
    assert analyze_res.status_code == 200
    analysis = analyze_res.json()

    # Step 4: Show relevant historical incident and connected decision
    evidence_ids = [e["id"] for e in analysis["relevant_evidence"]]
    assert "BUG-101" in evidence_ids or any("BUG-101" in path for path in analysis["evidence_paths"])
    assert "DEC-101" in evidence_ids or any("DEC-101" in path for path in analysis["evidence_paths"])

    # Step 5: Explain that the previous incident involved missing refresh-token middleware
    answer_text = analysis["answer"].lower()
    assessment_text = analysis["assessment"].lower()
    full_output = answer_text + " " + assessment_text
    assert "refresh-token" in full_output or "middleware" in full_output

    # Step 6: Recommend checking middleware registration, token expiry, validation, logs, tests
    checks_and_text = " ".join(analysis["suggested_checks"]).lower() + " " + full_output
    assert "middleware" in checks_and_text
    assert "token" in checks_and_text
    assert len(analysis["suggested_checks"]) >= 3
    assert len(analysis["suggested_tests"]) >= 1

    # Step 7: Show the graph paths supporting the answer
    assert len(analysis["evidence_paths"]) >= 2
    path_sample = analysis["evidence_paths"][0]
    assert "-[:" in path_sample and "]->(" in path_sample

    # Step 8: Run change impact analysis for Authentication
    impact_res = client.post("/api/impact", json={
        "project_id": "PRJ-SENTINEL",
        "changed_components": ["Authentication"],
    })
    assert impact_res.status_code == 200
    impact = impact_res.json()
    affected_names = [a["name"] for a in impact["affected_components"]]
    assert "Authentication" in affected_names
    assert "Users API" in affected_names
    assert "Admin Dashboard" in affected_names
    assert impact["heuristic_priority"] in ["HIGH", "MEDIUM"]
    assert len(impact["historical_risks"]) >= 1

    # Step 9: Save a new decision and demonstrate that it persists
    new_dec_payload = {
        "memory_type": "decision",
        "project_id": "PRJ-SENTINEL",
        "title": "Migrate Token Signing Algorithm to Ed25519",
        "affected_component": "Authentication",
        "reason": "Upgrade cryptographic strength and optimize asymmetric signature verification throughput.",
        "description": "Transition from RS256 to Ed25519 (RFC 8037) for token signing and public key distribution.",
        "author": "Security Engineering Lead",
    }
    mem_res = client.post("/api/memory", json=new_dec_payload)
    assert mem_res.status_code == 201
    mem_data = mem_res.json()
    new_entity_id = mem_data["entity_id"]
    assert new_entity_id.startswith("DEC-")

    # Verify that the new decision persists in the graph
    graph_recheck = client.get("/api/graph?project_id=PRJ-SENTINEL")
    assert graph_recheck.status_code == 200
    updated_node_ids = {n["id"]: n for n in graph_recheck.json()["nodes"]}
    assert new_entity_id in updated_node_ids
    saved_node = updated_node_ids[new_entity_id]
    assert saved_node["properties"]["title"] == "Migrate Token Signing Algorithm to Ed25519"
