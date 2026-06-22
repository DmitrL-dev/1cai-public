"""Agentic workflow guardrail API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.middleware.jwt_user_context import principal_actor, require_auth
from src.services.rentgen.agentic_workflows import (
    action_gate,
    create_agentic_plan,
    get_agentic_plan,
    list_agentic_plans,
    review_agentic_plan,
    transition_step,
)

router = APIRouter(prefix="/api/v1/agentic", tags=["Agentic Workflows"])


class PlanRequest(BaseModel):
    id: str | None = Field(default=None, max_length=120)
    title: str = Field(..., min_length=1, max_length=240)
    objective: str | None = Field(default=None, max_length=4000)
    mode: str = Field(default="plan", max_length=40)
    status: str = Field(default="draft", max_length=40)
    change_set_id: str | None = Field(default=None, max_length=160)
    source_artifact_ids: list[str] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)


class StepTransitionRequest(BaseModel):
    step_id: str = Field(..., min_length=1, max_length=80)
    status: str = Field(..., min_length=1, max_length=40)
    note: str | None = Field(default=None, max_length=1000)


class ActionGateRequest(BaseModel):
    action_type: str = Field(..., min_length=1, max_length=80)
    plan_id: str | None = Field(default=None, max_length=160)
    change_set_id: str | None = Field(default=None, max_length=160)
    risk: str = Field(default="low", max_length=40)
    confirm: bool = False


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(404, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(500, str(exc))


def _enforce_sod(record: dict[str, Any] | None, actor: str | None) -> None:
    """Block self-review: the reviewer must differ from the plan author (actor).

    Raises ``PermissionError`` (mapped to 403 by ``_handle_error``) mirroring
    the domain-layer separation-of-duties checks in ``policy_engine`` /
    ``approval_workflow``.
    """

    author = str((record or {}).get("actor") or "").strip()
    if actor and author and actor == author:
        raise PermissionError("separation of duties: approver must differ from author")


@router.post("/plans")
def create_plan(req: PlanRequest, principal=Depends(require_auth)) -> dict[str, Any]:
    """Create an agentic plan (author actor = authenticated principal)."""

    try:
        payload = req.model_dump(exclude_none=True)
        payload["actor"] = principal_actor(principal)
        return create_agentic_plan(payload)
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/plans")
def plans(
    status: str | None = Query(default=None),
    mode: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    return list_agentic_plans(status=status, mode=mode, limit=limit)


@router.get("/plans/{plan_id}")
def plan_details(plan_id: str) -> dict[str, Any]:
    item = get_agentic_plan(plan_id)
    if item is None:
        raise HTTPException(404, f"Agentic plan not found: {plan_id}")
    return item


@router.post("/plans/{plan_id}/steps")
def transition_plan_step(
    plan_id: str, req: StepTransitionRequest, principal=Depends(require_auth)
) -> dict[str, Any]:
    """Transition a plan step (actor = authenticated principal)."""

    try:
        return transition_step(
            plan_id,
            step_id=req.step_id,
            status=req.status,
            actor=principal_actor(principal),
            note=req.note,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/plans/{plan_id}/review")
def review_plan(plan_id: str, principal=Depends(require_auth)) -> dict[str, Any]:
    """Review a plan (reviewer = principal; self-review blocked by SoD)."""

    try:
        _enforce_sod(get_agentic_plan(plan_id), principal_actor(principal))
        return review_agentic_plan(plan_id)
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/action-gate")
def gate(req: ActionGateRequest) -> dict[str, Any]:
    return action_gate(**req.model_dump())
