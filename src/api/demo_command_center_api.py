"""Demo Command Center API for live buyer meetings."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.api.copilot_coverage_api import COVERAGE_ITEMS
from src.services.productization_readiness import productization_readiness
from src.services.rentgen.business_case import build_business_case
from src.services.rentgen.buyer_brief import build_buyer_brief
from src.services.rentgen.buyer_pulse import build_buyer_pulse
from src.services.rentgen.demo_command_center import build_demo_command_center
from src.services.rentgen.demo_story import build_demo_story
from src.services.rentgen.executive_dashboard import build_executive_dashboard
from src.services.rentgen.guided_demo import build_guided_demo
from src.services.rentgen.intake_wizard import build_intake_plan
from src.services.rentgen.pilot_launchpad import build_pilot_launchpad
from src.services.rentgen.platform_doctor import build_platform_doctor
from src.services.rentgen.scenario_hub import build_scenario_hub
from src.services.rentgen.value_packs import build_value_packs
from src.services.rentgen.vendor_portfolio import build_vendor_portfolio

router = APIRouter(prefix="/api/v1/demo-command-center", tags=["Demo Command Center"])


class DemoCommandCenterAssumptions(BaseModel):
    monthly_ai_subscription_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    hourly_rate: int | None = Field(default=None, ge=0, le=2_000_000)
    manual_review_hours_month: int | None = Field(default=None, ge=0, le=20_000)
    incident_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    release_delay_hours_per_item: int | None = Field(default=None, ge=0, le=1_000)
    release_windows_per_month: int | None = Field(default=None, ge=0, le=100)
    currency: str | None = Field(default=None, max_length=12)


class DemoCommandCenterRequest(BaseModel):
    client_name: str = Field(default="Demo client", min_length=1, max_length=200)
    config_path: str | None = Field(default=None, max_length=2000)
    target_platform_version: str | None = Field(default=None, max_length=80)
    governance_limit: int = Field(default=40, ge=1, le=200)
    hotspot_limit: int = Field(default=12, ge=1, le=50)
    assumptions: DemoCommandCenterAssumptions | None = None


def _build_report(req: DemoCommandCenterRequest) -> dict[str, Any]:
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
    business_case = build_business_case(
        executive=executive,
        platform=platform,
        intake=intake,
        vendor=vendor,
        value_packs=value_packs,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
        assumptions=assumptions,
    )
    productization = productization_readiness()
    demo_story = build_demo_story(executive)
    guided_demo = build_guided_demo(
        executive=executive,
        demo_story=demo_story,
        business_case=business_case,
        productization=productization,
        value_packs=value_packs,
        vendor_portfolio=vendor,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    scenario_hub = build_scenario_hub(
        executive=executive,
        guided_demo=guided_demo,
        business_case=business_case,
        productization=productization,
        value_packs=value_packs,
        vendor_portfolio=vendor,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    pilot_launchpad = build_pilot_launchpad(
        executive=executive,
        scenario_hub=scenario_hub,
        guided_demo=guided_demo,
        business_case=business_case,
        productization=productization,
        value_packs=value_packs,
        vendor_portfolio=vendor,
        buyer_brief=buyer_brief,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    return build_demo_command_center(
        executive=executive,
        scenario_hub=scenario_hub,
        guided_demo=guided_demo,
        pilot_launchpad=pilot_launchpad,
        business_case=business_case,
        productization=productization,
        vendor_portfolio=vendor,
        buyer_brief=buyer_brief,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )


@router.post("/build")
def build(req: DemoCommandCenterRequest) -> dict[str, Any]:
    """Build live demo stages, role pivots and presenter recovery cards."""

    return _build_report(req)


@router.get("/health")
def health() -> dict[str, Any]:
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
        "stages": 6,
        "total_minutes": 8,
        "purchase_status": pulse["purchase_status"],
        "three_year_ai_rent": pulse["commercial"]["three_year_ai_rent"],
        "source": pulse["source"],
    }
