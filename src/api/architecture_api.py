"""Architecture review API over the Rentgen module graph."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.rentgen.architecture_review import build_architecture_review

router = APIRouter(prefix="/api/v1/architecture", tags=["Architecture Review"])

_NO_STORE = (
    "Rentgen store not built. Run: python tools/rentgen/build_store.py "
    "(needs data/rentgen_callgraph.ndjson + gabriel_runs/scores.json)."
)


class ArchitectureReviewRequest(BaseModel):
    changed_modules: list[str] = Field(default_factory=list)
    diff: str | None = None
    limit: int = Field(default=5000, ge=100, le=50000)
    min_weight: int = Field(default=1, ge=1, le=10000)
    dense_threshold: int = Field(default=250, ge=10, le=10000)
    include_cycles: bool = True
    finding_limit: int = Field(default=200, ge=1, le=1000)


@router.post("/review")
def review(req: ArchitectureReviewRequest) -> dict[str, Any]:
    """Review architecture boundaries using module-level dependencies."""

    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    return build_architecture_review(
        store,
        changed_modules=req.changed_modules,
        diff=req.diff,
        limit=req.limit,
        min_weight=req.min_weight,
        dense_threshold=req.dense_threshold,
        include_cycles=req.include_cycles,
        finding_limit=req.finding_limit,
    )


@router.get("/health")
def health() -> dict[str, Any]:
    store = store_or_none()
    if store is None:
        return {"status": "store_not_built", "store": False, "hint": _NO_STORE}
    return {"status": "ok", "store": True}
