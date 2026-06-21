"""Lock Radar API for Technology Journal lock evidence."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.rentgen.lock_radar import build_lock_radar

router = APIRouter(prefix="/api/v1/lock-radar", tags=["Lock Radar"])


class LockRadarRequest(BaseModel):
    log_path: str | None = Field(default=None, max_length=2000)
    changed_modules: list[str] = Field(default_factory=list, max_length=200)
    module_limit: int = Field(default=12, ge=1, le=50)
    max_depth: int = Field(default=5, ge=1, le=12)
    max_edges: int = Field(default=300, ge=1, le=5000)


@router.post("/analyze")
def analyze(req: LockRadarRequest) -> dict[str, Any]:
    """Analyze TLOCK, TTIMEOUT and TDEADLOCK events from local Technology Journal logs."""

    try:
        return build_lock_radar(
            store_or_none(),
            log_path=req.log_path,
            changed_modules=req.changed_modules,
            module_limit=req.module_limit,
            max_depth=req.max_depth,
            max_edges=req.max_edges,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/health")
def health() -> dict[str, Any]:
    report = build_lock_radar()
    return {
        "status": report["decision"]["status"],
        "risk_score": report["decision"]["risk_score"],
        "events": report["summary"]["total_events"],
    }
