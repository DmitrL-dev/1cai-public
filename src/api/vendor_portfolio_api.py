"""Vendor Portfolio API for pre-sale and franchisee audit packs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.api.copilot_coverage_api import COVERAGE_ITEMS
from src.services.rentgen.buyer_brief import build_buyer_brief
from src.services.rentgen.buyer_pulse import build_buyer_pulse
from src.services.rentgen.executive_dashboard import build_executive_dashboard
from src.services.rentgen.intake_wizard import build_intake_plan
from src.services.rentgen.platform_doctor import build_platform_doctor
from src.services.rentgen.vendor_portfolio import (
    build_vendor_portfolio,
    build_vendor_portfolio_book,
)

router = APIRouter(prefix="/api/v1/vendor-portfolio", tags=["Vendor Portfolio"])


class PortfolioClientRequest(BaseModel):
    name: str = Field(default="Client", min_length=1, max_length=200)
    config_path: str | None = Field(default=None, max_length=2000)
    target_platform_version: str | None = Field(default=None, max_length=80)


class PortfolioRequest(BaseModel):
    portfolio_name: str = Field(
        default="Vendor portfolio", min_length=1, max_length=200
    )
    clients: list[PortfolioClientRequest] = Field(default_factory=list, max_length=50)
    governance_limit: int = Field(default=40, ge=1, le=200)
    hotspot_limit: int = Field(default=12, ge=1, le=50)


@router.get("/audit")
def audit(
    client_name: str = Query("Demo client", min_length=1, max_length=200),
    config_path: str | None = Query(default=None, max_length=2000),
    target_platform_version: str | None = Query(default=None, max_length=80),
    governance_limit: int = Query(40, ge=1, le=200),
    hotspot_limit: int = Query(12, ge=1, le=50),
) -> dict[str, Any]:
    """Build a local pre-sale audit pack from delivery, source and platform signals."""

    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=governance_limit,
        hotspot_limit=hotspot_limit,
        save_snapshot=False,
    )
    platform = build_platform_doctor(
        config_path=config_path,
        target_platform_version=target_platform_version,
    )
    intake = build_intake_plan(source_path=config_path, source_type="auto")
    buyer_brief = build_buyer_brief(executive=executive)
    return build_vendor_portfolio(
        executive=executive,
        platform=platform,
        intake=intake,
        buyer_brief=buyer_brief,
        client_name=client_name,
    )


@router.post("/portfolio")
def portfolio(req: PortfolioRequest) -> dict[str, Any]:
    """Build a multi-client vendor/franchisee portfolio from local audit signals."""

    store = store_or_none()
    executive = build_executive_dashboard(
        store,
        coverage_items=COVERAGE_ITEMS,
        governance_limit=req.governance_limit,
        hotspot_limit=req.hotspot_limit,
        save_snapshot=False,
    )
    buyer_brief = build_buyer_brief(executive=executive)
    audits: list[dict[str, Any]] = []
    clients = req.clients or [PortfolioClientRequest(name="Demo client")]
    for client in clients:
        platform = build_platform_doctor(
            config_path=client.config_path,
            target_platform_version=client.target_platform_version,
        )
        intake = build_intake_plan(source_path=client.config_path, source_type="auto")
        audit_report = build_vendor_portfolio(
            executive=executive,
            platform=platform,
            intake=intake,
            buyer_brief=buyer_brief,
            client_name=client.name,
        )
        audits.append(audit_report)
    return build_vendor_portfolio_book(
        audits=audits,
        portfolio_name=req.portfolio_name,
    )


@router.get("/health")
def health() -> dict[str, Any]:
    """Small fast payload for dashboards and load balancers."""

    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=10,
        hotspot_limit=5,
        save_snapshot=False,
    )
    pulse = build_buyer_pulse(executive=executive)
    return {
        "status": pulse["status"],
        "score": pulse["score"],
        "work_packages": 4,
        "portfolio_segments": 3,
        "purchase_status": pulse["purchase_status"],
        "three_year_ai_rent": pulse["commercial"]["three_year_ai_rent"],
        "source": pulse["source"],
    }
