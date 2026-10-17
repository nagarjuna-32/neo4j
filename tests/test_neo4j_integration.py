"""
DevGraph Sentinel — Live Neo4j Integration Test Suite
These tests execute ONLY when live Neo4j credentials are provided in .env.
When credentials are not present, pytest marks them as skipped, preventing false failures.
"""
import pytest
from backend.app.config import settings
from backend.app.database import db_manager, NEO4J_INSTALLED
from backend.app.services.graph_service import graph_service


@pytest.mark.skipif(
    not settings.is_neo4j_configured,
    reason="Live Neo4j credentials not configured in .env (NEO4J_URI, NEO4J_PASSWORD required)"
)
class TestLiveNeo4jIntegration:

    @classmethod
    def setup_class(cls):
        """Initialize driver connectivity before live tests."""
        connected = db_manager.initialize()
        assert connected is True, f"Failed to connect to configured Neo4j instance at {settings.NEO4J_URI}"

    @classmethod
    def teardown_class(cls):
        """Close driver session after live tests."""
        db_manager.close()

    def test_live_connectivity_and_version(self):
        records = db_manager.run_query("RETURN 1 AS ping")
        assert len(records) == 1
        assert records[0]["ping"] == 1

    def test_live_schema_and_constraints(self):
        res = graph_service.apply_schema()
        assert res["status"] == "success"
        assert res["statements_executed"] >= 10

    def test_live_idempotent_seed(self):
        res = graph_service.seed_data()
        assert res["status"] == "success"
        assert "Neo4j" in res["database"]
        assert res["node_count"] >= 10

    def test_live_parameterized_traversal(self):
        query = """
        MATCH (c:Component {id: $comp_id})
        OPTIONAL MATCH (c)-[:HAS_BUG]->(b:Bug)
        RETURN c.name AS component_name, count(b) AS bug_count
        """
        records = db_manager.run_query(query, {"comp_id": "COMP-AUTH"})
        assert len(records) == 1
        assert records[0]["component_name"] == "Authentication"
        assert records[0]["bug_count"] >= 1
