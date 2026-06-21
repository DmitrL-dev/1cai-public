"""Value Packs API for product packaging and buyer-facing outcomes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from src.api._rentgen_store import store_or_none
from src.api.copilot_coverage_api import COVERAGE_ITEMS
from src.services.rentgen.buyer_brief import build_buyer_brief
from src.services.rentgen.executive_dashboard import build_executive_dashboard
from src.services.rentgen.value_packs import build_value_packs

router = APIRouter(prefix="/api/v1/value-packs", tags=["Value Packs"])


@router.get("/catalog")
def catalog() -> dict[str, Any]:
    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=40,
        hotspot_limit=12,
        save_snapshot=False,
    )
    buyer_brief = build_buyer_brief(executive=executive)
    return build_value_packs(executive, buyer_brief=buyer_brief)


@router.get("/health")
def health() -> dict[str, Any]:
    """Liveness only — real numbers are served by /catalog."""

    return {"status": "ok", "service": "value-packs"}
