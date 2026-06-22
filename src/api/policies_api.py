"""Policy and gate evaluation API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.middleware.jwt_user_context import principal_actor, require_auth
from src.services.rentgen.policy_engine import (
    create_waiver,
    decide_waiver,
    evaluate_policy,
    get_evaluation,
    list_evaluations,
    list_waivers,
    load_policy,
)

router = APIRouter(prefix="/api/v1/policies", tags=["Policies"])


class PolicyEvaluationRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)
    domain: str | None = Field(default=None, max_length=80)
    scope_id: str | None = Field(default=None, max_length=160)
    persist: bool = True


class WaiverRequest(BaseModel):
    rule_id: str = Field(..., min_length=1, max_length=160)
    scope_id: str | None = Field(default=None, max_length=160)
    reason: str = Field(..., min_length=8, max_length=1000)
    expires_in_days: int = Field(default=30, ge=1, le=365)
    remediation: str | None = Field(default=None, max_length=1000)


class WaiverDecisionRequest(BaseModel):
    decision_reason: str | None = Field(default=None, max_length=1000)


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(404, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(500, str(exc))


@router.get("")
def policy() -> dict[str, Any]:
    """Return active default policy."""

    return load_policy()


@router.post("/evaluate")
def evaluate(req: PolicyEvaluationRequest) -> dict[str, Any]:
    """Evaluate policy rules against a workflow context."""

    try:
        return evaluate_policy(
            req.context, domain=req.domain, scope_id=req.scope_id, persist=req.persist
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/evaluations")
def evaluations(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    """List stored policy evaluations."""

    return list_evaluations(limit=limit)


@router.get("/evaluations/{evaluation_id}")
def evaluation_details(evaluation_id: str) -> dict[str, Any]:
    """Return one stored policy evaluation."""

    item = get_evaluation(evaluation_id)
    if item is None:
        raise HTTPException(404, f"Policy evaluation not found: {evaluation_id}")
    return item


@router.post("/waivers")
def request_waiver(
    req: WaiverRequest, principal=Depends(require_auth)
) -> dict[str, Any]:
    """Request a policy waiver (owner = authenticated principal, not request body)."""

    try:
        return create_waiver(
            rule_id=req.rule_id,
            scope_id=req.scope_id,
            reason=req.reason,
            owner=principal_actor(principal),
            expires_in_days=req.expires_in_days,
            remediation=req.remediation,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/waivers")
def waivers(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """List policy waivers."""

    return list_waivers(status=status, limit=limit)


@router.post("/waivers/{waiver_id}/approve")
def approve_waiver(
    waiver_id: str, req: WaiverDecisionRequest, principal=Depends(require_auth)
) -> dict[str, Any]:
    """Approve a policy waiver (actor = principal; self-approval blocked by engine)."""

    try:
        return decide_waiver(
            waiver_id,
            status="approved",
            actor=principal_actor(principal),
            decision_reason=req.decision_reason,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/waivers/{waiver_id}/reject")
def reject_waiver(
    waiver_id: str, req: WaiverDecisionRequest, principal=Depends(require_auth)
) -> dict[str, Any]:
    """Reject a policy waiver (actor = authenticated principal)."""

    try:
        return decide_waiver(
            waiver_id,
            status="rejected",
            actor=principal_actor(principal),
            decision_reason=req.decision_reason,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc
