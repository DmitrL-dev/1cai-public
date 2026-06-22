"""Internal approval workflow API for privileged delivery actions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.middleware.jwt_user_context import principal_actor, require_auth
from src.services.audit_log import record_event
from src.services.edt_mcp_bridge import classify_edt_mcp_tool
from src.services.rentgen.approval_workflow import (
    create_approval_record,
    get_approval_record,
    list_approval_records,
    update_approval_status,
    validate_approval_for_call,
)

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])


class EdtMcpApprovalRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=200)
    approval_reason: str = Field(..., min_length=12, max_length=1000)
    approval_ticket: str | None = Field(default=None, max_length=160)
    linked_record_type: str | None = Field(default=None, max_length=80)
    linked_record_id: str | None = Field(default=None, max_length=200)
    argument_constraints: dict[str, Any] = Field(default_factory=dict)
    expires_in_hours: float = Field(default=24, ge=1, le=24 * 30)


class ApprovalDecisionRequest(BaseModel):
    decision_reason: str | None = Field(default=None, max_length=1000)


class ApprovalValidationRequest(BaseModel):
    approval_id: str = Field(..., min_length=1, max_length=80)
    tool_name: str = Field(..., min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)


def _require_actor(principal: Any) -> str:
    """Return the authenticated actor identity or raise 401."""
    actor = principal_actor(principal)
    if not actor:
        raise HTTPException(401, "Not authenticated")
    return actor


def _audit_approval(action: str, *, actor: str, record: dict[str, Any]) -> None:
    record_event(
        action=action,
        actor=actor,
        target=str(record.get("id") or ""),
        category="approval",
        metadata={
            "tool_name": record.get("tool_name"),
            "risk": record.get("risk"),
            "status": record.get("status"),
            "requested_by": record.get("requested_by"),
            "approved_by": record.get("approved_by"),
            "linked_record": record.get("linked_record") or {},
            "argument_constraints": record.get("argument_constraints") or {},
        },
    )


@router.post("/edt-mcp")
async def create_edt_mcp_approval(
    req: EdtMcpApprovalRequest,
    principal: Any = Depends(require_auth),
) -> dict[str, Any]:
    """Create a requested approval record for a future EDT-MCP risky call."""

    classification = classify_edt_mcp_tool(req.tool_name)
    actor = _require_actor(principal)
    record = create_approval_record(
        tool_name=req.tool_name,
        actor=actor,
        approval_reason=req.approval_reason,
        risk=str(classification.get("risk") or "unknown"),
        approval_ticket=req.approval_ticket,
        requested_by=actor,
        linked_record_type=req.linked_record_type,
        linked_record_id=req.linked_record_id,
        argument_constraints=req.argument_constraints,
        expires_in_hours=req.expires_in_hours,
    )
    _audit_approval("approval.requested", actor=actor, record=record)
    return {"record": record, "classification": classification}


@router.post("/{approval_id}/approve")
async def approve_record(
    approval_id: str,
    req: ApprovalDecisionRequest,
    principal: Any = Depends(require_auth),
) -> dict[str, Any]:
    """Approve an internal approval record."""

    actor = _require_actor(principal)
    try:
        record = update_approval_status(
            approval_id,
            status="approved",
            actor=actor,
            decision_reason=req.decision_reason,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    _audit_approval("approval.approved", actor=actor, record=record)
    return {"record": record}


@router.post("/{approval_id}/reject")
async def reject_record(
    approval_id: str,
    req: ApprovalDecisionRequest,
    principal: Any = Depends(require_auth),
) -> dict[str, Any]:
    """Reject an internal approval record."""

    actor = _require_actor(principal)
    try:
        record = update_approval_status(
            approval_id,
            status="rejected",
            actor=actor,
            decision_reason=req.decision_reason,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    _audit_approval("approval.rejected", actor=actor, record=record)
    return {"record": record}


@router.post("/edt-mcp/validate")
def validate_edt_mcp_approval(
    req: ApprovalValidationRequest,
    principal: Any = Depends(require_auth),
) -> dict[str, Any]:
    """Validate an approval record against an EDT-MCP tool call."""

    actor = _require_actor(principal)
    classification = classify_edt_mcp_tool(req.tool_name)
    validation = validate_approval_for_call(
        req.approval_id,
        tool_name=req.tool_name,
        actor=actor,
        risk=str(classification.get("risk") or "unknown"),
        arguments=req.arguments,
    )
    return {"classification": classification, **validation}


@router.get("")
def approvals(
    status: str | None = Query(default=None, max_length=40),
    kind: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """List internal approval records."""

    return list_approval_records(status=status, kind=kind, limit=limit)


@router.get("/health/status")
def health() -> dict[str, Any]:
    return {"status": "ok", "store": "data/approval_records.json"}


@router.get("/{approval_id}")
def approval_details(approval_id: str) -> dict[str, Any]:
    """Return one approval record."""

    record = get_approval_record(approval_id)
    if not record:
        raise HTTPException(404, f"Approval record not found: {approval_id}")
    return record
