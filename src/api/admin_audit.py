
"""Admin endpoints for viewing security audit log."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from src.security import CurrentUser, require_roles

router = APIRouter(prefix="/admin/audit", tags=["admin", "audit"])


class AuditEntry(BaseModel):
    id: int
    timestamp: str
    actor: str
    action: str
    target: Optional[str]
    metadata: dict


class AuditLogResponse(BaseModel):
    items: list[AuditEntry]
    total: int
    limit: int
    offset: int


async def _fetch_audit_entries(
    limit: int,
    offset: int,
    actor: Optional[str],
    action: Optional[str],
) -> tuple[list[AuditEntry], int]:
    try:
        from src.database import get_pool

        pool = get_pool()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not available",
        ) from exc

    filters = []
    values = []
    if actor:
        values.append(actor)
        filters.append(f"actor = ${len(values)}")
    if action:
        values.append(action)
        filters.append(f"action = ${len(values)}")

    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    query = f"""
        SELECT id, timestamp, actor, action, target, metadata
        FROM security_audit_log
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ${len(values) + 1}
        OFFSET ${len(values) + 2}
    """
    count_query = f"""
        SELECT COUNT(*) AS total
        FROM security_audit_log
        {where_clause}
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *(values + [limit, offset]))
        total = await conn.fetchval(count_query, *values)

    items = [
        AuditEntry(
            id=row["id"],
            timestamp=row["timestamp"].isoformat(),
            actor=row["actor"],
            action=row["action"],
            target=row["target"],
            metadata=row["metadata"] or {},
        )
        for row in rows
    ]

    return items, total


@router.get("", response_model=AuditLogResponse)
async def list_audit_entries(
    current_user: CurrentUser = Depends(require_roles("admin")),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    actor: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
) -> AuditLogResponse:
    items, total = await _fetch_audit_entries(limit, offset, actor, action)
    return AuditLogResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
