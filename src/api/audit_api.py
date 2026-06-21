"""Product audit log API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.middleware.jwt_user_context import principal_actor, require_auth
from src.services.audit_log import (
    export_events,
    export_siem_events,
    list_events,
    record_event,
    verify_chain,
)


router = APIRouter(prefix="/api/v1/audit", tags=["Audit"])


class AuditEventRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=200)
    target: str | None = Field(default=None, max_length=300)
    category: str = Field(default="governance", max_length=80)
    outcome: str = Field(default="success", max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=160)


@router.get("/events")
def events(
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    category: str | None = Query(default=None),
    target: str | None = Query(default=None),
    since: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict[str, Any]:
    """List product audit events newest first."""

    return list_events(actor=actor, action=action, category=category, target=target, since=since, limit=limit)


@router.get("/export")
def export(format: str = Query(default="jsonl", pattern="^(jsonl|json)$")) -> dict[str, Any]:
    """Export product audit log content."""

    try:
        return export_events(output_format=format)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/siem-export")
def siem_export(
    format: str = Query(default="jsonl", pattern="^(jsonl|json)$"),
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict[str, Any]:
    """Export SIEM-ready audit events with hash-chain verification context."""

    try:
        return export_siem_events(output_format=format, limit=limit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/verify")
def verify() -> dict[str, Any]:
    """Verify the audit log hash-chain and report any tampering."""

    return verify_chain()


@router.post("/events")
def create_event(
    req: AuditEventRequest,
    principal: Any = Depends(require_auth),
) -> dict[str, Any]:
    """Append an explicit product audit event for integrations.

    The ``actor`` is taken from the authenticated principal — it can NOT be
    spoofed via the request body.
    """

    actor = principal_actor(principal)
    if not actor:
        raise HTTPException(401, "Not authenticated")
    return record_event(actor=actor, **req.model_dump())
