import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.chat_service import chat_service
from backend.app.models import ChatMessage


@pytest.fixture
def client():
    return TestClient(app)


# 1. Ask for a component's recorded information
def test_chat_component_information(client):
    payload = {
        "message": "What is the Authentication component?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["intent"] in ("direct_info", "general")
    assert "Authentication" in data["answer"]
    assert len(data["evidence"]) > 0

    # Verify component evidence
    evidence_ids = [e["id"] for e in data["evidence"]]
    assert "COMP-AUTH" in evidence_ids
    assert any(e["type"] == "Component" for e in data["evidence"])
    assert len(data["suggested_actions"]) > 0
    assert len(data["follow_up_questions"]) > 0


# 2. Ask why a documented architectural decision was made
def test_chat_decision_rationale(client):
    payload = {
        "message": "Why did we migrate to JWT?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "JWT" in data["answer"] or "stateless" in data["answer"].lower()
    evidence_ids = [e["id"] for e in data["evidence"]]
    assert "DEC-101" in evidence_ids
    assert any(e["type"] == "Decision" for e in data["evidence"])

    # Rationale must not be invented; must reference mobile / stateless
    assert "mobile" in data["answer"].lower() or "stateless" in data["answer"].lower()


# 3. Ask about a known historical bug
def test_chat_debugging_known_bug(client):
    payload = {
        "message": "The Users API returns HTTP 401. How do I fix it?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["intent"] == "debugging"
    assert "BUG-101" in [e["id"] for e in data["evidence"]]
    assert "FIX-101" in [e["id"] for e in data["evidence"]]
    assert "401" in data["answer"]
    assert "TokenValidationMiddleware" in data["answer"] or "middleware" in data["answer"].lower()
    assert len(data["suggested_actions"]) > 0


# 4. Ask a general Python or FastAPI question
def test_chat_code_question(client):
    payload = {
        "message": "How should I handle expired JWT tokens in FastAPI?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["intent"] == "code_question"
    assert "```python" in data["answer"]
    assert "FastAPI" in data["answer"] or "fastapi" in data["answer"].lower()


# 5. Ask about potential change impact and reverse dependencies
def test_chat_reverse_dependencies(client):
    payload = {
        "message": "Which components depend on Authentication?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "Users API" in data["answer"] or "COMP-USERS" in data["answer"]
    evidence_ids = [e["id"] for e in data["evidence"]]
    assert "COMP-USERS" in evidence_ids


def test_chat_change_impact_question(client):
    payload = {
        "message": "What could be affected if I change the JWT middleware?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "Users API" in data["answer"] or "COMP-USERS" in data["answer"]
    assert "downstream" in data["answer"].lower() or "impact" in data["answer"].lower()


def test_chat_list_all_bugs(client):
    payload = {
        "message": "Show all recorded bugs.",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "BUG-101" in data["answer"]
    assert any(e["id"] == "BUG-101" for e in data["evidence"])


def test_chat_verified_tests(client):
    payload = {
        "message": "Which fixes have verified regression tests?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "FIX-101" in data["answer"]
    assert "TEST-101" in data["answer"]


# 6. Ask a question for which no project evidence exists
def test_chat_no_evidence_question(client):
    payload = {
        "message": "How do I deploy a Kubernetes Helm chart for Ruby on Rails?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Evidence list should not invent nonexistent project records
    project_memory_evidence = [e for e in data["evidence"] if e["source"] == "Project Memory" and "Helm" in e["title"]]
    assert len(project_memory_evidence) == 0


# 7. Test AI provider failure & deterministic fallback
def test_chat_deterministic_fallback(client, monkeypatch):
    # Simulate OpenAI client failing or disabled
    monkeypatch.setattr(chat_service, "openai_client", None)

    payload = {
        "message": "The Users API returns HTTP 401. How do I fix it?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "Deterministic Knowledge Engine" in data["ai_provider"]
    assert data["model_used"] is None
    assert "BUG-101" in [e["id"] for e in data["evidence"]]
    assert "FIX-101" in [e["id"] for e in data["evidence"]]


# 8. Test conversation follow-ups and context preservation
def test_chat_conversation_follow_up(client):
    # Turn 1: initial question
    turn1_history = []
    payload1 = {
        "message": "The Users API returns HTTP 401. How do I fix it?",
        "project_id": "PRJ-SENTINEL",
        "history": turn1_history,
    }
    resp1 = client.post("/api/chat", json=payload1)
    assert resp1.status_code == 200
    data1 = resp1.json()

    # Turn 2: follow-up asking for the fix in Python
    turn2_history = [
        {"role": "user", "content": payload1["message"]},
        {"role": "assistant", "content": data1["answer"]},
    ]
    payload2 = {
        "message": "Show the fix in Python.",
        "project_id": "PRJ-SENTINEL",
        "conversation_id": data1["conversation_id"],
        "history": turn2_history,
    }
    resp2 = client.post("/api/chat", json=payload2)
    assert resp2.status_code == 200
    data2 = resp2.json()

    # Should retain the conversation id and return python code
    assert data2["conversation_id"] == data1["conversation_id"]
    assert "```python" in data2["answer"]


# 9. Verify displayed evidence schema and source labels
def test_chat_evidence_schema(client):
    payload = {
        "message": "What is the Authentication component?",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    for ev in data["evidence"]:
        assert "id" in ev
        assert "type" in ev
        assert "title" in ev
        assert "source" in ev
        assert ev["source"] in ("Project Memory", "General Engineering Guidance", "Hypothesis")


# 10. Test input validation
def test_chat_empty_message_validation(client):
    payload = {
        "message": "   ",
        "project_id": "PRJ-SENTINEL",
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()
