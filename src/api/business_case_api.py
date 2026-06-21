"""Business Case API for director-level value and deal room reports."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.api.copilot_coverage_api import COVERAGE_ITEMS
from src.services.rentgen.business_case import build_business_case
from src.services.rentgen.buyer_brief import build_buyer_brief
from src.services.rentgen.executive_dashboard import build_executive_dashboard
from src.services.rentgen.intake_wizard import build_intake_plan
from src.services.rentgen.platform_doctor import build_platform_doctor
from src.services.rentgen.value_packs import build_value_packs
from src.services.rentgen.vendor_portfolio import build_vendor_portfolio

router = APIRouter(prefix="/api/v1/business-case", tags=["Business Case"])


class BusinessCaseAssumptions(BaseModel):
    monthly_ai_subscription_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    hourly_rate: int | None = Field(default=None, ge=0, le=2_000_000)
    manual_review_hours_month: int | None = Field(default=None, ge=0, le=20_000)
    incident_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    release_delay_hours_per_item: int | None = Field(default=None, ge=0, le=1_000)
    release_windows_per_month: int | None = Field(default=None, ge=0, le=100)
    currency: str | None = Field(default=None, max_length=12)


class BusinessCaseRequest(BaseModel):
    client_name: str = Field(default="Demo client", min_length=1, max_length=200)
    config_path: str | None = Field(default=None, max_length=2000)
    target_platform_version: str | None = Field(default=None, max_length=80)
    governance_limit: int = Field(default=40, ge=1, le=200)
    hotspot_limit: int = Field(default=12, ge=1, le=50)
    assumptions: BusinessCaseAssumptions | None = None


@router.post("/build")
def build(req: BusinessCaseRequest) -> dict[str, Any]:
    """Build a buyer-safe business case over live local Rentgen signals."""

    store = store_or_none()
    executive = build_executive_dashboard(
        store,
        coverage_items=COVERAGE_ITEMS,
        governance_limit=req.governance_limit,
        hotspot_limit=req.hotspot_limit,
        save_snapshot=False,
    )
    platform = build_platform_doctor(
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    intake = build_intake_plan(source_path=req.config_path, source_type="auto")
    value_packs = build_value_packs(executive)
    vendor = build_vendor_portfolio(
        executive=executive,
        platform=platform,
        intake=intake,
        client_name=req.client_name,
    )
    assumptions = req.assumptions.model_dump(exclude_none=True) if req.assumptions else None
    buyer_brief = build_buyer_brief(
        executive=executive,
        monthly_ai_subscription_cost=int((assumptions or {}).get("monthly_ai_subscription_cost") or 120_000),
        currency=str((assumptions or {}).get("currency") or "RUB"),
    )
    return build_business_case(
        executive=executive,
        platform=platform,
        intake=intake,
        vendor=vendor,
        value_packs=value_packs,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
        assumptions=assumptions,
        buyer_brief=buyer_brief,
    )


@router.get("/health")
def health() -> dict[str, Any]:
    """Liveness only — real numbers are served by /build."""

    return {"status": "ok", "service": "business-case"}
