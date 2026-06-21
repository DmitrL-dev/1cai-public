"""
Wiki Service Implementation
Handles logic for page management, versioning, rendering, and advanced features (Blueprints, AI)
"""

import inspect
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.infrastructure.db.connection import get_db_connection
from src.utils.structured_logging import StructuredLogger

# Import DTOs
from .models import WikiPage as PageDTO
from .models import WikiPageCreate, WikiPageUpdate

# Import Renderer
from .renderer import WikiRenderer

logger = StructuredLogger(__name__).logger

_WORD_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]{3,}", re.IGNORECASE)


class WikiService:
    """
    Service for managing Wiki pages with versioning, code integration, and AI features.
    """

    def __init__(self, db_session=None):
        self.renderer = WikiRenderer()
        # Optional semantic index. When absent, Wiki answers stay lexical and caveated.
        self.qdrant = None

    async def get_page(
        self, slug: str, version: Optional[int] = None
    ) -> Optional[PageDTO]:
        """
        Retrieve a wiki page by slug from DB.
        """
        query = """
            SELECT
                p.id, p.slug, p.title, p.namespace_id, p.current_revision_id, p.version, p.created_at, p.updated_at,
                r.content
            FROM wiki_pages p
            LEFT JOIN wiki_revisions r ON p.current_revision_id = r.id
            WHERE p.slug = $1 AND p.is_deleted = FALSE
        """
        params = [slug]

        if version:
            query = """
                SELECT
                    p.id, p.slug, p.title, p.namespace_id, p.current_revision_id, p.version, p.created_at, p.updated_at,
                    r.content
                FROM wiki_pages p
                JOIN wiki_revisions r ON r.page_id = p.id
                WHERE p.slug = $1 AND r.version = $2
            """
            params = [slug, version]

        async with get_db_connection() as conn:
            row = await conn.fetchrow(query, *params)

            if not row:
                return None

            # Render content on the fly (or cache it in future)
            html_content = (
                self.renderer.render(row["content"]) if row["content"] else ""
            )

            # Construct DTO
            page_dto = PageDTO(
                id=row["id"],
                slug=row["slug"],
                namespace=row["namespace_id"] or "default",
                title=row["title"],
                current_revision_id=str(row["current_revision_id"] or ""),
                version=row["version"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            page_dto.html_content = html_content  # Attach rendered content
            return page_dto

    async def create_page(
        self, data: WikiPageCreate, author_id: str, blueprint_id: Optional[str] = None
    ) -> PageDTO:
        """
        Create a new wiki page with initial revision in DB.
        """
        content = data.content
        if blueprint_id:
            logger.info("Applying blueprint %s to page {data.slug}", blueprint_id)
            content = f"# {data.title}\n\nGenerated from blueprint..."

        page_id = str(uuid.uuid4())
        revision_id = str(uuid.uuid4())

        # Resolve human namespace names to deterministic IDs for offline/local usage.
        try:
            uuid.UUID(data.namespace)
            namespace_id = data.namespace
        except (ValueError, AttributeError):
            namespace_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"wiki:{data.namespace}"))

        async with get_db_connection() as conn:
            async with conn.transaction():
                # 1. Create Page
                await conn.execute(
                    """
                    INSERT INTO wiki_pages (id, namespace_id, slug, title, current_revision_id, version)
                    VALUES ($1, $2, $3, $4, $5, 1)
                """,
                    page_id,
                    namespace_id,
                    data.slug,
                    data.title,
                    revision_id,
                )

                # 2. Create Revision
                await conn.execute(
                    """
                    INSERT INTO wiki_revisions (id, page_id, version, content, commit_message, author_id)
                    VALUES ($1, $2, 1, $3, $4, $5)
                """,
                    revision_id,
                    page_id,
                    content,
                    data.commit_message,
                    author_id,
                )

                if self.qdrant:
                    index_page = getattr(self.qdrant, "index_page", None)
                    if index_page:
                        result = index_page(page_id, data.title, content)
                        if inspect.isawaitable(result):
                            await result
                    else:
                        logger.debug("Wiki semantic index adapter has no index_page method")

        logger.info(f"Created wiki page: {data.title}", extra={"author_id": author_id})

        return PageDTO(
            id=page_id,
            slug=data.slug,
            namespace=data.namespace,
            title=data.title,
            current_revision_id=revision_id,
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    async def update_page(
        self, slug: str, data: WikiPageUpdate, author_id: str
    ) -> PageDTO:
        """
        Update a page with optimistic locking check in DB.
        """
        async with get_db_connection() as conn:
            async with conn.transaction():
                # 1. Get current page
                page = await conn.fetchrow(
                    "SELECT id, version, title FROM wiki_pages WHERE slug = $1 FOR UPDATE",
                    slug,
                )
                if not page:
                    raise ValueError("Page not found")

                # 2. Optimistic Locking
                if page["version"] != data.version:
                    raise ValueError(
                        f"Conflict: Page has been modified (v{page['version']} vs v{data.version})"
                    )

                new_version = page["version"] + 1
                revision_id = str(uuid.uuid4())

                # 3. Create Revision
                await conn.execute(
                    """
                    INSERT INTO wiki_revisions (id, page_id, version, content, commit_message, author_id)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    revision_id,
                    page["id"],
                    new_version,
                    data.content,
                    data.commit_message,
                    author_id,
                )

                # 4. Update Page
                await conn.execute(
                    """
                    UPDATE wiki_pages
                    SET version = $1, current_revision_id = $2, updated_at = NOW()
                    WHERE id = $3
                """,
                    new_version,
                    revision_id,
                    page["id"],
                )

        logger.info("Updated page %s to v{new_version}", slug)

        return PageDTO(
            id=page["id"],
            slug=slug,
            namespace="default",
            title=page["title"],
            current_revision_id=revision_id,
            version=new_version,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    async def list_pages(self, limit: int = 50, offset: int = 0) -> List[PageDTO]:
        """
        List wiki pages with pagination.
        """
        query = """
            SELECT
                id, slug, title, namespace_id, current_revision_id, version, created_at, updated_at
            FROM wiki_pages
            WHERE is_deleted = FALSE
            ORDER BY updated_at DESC
            LIMIT $1 OFFSET $2
        """

        async with get_db_connection() as conn:
            rows = await conn.fetch(query, limit, offset)

            return [
                PageDTO(
                    id=row["id"],
                    slug=row["slug"],
                    namespace=row["namespace_id"] or "default",
                    title=row["title"],
                    current_revision_id=str(row["current_revision_id"] or ""),
                    version=row["version"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    async def render_content(self, markdown: str) -> str:
        """
        Render Markdown to HTML using the rendering engine.
        """
        return self.renderer.render(markdown)

    async def ask_wiki(self, query: str) -> Dict[str, Any]:
        """Answer from local wiki evidence without inventing missing facts."""
        clean_query = " ".join(str(query or "").split())[:500]
        logger.info("Asking Wiki: %s", clean_query)

        if not clean_query:
            return {
                "answer": "Ask Wiki needs a non-empty question before it can search local evidence.",
                "sources": [],
                "evidence": [],
                "mode": "offline-evidence-search",
                "coverage": "no_query",
                "caveats": ["No query text was provided."],
            }

        caveats: list[str] = []
        try:
            evidence = await self._search_local_pages(clean_query, limit=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Wiki evidence search failed: %s", exc)
            evidence = []
            caveats.append(f"Wiki evidence search failed: {exc}")

        if not evidence:
            caveats.append(
                "No local wiki pages matched the question; answer is intentionally not invented."
            )
            return {
                "answer": (
                    "No local wiki evidence was found for this question. "
                    "I will not invent a RAG answer; add or sync a wiki page, then ask again."
                ),
                "sources": [],
                "evidence": [],
                "mode": "offline-evidence-search",
                "coverage": "no_local_evidence",
                "caveats": caveats,
            }

        return {
            "answer": self._build_evidence_answer(clean_query, evidence),
            "sources": [item["source"] for item in evidence],
            "evidence": evidence,
            "mode": "offline-evidence-search",
            "coverage": "local_wiki_evidence",
            "caveats": caveats,
        }

    async def _search_local_pages(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        terms = self._tokens(query)
        if not terms:
            return []

        sql = """
            SELECT p.slug, p.title, p.namespace_id, p.updated_at, r.content
            FROM wiki_pages p
            LEFT JOIN wiki_revisions r ON p.current_revision_id = r.id
            WHERE p.is_deleted = FALSE
            ORDER BY p.updated_at DESC
            LIMIT 200
        """
        async with get_db_connection() as conn:
            rows = await conn.fetch(sql)

        scored: list[dict[str, Any]] = []
        for row in rows:
            content = row["content"] or ""
            haystack = f"{row['title']} {row['slug']} {content}"
            score = self._score_text(terms, haystack)
            if score <= 0:
                continue
            scored.append(
                {
                    "title": row["title"],
                    "slug": row["slug"],
                    "namespace": row["namespace_id"] or "default",
                    "score": score,
                    "snippet": self._snippet(content or row["title"], terms),
                    "source": f"/wiki/pages/{row['slug']}",
                    "updated_at": row["updated_at"].isoformat()
                    if row["updated_at"]
                    else None,
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:limit]

    def _build_evidence_answer(self, query: str, evidence: list[dict[str, Any]]) -> str:
        lead = (
            f"Found {len(evidence)} local wiki source(s) for: {query}. "
            "Use this as an evidence map, not as an invented summary."
        )
        lines = [
            f"- {item['title']}: {item['snippet']} ({item['source']})"
            for item in evidence[:3]
        ]
        return "\n".join([lead, *lines])

    def _tokens(self, text: str) -> set[str]:
        return {token.lower() for token in _WORD_RE.findall(text or "")}

    def _score_text(self, terms: set[str], text: str) -> float:
        haystack = " ".join(_WORD_RE.findall(text or "")).lower()
        if not haystack:
            return 0.0
        matches = sum(1 for term in terms if term in haystack)
        return round(matches / max(len(terms), 1), 3)

    def _snippet(self, content: str, terms: set[str], limit: int = 220) -> str:
        compact = " ".join(str(content or "").split())
        if not compact:
            return ""
        lower = compact.lower()
        first_hit = min((lower.find(term) for term in terms if term in lower), default=0)
        start = max(first_hit - 70, 0)
        snippet = compact[start : start + limit].strip()
        if start > 0:
            snippet = "..." + snippet
        if start + limit < len(compact):
            snippet += "..."
        return snippet
