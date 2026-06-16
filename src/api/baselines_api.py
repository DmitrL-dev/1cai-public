"""Baselines and review packs API for internal ALM governance."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.rentgen.baselines import (
    add_review_comment,
    create_baseline,
    create_review_pack,
    decide_review_pack,
    get_baseline,
    get_review_pack,
    list_baselines,
    list_review_packs,
)


router = APIRouter(prefix="/api/v1", tags=["Baselines"])


class BaselineRequest(BaseModel):
    id: str | None = Field(default=None, max_length=120)
    title: str = Field(..., min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    owner: str | None = Field(default=None, max_length=160)
    artifact_ids: list[str] = Field(default_factory=list)
    release_id: str | None = Field(default=None, max_length=160)
    change_set_ids: list[str] = Field(default_factory=list)


class ReviewPackRequest(BaseModel):
    id: str | None = Field(default=None, max_length=120)
    title: str = Field(..., min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=4000)
    owner: str | None = Field(default=None, max_length=160)
    artifact_ids: list[str] = Field(default_factory=list)
    reviewers: list[str] = Field(default_factory=list)


class ReviewCommentRequest(BaseModel):
    actor: str = Field(default="system", max_length=160)
    message: str = Field(..., min_length=1, max_length=2000)
    artifact_id: str | None = Field(default=None, max_length=160)


class ReviewDecisionRequest(BaseModel):
    actor: str = Field(default="system", max_length=160)
    reason: str | None = Field(default=None, max_length=1000)


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(404, str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(400, str(exc))
    return HTTPException(500, str(exc))


@router.post("/baselines")
def create_baseline_endpoint(req: BaselineRequest) -> dict[str, Any]:
    """Create an immutable baseline snapshot."""

    try:
        return create_baseline(
            baseline_id=req.id,
            title=req.title,
            description=req.description,
            owner=req.owner,
            artifact_ids=req.artifact_ids,
            release_id=req.release_id,
            change_set_ids=req.change_set_ids,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/baselines")
def baselines(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    """List baselines."""

    return list_baselines(limit=limit)


@router.get("/baselines/{baseline_id}")
def baseline_details(baseline_id: str) -> dict[str, Any]:
    """Return one baseline."""

    item = get_baseline(baseline_id)
    if item is None:
        raise HTTPException(404, f"Baseline not found: {baseline_id}")
    return item


@router.post("/review-packs")
def create_review_pack_endpoint(req: ReviewPackRequest) -> dict[str, Any]:
    """Create a review pack with a fixed artifact set."""

    try:
        return create_review_pack(
            review_pack_id=req.id,
            title=req.title,
            description=req.description,
            owner=req.owner,
            artifact_ids=req.artifact_ids,
            reviewers=req.reviewers,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.get("/review-packs")
def review_packs(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """List review packs."""

    return list_review_packs(status=status, limit=limit)


@router.get("/review-packs/{review_pack_id}")
def review_pack_details(review_pack_id: str) -> dict[str, Any]:
    """Return one review pack."""

    item = get_review_pack(review_pack_id)
    if item is None:
        raise HTTPException(404, f"Review pack not found: {review_pack_id}")
    return item


@router.post("/review-packs/{review_pack_id}/comment")
def add_comment(review_pack_id: str, req: ReviewCommentRequest) -> dict[str, Any]:
    """Append a review-pack comment."""

    try:
        return add_review_comment(
            review_pack_id,
            actor=req.actor,
            message=req.message,
            artifact_id=req.artifact_id,
        )
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/review-packs/{review_pack_id}/approve")
def approve_review_pack(review_pack_id: str, req: ReviewDecisionRequest) -> dict[str, Any]:
    """Approve a review pack."""

    try:
        return decide_review_pack(review_pack_id, actor=req.actor, decision="approved", reason=req.reason)
    except Exception as exc:
        raise _handle_error(exc) from exc


@router.post("/review-packs/{review_pack_id}/reject")
def reject_review_pack(review_pack_id: str, req: ReviewDecisionRequest) -> dict[str, Any]:
    """Reject a review pack."""

    try:
        return decide_review_pack(review_pack_id, actor=req.actor, decision="rejected", reason=req.reason)
    except Exception as exc:
        raise _handle_error(exc) from exc
