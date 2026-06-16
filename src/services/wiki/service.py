"""
Wiki Service Implementation
Handles logic for page management, versioning, rendering, and advanced features (Blueprints, AI)
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from src.database import get_db_connection
from src.utils.structured_logging import StructuredLogger

# Import DTOs
from .models import WikiPage as PageDTO
from .models import WikiPageCreate, WikiPageUpdate

# Import Renderer
from .renderer import WikiRenderer

logger = StructuredLogger(__name__).logger


class WikiService:
    """
    Service for managing Wiki pages with versioning, code integration, and AI features.
    """

    def __init__(self, db_session=None):
        self.renderer = WikiRenderer()
        # Stub Qdrant integration for now
        self.qdrant = None

    async def get_page(
        self, slug: str, version: Optional[int] = None
    ) -> Optional[PageDTO]:
        """
        Retrieve a wiki page by slug from DB.
        """
        query = """
            SELECT
                p.id, p.slug, p.title, p.namespace_id, p.version, p.created_at, p.updated_at,
                r.content
            FROM wiki_pages p
            LEFT JOIN wiki_revisions r ON p.current_revision_id = r.id
            WHERE p.slug = $1 AND p.is_deleted = FALSE
        """
        params = [slug]

        if version:
            query = """
                SELECT
                    p.id, p.slug, p.title, p.namespace_id, p.version, p.created_at, p.updated_at,
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
                namespace="default",  # STUB
                title=row["title"],
                current_revision_id="stub",
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

        # If namespace is not a valid UUID (e.g. "default"), treat it as a name or handle properly
        # For now, if it looks like a UUID, use it; otherwise generate a stub ID or lookup.
        try:
            uuid.UUID(data.namespace)
            namespace_id = data.namespace
        except (ValueError, AttributeError):
            # Fallback for legacy/test calls
            namespace_id = str(uuid.uuid4())

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

                # 3. Index in Qdrant (Stub)
                if self.qdrant:
                    # await self.qdrant.index_page(...)
                    logger.debug("Qdrant indexing skipped (not configured)")

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
                id, slug, title, namespace_id, version, created_at, updated_at
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
                    namespace="default",  # Stub
                    title=row["title"],
                    current_revision_id="stub",
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

    async def ask_wiki(self, query: str) -> Dict[str, str]:
        """
        AI RAG Chatbot stub (Ask Wiki).
        """
        logger.info("Asking Wiki: %s", query)
        return {
            "answer": "This is a stub answer from the AI RAG system based on your query.",
            "sources": ["/wiki/pages/architecture-overview", "/wiki/pages/api-docs"],
        }
