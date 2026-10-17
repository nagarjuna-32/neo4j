"""
CodeBrain AI — Error Handling, Security, and Mocked Dependencies Test Suite
Validates:
- Mocked database failure in memory creation -> HTTP 500 with clean error detail
- Mocked OpenAI API failure -> graceful fallback to deterministic evidence engine
- Handling of empty evidence / missing context
- Security assertions: no passwords, API keys, or raw secrets leaked in any response
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.ai_service import ai_service


@pytest.fixture
def client():
    return TestClient(app)


def test_mocked_database_error_on_memory_creation(client):
    """Verify robust 500 handling when database throws an exception during memory persistence."""
    with patch("backend.app.services.graph_service.graph_service.add_memory_decision") as mock_add:
        mock_add.side_effect = RuntimeError("Simulated transient connection timeout to Neo4j cluster")

        payload = {
            "memory_type": "decision",
            "project_id": "PRJ-SENTINEL",
            "title": "Adopt gRPC for Internal RPCs",
            "affected_component": "Users API",
            "reason": "Reduce network latency",
        }
        response = client.post("/api/memory", json=payload)
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to persist memory" in data["detail"]
        # Ensure raw database credentials are not in response
        assert "password" not in data["detail"].lower()


def test_mocked_openai_failure_falls_back_gracefully(client):
    """Verify that when OpenAI client raises an exception, the system uses deterministic fallback."""
    # Force mock client that raises an exception
    with patch.object(ai_service, "client") as mock_client:
        mock_client.chat.completions.create.side_effect = ConnectionError("OpenAI API unreachable / RateLimit")

        payload = {
            "project_id": "PRJ-SENTINEL",
            "question": "The Users API returns HTTP 401 after the authentication refactor. Why might this happen?",
            "component": "Authentication",
        }
        response = client.post("/api/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()

        # Should fall back gracefully to deterministic engine
        assert "deterministic_graph_engine" in data["source"]
        assert len(data["relevant_evidence"]) > 0
        assert "refresh-token" in data["answer"].lower() or "middleware" in data["answer"].lower()


def test_empty_evidence_handling(client):
    """Verify querying an unknown component returns structured guidance acknowledging lack of evidence."""
    payload = {
        "project_id": "PRJ-SENTINEL",
        "question": "Why is the Payment Gateway webhooks listener dropping TLS 1.3 packets?",
        "component": "Payment Gateway Unknown",
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "evidence_limitations" in data
    # In absence of direct bug records, it shouldn't invent fake incidents
    assert len(data["historical_bugs"]) == 0


def test_security_no_secrets_leaked(client):
    """Verify that no endpoint leaks secrets, passwords, or raw environment variables."""
    endpoints = [
        ("GET", "/api/health", None),
        ("GET", "/api/projects", None),
        ("GET", "/api/graph?project_id=PRJ-SENTINEL", None),
        ("GET", "/api/activity?project_id=PRJ-SENTINEL", None),
        ("POST", "/api/analyze", {
            "project_id": "PRJ-SENTINEL",
            "question": "Check security credentials",
            "component": "Authentication",
        }),
        ("POST", "/api/impact", {
            "project_id": "PRJ-SENTINEL",
            "changed_components": ["Authentication"],
        }),
    ]

    sensitive_patterns = ["password=", "api_key=", "sk-proj-", "sk-", "authorization: bearer", "bearer eyj"]

    for method, url, payload in endpoints:
        if method == "GET":
            res = client.get(url)
        else:
            res = client.post(url, json=payload)

        body_text = res.text.lower()
        for pattern in sensitive_patterns:
            assert pattern not in body_text, f"Potential sensitive leak '{pattern}' detected in {method} {url}"


def test_parameterized_cypher_injection_resilience(client):
    """Verify that Cypher injection payloads in user inputs do not break execution."""
    malicious_inputs = [
        "Authentication'; DROP CONSTRAINT project_id_unique; --",
        "Users API' OR 1=1 --",
        '{"$gt": ""}',
    ]

    for evil_input in malicious_inputs:
        res = client.post("/api/analyze", json={
            "project_id": "PRJ-SENTINEL",
            "question": f"What decisions affected {evil_input}?",
            "component": evil_input,
        })
        # Should be handled gracefully without crashing or throwing 500
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
