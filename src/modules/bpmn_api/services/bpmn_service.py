from typing import Any, Dict, List

import asyncpg

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class BPMNService:
    """Service for BPMN diagram management."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool

    async def list_diagrams(self, project_id: str | None = None) -> List[Dict[str, Any]]:
        """List all BPMN diagrams."""
        async with self.db.acquire() as conn:
            tenant_id = await conn.fetchval("SELECT id FROM tenants LIMIT 1")

            if not tenant_id:
                return []

            if project_id:
                diagrams = await conn.fetch(
                    """
                    SELECT id, name, description, created_at, updated_at
                    FROM bpmn_diagrams
                    WHERE tenant_id = $1 AND project_id = $2
                    ORDER BY updated_at DESC
                    """,
                    tenant_id,
                    project_id,
                )
            else:
                diagrams = await conn.fetch(
                    """
                    SELECT id, name, description, created_at, updated_at
                    FROM bpmn_diagrams
                    WHERE tenant_id = $1
                    ORDER BY updated_at DESC
                    LIMIT 50
                    """,
                    tenant_id,
                )

            return [
                {
                    "id": str(row["id"]),
                    "name": row["name"],
                    "description": row["description"],
                    "created_at": row["created_at"].isoformat(),
                    "updated_at": row["updated_at"].isoformat(),
                }
                for row in diagrams
            ]

    async def get_diagram(self, diagram_id: str) -> Dict[str, Any] | None:
        """Get specific BPMN diagram."""
        async with self.db.acquire() as conn:
            diagram = await conn.fetchrow(
                """
                SELECT id, name, description, xml_content, project_id, created_at, updated_at
                FROM bpmn_diagrams
                WHERE id = $1
                """,
                diagram_id,
            )

            if not diagram:
                return None

            return {
                "id": str(diagram["id"]),
                "name": diagram["name"],
                "description": diagram["description"],
                "xml": diagram["xml_content"],
                "project_id": (str(diagram["project_id"]) if diagram["project_id"] else None),
                "created_at": diagram["created_at"].isoformat(),
                "updated_at": diagram["updated_at"].isoformat(),
            }

    async def save_diagram(self, name: str, description: str, xml: str, project_id: str | None = None) -> str:
        """Save new BPMN diagram."""
        async with self.db.acquire() as conn:
            tenant_id = await conn.fetchval("SELECT id FROM tenants LIMIT 1")

            if not tenant_id:
                raise ValueError("No tenant found")

            diagram_id = await conn.fetchval(
                """
                INSERT INTO bpmn_diagrams
                (tenant_id, name, description, xml_content, project_id, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
                RETURNING id
                """,
                tenant_id,
                name,
                description,
                xml,
                project_id,
            )

            logger.info("Saved BPMN diagram", extra={"diagram_id": str(diagram_id)})
            return str(diagram_id)

    async def update_diagram(self, diagram_id: str, name: str, description: str, xml: str) -> bool:
        """Update existing BPMN diagram."""
        async with self.db.acquire() as conn:
            updated = await conn.execute(
                """
                UPDATE bpmn_diagrams
                SET name = $1,
                    description = $2,
                    xml_content = $3,
                    updated_at = NOW()
                WHERE id = $4
                """,
                name,
                description,
                xml,
                diagram_id,
            )

            return updated != "UPDATE 0"

    async def delete_diagram(self, diagram_id: str) -> bool:
        """Delete BPMN diagram."""
        async with self.db.acquire() as conn:
            deleted = await conn.execute("DELETE FROM bpmn_diagrams WHERE id = $1", diagram_id)

            return deleted != "DELETE 0"
