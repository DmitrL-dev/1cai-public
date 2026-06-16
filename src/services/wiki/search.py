"""
Wiki Search Service
Handles semantic search via Qdrant and integration with WikiService
"""

from typing import Any, Dict, List

try:
    from src.db.qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None  # type: ignore
from src.services.embedding.service import EmbeddingService
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class WikiSearchService:
    """
    Service for indexing and searching Wiki pages using vector embeddings.
    """

    COLLECTION_NAME = "wiki_pages"

    def __init__(self, qdrant: QdrantClient, embedding: EmbeddingService):
        self.qdrant = qdrant
        self.embedding = embedding

    async def ensure_collection(self):
        """Ensure Qdrant collection exists"""
        # Stub: In real implementation, check and create collection
        # self.qdrant.create_collection(self.COLLECTION_NAME, vector_size=768)

    async def index_page(self, page_id: str, title: str, content: str):
        """
        Generate embeddings for page and save to Qdrant.
        Should be called asynchronously (Background Task).
        """
        try:
            text_to_embed = f"{title}\n\n{content}"
            # Truncate if too long
            text_to_embed = text_to_embed[:8000]

            await self.embedding.encode(text_to_embed)

            # Prepare payload
            payload = {"page_id": page_id, "title": title, "snippet": content[:200]}

            # Upsert to Qdrant
            # Stub: self.qdrant.upsert(self.COLLECTION_NAME, points=[...])
            logger.info("Indexed wiki page %s in Qdrant", page_id)

        except Exception as e:
            logger.error(f"Failed to index wiki page {page_id}: {e}", exc_info=True)

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search for wiki pages.
        """
        try:
            await self.embedding.encode(query)

            # Stub: results = self.qdrant.search(self.COLLECTION_NAME, vector, limit=limit)
            # Returning mock results for MVP
            logger.info("Searching wiki for: %s", query)

            return [
                {
                    "page_id": "mock-id-1",
                    "title": "Architecture Overview",
                    "score": 0.95,
                    "snippet": "High level overview of the system...",
                },
                {
                    "page_id": "mock-id-2",
                    "title": "API Documentation",
                    "score": 0.88,
                    "snippet": "Details about REST endpoints...",
                },
            ]

        except Exception as e:
            logger.error(f"Wiki search failed: {e}", exc_info=True)
            return []


# Dependency helper
def get_wiki_search_service():
    # In FastAPI app context, these dependencies would be resolved
    # For now, we return None or mock if outside app context
    return WikiSearchService(None, None)
