import asyncio
from typing import Any, Dict

from src.ai.strategies.base import AIStrategy

try:
    from src.db.qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None  # type: ignore
from src.services.embedding_service import EmbeddingService
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class QdrantStrategy(AIStrategy):
    """Strategy for Semantic Search with Qdrant"""

    def __init__(self):
        try:
            self.client = QdrantClient()
            self.embedding_service = EmbeddingService()
            self.is_available = True
        except Exception as e:
            logger.warning("Qdrant/Embedding services not available: %s", e)
            self.client = None
            self.embedding_service = None
            self.is_available = False

    @property
    def service_name(self) -> str:
        return "qdrant"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_available:
            return {
                "error": "Vector search services not available",
                "service": self.service_name,
            }

        try:
            # Generate embedding
            query_vector = await self.embedding_service.generate_embedding(query)

            # Search in Qdrant
            search_results = await asyncio.to_thread(
                self.client.search,
                collection_name="code_snippets",
                query_vector=query_vector,
                limit=context.get("limit", 10),
            )

            # Format results
            formatted_results = []
            for result in search_results:
                formatted_results.append(
                    {
                        "code": result.payload.get("code", ""),
                        "function_name": result.payload.get("function_name", "Unknown"),
                        "module": result.payload.get("module", "Unknown"),
                        "score": float(result.score),
                        "description": result.payload.get("description", ""),
                    }
                )

            return {
                "type": "semantic_search",
                "service": self.service_name,
                "query": query,
                "results": formatted_results,
                "count": len(formatted_results),
                "explanation": f"Found {len(formatted_results)} code snippets similar to your query",
            }

        except Exception as e:
            logger.error(f"Qdrant strategy error: {e}", exc_info=True)
            return {"error": str(e), "service": self.service_name}
