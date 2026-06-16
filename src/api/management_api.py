"""Management cockpit API for executive 1C delivery control."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from src.api._rentgen_store import store_or_none
from src.api.copilot_coverage_api import COVERAGE_ITEMS
from src.services.rentgen.executive_dashboard import build_executive_dashboard

router = APIRouter(prefix="/api/v1/management", tags=["Management"])


@router.get("/executive")
def executive_dashboard(
    governance_limit: int = Query(40, ge=1, le=200),
    hotspot_limit: int = Query(12, ge=1, le=50),
    save_snapshot: bool = Query(False),
) -> dict[str, Any]:
    """Return the internal executive cockpit for managers and delivery leads."""

    return build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=governance_limit,
        hotspot_limit=hotspot_limit,
        save_snapshot=save_snapshot,
    )


@router.get("/health")
def health() -> dict[str, Any]:
    store = store_or_none()
    return {"status": "ok" if store is not None else "store_not_built", "store": store is not None}
