"""ITS RAG Search Service — local-first search over ITS documentation."""

from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass
from typing import List, Optional

from .chunker import ITSChunk, ITSChunker

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]{3,}")


@dataclass
class ITSSearchResult:
    """A single search result from ITS documentation."""

    text: str
    section_title: str
    source_file: str
    its_article_id: str
    score: float
    chunk_index: int = 0


class ITSSearchService:
    """Search over local ITS documentation.

    Default mode is offline lexical search over ``docs/its_forms/sections``.
    Semantic Qdrant search is still available with ``ITS_RAG_MODE=semantic`` or
    ``ITS_RAG_MODE=auto`` when all local services/models are already present.
    """

    COLLECTION_NAME = "its_documentation"

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
        mode: str | None = None,
        chunker: ITSChunker | None = None,
    ):
        self.qdrant_url = qdrant_url
        self.embedding_model = embedding_model
        self.mode = (mode or os.getenv("ITS_RAG_MODE") or "offline").lower()
        self.chunker = chunker or ITSChunker()
        self._qdrant = None
        self._embedder = None
        self._offline_chunks: list[ITSChunk] | None = None

    def _get_qdrant(self):
        """Lazy-init Qdrant client."""
        if self._qdrant is None:
            from qdrant_client import QdrantClient

            self._qdrant = QdrantClient(url=self.qdrant_url)
        return self._qdrant

    def _get_embedder(self):
        """Lazy-init sentence-transformers model."""
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(self.embedding_model)
        return self._embedder

    def _embed_query(self, text: str) -> List[float]:
        """Embed a search query."""
        model = self._get_embedder()
        return model.encode(text, normalize_embeddings=True).tolist()

    def _get_offline_chunks(self) -> list[ITSChunk]:
        if self._offline_chunks is None:
            try:
                self._offline_chunks = self.chunker.chunk_all()
            except FileNotFoundError:
                self._offline_chunks = []
        return self._offline_chunks

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [m.group(0).lower() for m in _TOKEN_RE.finditer(text)]

    @classmethod
    def _terms(cls, text: str) -> list[str]:
        terms = []
        for token in cls._tokens(text):
            if len(token) >= 5:
                terms.append(token[:5])
            else:
                terms.append(token)
        return terms

    def _query_offline(
        self,
        question: str,
        limit: int,
        score_threshold: float,
        section_filter: Optional[str],
    ) -> list[ITSSearchResult]:
        query_terms = self._terms(question)
        if not query_terms:
            return []

        query_set = set(query_terms)
        ranked: list[ITSSearchResult] = []
        for chunk in self._get_offline_chunks():
            if (
                section_filter
                and section_filter.lower() not in chunk.section_title.lower()
            ):
                continue

            haystack = f"{chunk.section_title}\n{chunk.text}"
            tokens = self._terms(haystack)
            if not tokens:
                continue

            token_set = set(tokens)
            overlap = query_set & token_set
            if not overlap:
                continue

            hits = sum(tokens.count(token) for token in query_set)
            coverage = len(overlap) / max(len(query_set), 1)
            density = hits / math.sqrt(len(tokens))
            title_tokens = set(self._terms(chunk.section_title))
            title_bonus = len(query_set & title_tokens) / max(len(query_set), 1)
            score = min(
                1.0,
                0.12 + 0.58 * coverage + 0.22 * title_bonus + 0.08 * density,
            )
            if score < score_threshold:
                continue

            ranked.append(
                ITSSearchResult(
                    text=chunk.text,
                    section_title=chunk.section_title,
                    source_file=chunk.source_file,
                    its_article_id=chunk.its_article_id,
                    score=round(score, 4),
                    chunk_index=chunk.chunk_index,
                )
            )

        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:limit]

    def _query_semantic(
        self,
        question: str,
        limit: int,
        score_threshold: float,
        section_filter: Optional[str],
    ) -> list[ITSSearchResult]:
        query_vector = self._embed_query(question)
        qdrant = self._get_qdrant()

        query_filter = None
        if section_filter:
            from qdrant_client.models import FieldCondition, Filter, MatchText

            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="section_title",
                        match=MatchText(text=section_filter),
                    )
                ]
            )

        results = qdrant.search(
            collection_name=self.COLLECTION_NAME,
            query_vector=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=query_filter,
        )

        return [
            ITSSearchResult(
                text=hit.payload.get("text", ""),
                section_title=hit.payload.get("section_title", ""),
                source_file=hit.payload.get("source_file", ""),
                its_article_id=hit.payload.get("its_article_id", ""),
                score=hit.score,
                chunk_index=hit.payload.get("chunk_index", 0),
            )
            for hit in results
        ]

    async def query(
        self,
        question: str,
        limit: int = 5,
        score_threshold: float = 0.3,
        section_filter: Optional[str] = None,
    ) -> List[ITSSearchResult]:
        """Search ITS documentation."""
        if self.mode == "offline":
            return self._query_offline(question, limit, score_threshold, section_filter)

        if self.mode == "semantic":
            return self._query_semantic(
                question, limit, score_threshold, section_filter
            )

        try:
            return self._query_semantic(
                question, limit, score_threshold, section_filter
            )
        except Exception as exc:
            logger.info(
                "ITS semantic search unavailable, using offline search: %s", exc
            )
            return self._query_offline(question, limit, score_threshold, section_filter)

    async def get_context_for_llm(
        self,
        question: str,
        max_chunks: int = 3,
        max_chars: int = 6000,
    ) -> str:
        """Get formatted context for LLM augmentation."""
        results = await self.query(question, limit=max_chunks)

        if not results:
            return ""

        context_parts = []
        total_chars = 0
        for r in results:
            chunk_text = (
                f"[Источник: {r.section_title} | Файл: {r.source_file}]\n{r.text}"
            )
            if total_chars + len(chunk_text) > max_chars:
                break
            context_parts.append(chunk_text)
            total_chars += len(chunk_text)

        return "\n\n---\n\n".join(context_parts)
