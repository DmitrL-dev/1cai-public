"""Team governance board over Rentgen quality and ownership signals."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from src.api._rentgen_store import store_or_none
from src.services.rentgen.team_governance import build_team_governance

router = APIRouter(prefix="/api/v1/team-governance", tags=["Team Governance"])


@router.get("/board")
def board(
    limit: int = Query(40, ge=1, le=200),
    save_snapshot: bool = Query(False),
) -> dict[str, Any]:
    return build_team_governance(store_or_none(), limit=limit, save_snapshot=save_snapshot)


@router.post("/snapshots")
def create_snapshot(limit: int = Query(40, ge=1, le=200)) -> dict[str, Any]:
    report = build_team_governance(store_or_none(), limit=limit, save_snapshot=True)
    return {
        "stored_snapshot": report.get("stored_snapshot"),
        "summary": report.get("summary", {}),
        "trend": report.get("trend", {}),
    }
