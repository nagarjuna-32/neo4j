import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

try:
    from neo4j import GraphDatabase, Driver, Session
    from neo4j.exceptions import ServiceUnavailable, AuthError, Neo4jError
    NEO4J_INSTALLED = True
except ImportError:
    NEO4J_INSTALLED = False
    Driver = None
    Session = None

from backend.app.config import settings

logger = logging.getLogger("codebrain.database")


class Neo4jConnectionManager:
    def __init__(self):
        self._driver: Optional[Driver] = None
        self._is_connected: bool = False
        self._connection_error: Optional[str] = None

    def initialize(self) -> bool:
        if not NEO4J_INSTALLED:
            self._connection_error = "neo4j python driver is not installed in the current environment"
            logger.warning(self._connection_error)
            self._is_connected = False
            return False

        if not settings.is_neo4j_configured:
            self._connection_error = (
                "Neo4j credentials not configured. Set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD in .env"
            )
            logger.info("Neo4j not configured. Running in Local Graph Engine mode.")
            self._is_connected = False
            return False

        try:
            logger.info(f"Connecting to Neo4j instance at {settings.NEO4J_URI}...")
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
                max_connection_lifetime=30 * 60,
                connection_timeout=5.0,
            )
            # Verify connectivity
            self._driver.verify_connectivity()
            self._is_connected = True
            self._connection_error = None
            logger.info("Successfully connected to Neo4j database.")
            return True
        except (ServiceUnavailable, AuthError, Neo4jError, Exception) as exc:
            self._is_connected = False
            safe_err = str(exc)
            if settings.NEO4J_PASSWORD and settings.NEO4J_PASSWORD in safe_err:
                safe_err = safe_err.replace(settings.NEO4J_PASSWORD, "******")
            self._connection_error = f"Neo4j connection error: {safe_err}"
            logger.warning(
                f"Failed to connect to Neo4j: {safe_err}. Falling back to Local Graph Engine."
            )
            return False

    def close(self):
        if self._driver:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None
            self._is_connected = False
            logger.info("Neo4j driver closed.")

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def connection_error(self) -> Optional[str]:
        return self._connection_error

    @contextmanager
    def get_session(self):
        if not self._is_connected or not self._driver:
            raise RuntimeError(
                f"Neo4j driver is not active. {self._connection_error or 'Not connected.'}"
            )
        session = self._driver.session(database=settings.NEO4J_DATABASE)
        try:
            yield session
        finally:
            session.close()

    def run_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a read/write Cypher query and return results as a list of dicts."""
        if not self._is_connected:
            raise RuntimeError(
                f"Cannot execute Cypher query: Neo4j is offline ({self._connection_error})"
            )
        parameters = parameters or {}
        with self.get_session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]


db_manager = Neo4jConnectionManager()
