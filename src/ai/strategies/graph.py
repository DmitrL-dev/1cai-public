import asyncio
from typing import Any, Dict

from src.ai.nl_to_cypher import get_nl_to_cypher_converter
from src.ai.strategies.base import AIStrategy

try:
    from src.db.neo4j_client import get_neo4j_client
except ImportError:
    get_neo4j_client = None  # type: ignore
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class Neo4jStrategy(AIStrategy):
    """Strategy for Neo4j Graph Queries"""

    def __init__(self):
        # No side effects in init
        pass

    @property
    def service_name(self) -> str:
        return "neo4j"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        client = get_neo4j_client()
        if not client:
            return {"error": "Neo4j client not available", "service": self.service_name}

        try:
            # Convert NL to Cypher
            converter = get_nl_to_cypher_converter()
            cypher_result = converter.convert(query)

            # Validate cypher is safe
            if not converter.validate_cypher(cypher_result["cypher"]):
                return {
                    "type": "graph_query",
                    "error": "Unsafe query detected. Only read operations allowed.",
                    "service": self.service_name,
                }

            # Execute on Neo4j
            # Use async executor if client is synchronous, or await if async
            # Assuming execute_query is blocking based on previous context, wrapping in thread
            results = await asyncio.to_thread(
                client.execute_query, cypher_result["cypher"]
            )

            return {
                "type": "graph_query",
                "service": self.service_name,
                "cypher": cypher_result["cypher"],
                "confidence": cypher_result["confidence"],
                "results": results,
                "count": len(results) if results else 0,
                "explanation": cypher_result["explanation"],
            }

        except Exception as e:
            logger.error(f"Neo4j strategy error: {e}", exc_info=True)
            return {"error": str(e), "service": self.service_name}
