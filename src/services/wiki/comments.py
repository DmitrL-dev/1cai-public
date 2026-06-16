"""
Wiki Comments Service
Handles adding, retrieving, and managing comments on wiki pages.
"""

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from src.database import get_db_connection
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class CommentDTO(BaseModel):
    id: str
    page_id: str
    author_id: str
    content: str
    created_at: datetime
    resolved: bool
    parent_id: Optional[str] = None
    replies: List["CommentDTO"] = []


class WikiCommentsService:
    """Service for Wiki Comments"""

    async def add_comment(
        self,
        page_id: str,
        author_id: str,
        content: str,
        parent_id: Optional[str] = None,
    ) -> CommentDTO:
        """Add a comment to a page"""
        comment_id = str(uuid.uuid4())
        created_at = datetime.utcnow()

        async with get_db_connection() as conn:
            await conn.execute(
                """
                INSERT INTO wiki_comments (id, page_id, author_id, content, created_at, resolved, parent_id)
                VALUES ($1, $2, $3, $4, $5, FALSE, $6)
            """,
                comment_id,
                page_id,
                author_id,
                content,
                created_at,
                parent_id,
            )

        logger.info("Added comment %s to page {page_id}", comment_id)

        return CommentDTO(
            id=comment_id,
            page_id=page_id,
            author_id=author_id,
            content=content,
            created_at=created_at,
            resolved=False,
            parent_id=parent_id,
        )

    async def get_page_comments(self, page_id: str) -> List[CommentDTO]:
        """Get all comments for a page, organized in threads"""
        async with get_db_connection() as conn:
            rows = await conn.fetch(
                """
                SELECT id, page_id, author_id, content, created_at, resolved, parent_id
                FROM wiki_comments
                WHERE page_id = $1
                ORDER BY created_at ASC
            """,
                page_id,
            )

        # Build tree
        comments_map = {}
        roots = []

        for row in rows:
            comment = CommentDTO(
                id=row["id"],
                page_id=row["page_id"],
                author_id=row["author_id"],
                content=row["content"],
                created_at=row["created_at"],
                resolved=row["resolved"],
                parent_id=row["parent_id"],
            )
            comments_map[comment.id] = comment

            if comment.parent_id:
                parent = comments_map.get(comment.parent_id)
                if parent:
                    parent.replies.append(comment)
            else:
                roots.append(comment)

        return roots

    async def resolve_comment(self, comment_id: str, resolved: bool = True):
        """Mark comment thread as resolved"""
        async with get_db_connection() as conn:
            await conn.execute(
                "UPDATE wiki_comments SET resolved = $1 WHERE id = $2",
                resolved,
                comment_id,
            )
