"""Internal change-set workflow API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.middleware.jwt_user_context import principal_actor, require_auth
from src.services.rentgen.change_sets import (
    add_decision,
    analyze_change_set,
    attach_release_readiness,
    create_change_set,
    get_change_set,
    list_change_sets,
    select_change_set_tests,
    transition_change_set,
)

router = APIRouter(prefix="/api/v1/change-sets", tags=["Change Sets"])

_NO_STORE = (
    "Rentgen store not built. Run: python tools/rentgen/build_store.py "
    "(needs data/rentgen_callgraph.ndjson + gabriel_runs/scores.json)."
)


class ChangeSetRequest(BaseModel):
    id: str | None = Field(default=None, max_length=120)
    title: str = Field(..., min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    source_requirement_ids: list[str] = Field(default_factory=list)
    changed_modules: list[str] = Field(default_factory=list)
    diff: str | None = None


class TransitionRequest(BaseModel):
    status: str = Field(..., min_length=1, max_length=80)
    reason: str | None = Field(default=None, max_length=1000)
    allow_policy_failure: bool = False


class DecisionRequest(BaseModel):
    decision: str = Field(..., min_length=1, max_length=160)
    reason: str | None = Field(default=None, max_length=1000)


class AnalyzeRequest(BaseModel):
    max_depth: int = Field(default=5, ge=1, le=12)
    max_edges: int = Field(default=600, ge=1, le=5000)
    hotspot_limit: int = Field(default=10, ge=1, le=100)


class TestSelectionRequest(AnalyzeRequest):
    match_limit: int = Field(default=10, ge=1, le=100)


class ReleaseReadinessRequest(BaseModel):
    include_security: bool = False
    include_forms: bool = True


def _store_or_503():
    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)
    return store


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(404, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(500, str(exc))


# Change-set lifecycle transitions that constitute an approval / promotion /
# sign-off. For these the acting principal must differ from the change set's
# author (owner) so attribution cannot be forged to bypass separation of duties.
_SOD_TRANSITIONS = {"approved", "merged", "released"}


def _enforce_sod(record: dict[str, Any] | None, actor: str | None) -> None:
    """Block self-approval: the approver must differ from the author (owner).

    Raises ``PermissionError`` (mapped to 403 by ``_handle_error``) mirroring
    the domain-layer separation-of-duties checks in ``policy_engine`` /
    ``approval_workflow``.
    """

    owner = str((record or {}).get("owner") or "").strip()
    if actor and owner and actor == owner:
        raise PermissionError("separation of duties: approver must differ from author")


@router.post("")
def create(req: ChangeSetRequest, principal=Depends(require_auth)) -> dict[str, Any]:
    """Create an internal change set (owner = authenticated principal)."""

    try:
        payload = req.model_dump(exclude_none=True)
        payload["owner"] = principal_actor(principal)
        return create_change_set(payload)
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("")
def list_items(
    status: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """List change sets."""

    return list_change_sets(status=status, owner=owner, limit=limit)


@router.get("/{change_set_id}")
def details(change_set_id: str) -> dict[str, Any]:
    """Return one change set."""

    item = get_change_set(change_set_id)
    if item is None:
        raise HTTPException(404, f"Change set not found: {change_set_id}")
    return item


@router.post("/{change_set_id}/transition")
def transition(
    change_set_id: str, req: TransitionRequest, principal=Depends(require_auth)
) -> dict[str, Any]:
    """Move a change set through its lifecycle (actor = authenticated principal)."""

    actor = principal_actor(principal)
    try:
        if req.status in _SOD_TRANSITIONS:
            _enforce_sod(get_change_set(change_set_id), actor)
        return transition_change_set(
            change_set_id,
            status=req.status,
            actor=actor,
            reason=req.reason,
            allow_policy_failure=req.allow_policy_failure,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/{change_set_id}/decision")
def decision(
    change_set_id: str, req: DecisionRequest, principal=Depends(require_auth)
) -> dict[str, Any]:
    """Append a decision-log entry (actor = authenticated principal)."""

    try:
        return add_decision(
            change_set_id,
            actor=principal_actor(principal),
            decision=req.decision,
            reason=req.reason,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/{change_set_id}/analyze")
def analyze(change_set_id: str, req: AnalyzeRequest) -> dict[str, Any]:
    """Attach Rentgen impact analysis to a change set."""

    try:
        return analyze_change_set(
            _store_or_503(),
            change_set_id,
            max_depth=req.max_depth,
            max_edges=req.max_edges,
            hotspot_limit=req.hotspot_limit,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/{change_set_id}/select-tests")
def select_tests(change_set_id: str, req: TestSelectionRequest) -> dict[str, Any]:
    """Attach risk-driven test coverage matrix to a change set."""

    try:
        return select_change_set_tests(
            _store_or_503(),
            change_set_id,
            max_depth=req.max_depth,
            max_edges=req.max_edges,
            hotspot_limit=req.hotspot_limit,
            match_limit=req.match_limit,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/{change_set_id}/release-readiness")
def release_readiness(
    change_set_id: str, req: ReleaseReadinessRequest
) -> dict[str, Any]:
    """Attach release-readiness report to a change set."""

    try:
        return attach_release_readiness(
            _store_or_503(),
            change_set_id,
            include_security=req.include_security,
            include_forms=req.include_forms,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc
