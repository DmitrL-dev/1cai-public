"""Release-readiness API for enterprise 1C delivery governance."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.rentgen.release_readiness import build_release_readiness

router = APIRouter(prefix="/api/v1/release-readiness", tags=["Release Readiness"])

_NO_STORE = (
    "Rentgen store not built. Run: python tools/rentgen/build_store.py "
    "(needs data/rentgen_callgraph.ndjson + gabriel_runs/scores.json)."
)


class ReleaseReadinessRequest(BaseModel):
    release_name: str | None = Field(default=None, max_length=160)
    changed_modules: list[str] = Field(default_factory=list)
    diff: str | None = None
    snapshot_id: str | None = Field(default=None, max_length=260)
    include_security: bool = False
    include_forms: bool = True
    form_object_limit: int = Field(default=4, ge=0, le=20)
    security_limit: int = Field(default=100, ge=1, le=1000)
    max_depth: int = Field(default=5, ge=1, le=10)
    max_edges: int = Field(default=600, ge=1, le=2000)
    hotspot_limit: int = Field(default=10, ge=1, le=100)
    risk_threshold: int = Field(default=70, ge=0, le=100)
    impact_threshold: int = Field(default=300, ge=0, le=5000)
    fail_on_high: bool = True


@router.post("/analyze")
def analyze_release(req: ReleaseReadinessRequest) -> dict[str, Any]:
    """Analyze a release candidate: diff/modules -> decision, risks, tests and actions."""

    store = store_or_none()
    if store is None:
        raise HTTPException(503, _NO_STORE)

    try:
        return build_release_readiness(
            store,
            changed_modules=req.changed_modules,
            diff=req.diff,
            release_name=req.release_name,
            snapshot_id=req.snapshot_id,
            include_security=req.include_security,
            include_forms=req.include_forms,
            form_object_limit=req.form_object_limit,
            security_limit=req.security_limit,
            max_depth=req.max_depth,
            max_edges=req.max_edges,
            hotspot_limit=req.hotspot_limit,
            risk_threshold=req.risk_threshold,
            impact_threshold=req.impact_threshold,
            fail_on_high=req.fail_on_high,
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/health")
def health() -> dict[str, Any]:
    store = store_or_none()
    if store is None:
        return {"status": "store_not_built", "store": False, "hint": _NO_STORE}
    return {"status": "ok", "store": True}
