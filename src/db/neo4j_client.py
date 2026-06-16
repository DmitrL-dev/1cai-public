"""Neo4j client for 1C code graph storage."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Async-compatible Neo4j client wrapper.

    Usage:
        client = Neo4jClient("bolt://localhost:7687")
        client.verify_connectivity()
        results = client.run("MATCH (n) RETURN n LIMIT 10")
        client.close()
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "sentinel2026",
        database: str = "neo4j",
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            try:
                from neo4j import GraphDatabase

                self._driver = GraphDatabase.driver(
                    self.uri, auth=(self.user, self.password)
                )
                logger.info("Neo4j connected: %s", self.uri)
            except ImportError:
                raise ImportError("neo4j not installed. Run: pip install neo4j")
        return self._driver

    def verify_connectivity(self) -> bool:
        try:
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error("Neo4j connectivity check failed: %s", e)
            return False

    def run(self, query: str, parameters: Optional[dict] = None) -> list[dict]:
        """Execute a Cypher query and return results as list of dicts."""
        with self.driver.session(database=self.database) as session:
            result = session.run(query, parameters or {})
            return [self._sanitize(record.data()) for record in result]

    @staticmethod
    def _sanitize(obj):
        """Recursively convert Neo4j types to JSON-safe Python types."""
        if isinstance(obj, dict):
            return {k: Neo4jClient._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [Neo4jClient._sanitize(v) for v in obj]
        if isinstance(obj, bool):
            return obj
        if isinstance(obj, int):
            return int(obj)
        if isinstance(obj, float):
            return float(obj)
        if hasattr(obj, "__int__"):
            return int(obj)
        if hasattr(obj, "__float__"):
            return float(obj)
        if obj is None:
            return None
        return str(obj)

    def run_write(self, query: str, parameters: Optional[dict] = None) -> Any:
        """Execute a write Cypher query in a transaction."""
        with self.driver.session(database=self.database) as session:
            return session.execute_write(
                lambda tx: tx.run(query, parameters or {}).consume()
            )

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None


def get_neo4j_client() -> Neo4jClient:
    """FastAPI dependency for Neo4j client."""
    import os

    return Neo4jClient(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "sentinel2026"),
    )
