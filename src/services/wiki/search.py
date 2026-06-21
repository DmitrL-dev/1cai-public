"""Wiki search service with honest offline lexical fallback."""

from __future__ import annotations

import inspect
import re
from typing import Any, Dict, List, Optional

try:
    from src.db.qdrant_client import QdrantClient
except ImportError:
    QdrantClient = None  # type: ignore
from src.services.embedding.service import EmbeddingService
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

_WORD_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]{3,}", re.IGNORECASE)


class WikiSearchService:
    """Service for indexing and searching Wiki pages."""

    COLLECTION_NAME = "wiki_pages"

    def __init__(
        self,
        qdrant: Optional[QdrantClient] = None,
        embedding: Optional[EmbeddingService] = None,
    ):
        self.qdrant = qdrant
        self.embedding = embedding
        self._offline_pages: dict[str, dict[str, Any]] = {}

    async def ensure_collection(self):
        """Ensure the configured vector collection exists when an adapter is present."""
        if self.qdrant and hasattr(self.qdrant, "create_collection"):
            result = self.qdrant.create_collection(self.COLLECTION_NAME, vector_size=768)
            if inspect.isawaitable(result):
                await result
            return {"mode": "qdrant", "collection": self.COLLECTION_NAME}
        return {"mode": "offline-lexical", "collection": None}

    async def index_page(self, page_id: str, title: str, content: str):
        """
        Generate embeddings for page and save to Qdrant.
        Should be called asynchronously (Background Task).
        """
        try:
            text_to_embed = f"{title}\n\n{content}"
            text_to_embed = text_to_embed[:8000]

            vector = None
            if self.embedding:
                vector = await self.embedding.encode(text_to_embed)

            payload = {"page_id": page_id, "title": title, "snippet": content[:200]}

            if self.qdrant and vector is not None and hasattr(self.qdrant, "upsert"):
                result = self.qdrant.upsert(self.COLLECTION_NAME, points=[payload])
                if inspect.isawaitable(result):
                    await result
                logger.info("Indexed wiki page %s in Qdrant", page_id)
                return {"mode": "qdrant", "page_id": page_id}

            self._offline_pages[page_id] = {
                "page_id": page_id,
                "title": title,
                "content": content,
                "snippet": self._snippet(content),
            }
            logger.info("Indexed wiki page %s in offline lexical index", page_id)
            return {"mode": "offline-lexical", "page_id": page_id}

        except Exception as e:
            logger.error(f"Failed to index wiki page {page_id}: {e}", exc_info=True)
            return {"mode": "error", "page_id": page_id, "error": str(e)}

    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Semantic search for wiki pages.
        """
        try:
            logger.info("Searching wiki for: %s", query)
            vector = await self.embedding.encode(query) if self.embedding else None
            if self.qdrant and vector is not None and hasattr(self.qdrant, "search"):
                results = self.qdrant.search(
                    self.COLLECTION_NAME,
                    vector,
                    limit=limit,
                )
                if inspect.isawaitable(results):
                    results = await results
                return [self._normalize_result(item) for item in results]

            return self._lexical_search(query, limit=limit)

        except Exception as e:
            logger.error(f"Wiki search failed: {e}", exc_info=True)
            return []

    def _lexical_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        terms = self._tokens(query)
        if not terms:
            return []
        results: list[dict[str, Any]] = []
        for page in self._offline_pages.values():
            haystack = f"{page.get('title', '')} {page.get('content', '')}"
            score = self._score(terms, haystack)
            if score <= 0:
                continue
            results.append(
                {
                    "page_id": page["page_id"],
                    "title": page["title"],
                    "score": score,
                    "snippet": self._snippet(page.get("content", "")),
                    "mode": "offline-lexical",
                }
            )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def _normalize_result(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            payload = item.get("payload") or item
            return {
                "page_id": payload.get("page_id") or item.get("id"),
                "title": payload.get("title", "Untitled"),
                "score": float(item.get("score", payload.get("score", 0.0)) or 0.0),
                "snippet": payload.get("snippet", ""),
                "mode": "qdrant",
            }
        return {
            "page_id": getattr(item, "id", None),
            "title": "Untitled",
            "score": float(getattr(item, "score", 0.0) or 0.0),
            "snippet": "",
            "mode": "qdrant",
        }

    def _tokens(self, text: str) -> set[str]:
        return {token.lower() for token in _WORD_RE.findall(text or "")}

    def _score(self, terms: set[str], text: str) -> float:
        haystack = " ".join(_WORD_RE.findall(text or "")).lower()
        if not haystack:
            return 0.0
        matches = sum(1 for term in terms if term in haystack)
        return round(matches / max(len(terms), 1), 3)

    def _snippet(self, content: str, limit: int = 200) -> str:
        compact = " ".join(str(content or "").split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3].rstrip() + "..."


# Dependency helper
def get_wiki_search_service():
    return WikiSearchService(None, None)
