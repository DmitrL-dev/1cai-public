"""Launch Room API for the first buyer-facing Rentgen cockpit."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.api.copilot_coverage_api import COVERAGE_ITEMS
from src.services.productization_readiness import productization_readiness
from src.services.rentgen.board_pack import build_board_pack
from src.services.rentgen.business_case import build_business_case
from src.services.rentgen.buyer_brief import build_buyer_brief
from src.services.rentgen.buyer_concierge import build_buyer_concierge
from src.services.rentgen.buyer_pulse import build_buyer_pulse
from src.services.rentgen.commercial_offer_studio import build_commercial_offer_studio
from src.services.rentgen.demo_command_center import build_demo_command_center
from src.services.rentgen.demo_story import build_demo_story
from src.services.rentgen.enterprise_trust_center import build_enterprise_trust_center
from src.services.rentgen.executive_dashboard import build_executive_dashboard
from src.services.rentgen.guided_demo import build_guided_demo
from src.services.rentgen.intake_wizard import build_intake_plan
from src.services.rentgen.launch_room import build_launch_room
from src.services.rentgen.offline_readiness import build_offline_readiness
from src.services.rentgen.outcome_ledger import build_outcome_ledger
from src.services.rentgen.pilot_launchpad import build_pilot_launchpad
from src.services.rentgen.platform_doctor import build_platform_doctor
from src.services.rentgen.rights_rls import build_rights_rls
from src.services.rentgen.scenario_hub import build_scenario_hub
from src.services.rentgen.security_posture import build_security_posture
from src.services.rentgen.value_packs import build_value_packs
from src.services.rentgen.vendor_portfolio import build_vendor_portfolio

router = APIRouter(prefix="/api/v1/launch-room", tags=["Launch Room"])


class LaunchRoomAssumptions(BaseModel):
    monthly_ai_subscription_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    hourly_rate: int | None = Field(default=None, ge=0, le=2_000_000)
    manual_review_hours_month: int | None = Field(default=None, ge=0, le=20_000)
    incident_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    release_delay_hours_per_item: int | None = Field(default=None, ge=0, le=1_000)
    release_windows_per_month: int | None = Field(default=None, ge=0, le=100)
    currency: str | None = Field(default=None, max_length=12)


class LaunchRoomRequest(BaseModel):
    client_name: str = Field(default="Demo client", min_length=1, max_length=200)
    config_path: str | None = Field(default=None, max_length=2000)
    target_platform_version: str | None = Field(default=None, max_length=80)
    governance_limit: int = Field(default=40, ge=1, le=200)
    hotspot_limit: int = Field(default=12, ge=1, le=50)
    security_limit: int = Field(default=120, ge=1, le=500)
    security_module_limit: int = Field(default=1200, ge=1, le=5000)
    assumptions: LaunchRoomAssumptions | None = None


def _artifact_summary(
    id: str, title: str, route: str, report: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": id,
        "title": title,
        "route": route,
        "status": (report.get("decision") or {}).get("status")
        or report.get("status")
        or "unknown",
        "score": (report.get("decision") or {}).get("score"),
    }


def _build_report(req: LaunchRoomRequest) -> dict[str, Any]:
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
    assumptions = (
        req.assumptions.model_dump(exclude_none=True) if req.assumptions else None
    )
    buyer_brief = build_buyer_brief(
        executive=executive,
        monthly_ai_subscription_cost=int(
            (assumptions or {}).get("monthly_ai_subscription_cost") or 120_000
        ),
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
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    demo_command_center = build_demo_command_center(
        executive=executive,
        scenario_hub=scenario_hub,
        guided_demo=guided_demo,
        pilot_launchpad=pilot_launchpad,
        business_case=business_case,
        productization=productization,
        vendor_portfolio=vendor,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    enterprise_trust_center = build_enterprise_trust_center(
        executive=executive,
        platform=platform,
        business_case=business_case,
        productization=productization,
        offline_readiness=build_offline_readiness(strict=False, include_metadata=False),
        security_posture=build_security_posture(
            config_path=req.config_path,
            limit=req.security_limit,
            module_limit=req.security_module_limit,
        ),
        rights_rls=build_rights_rls(
            config_path=req.config_path, role_limit=60, object_limit=160
        ),
        demo_command_center=demo_command_center,
        pilot_launchpad=pilot_launchpad,
        scenario_hub=scenario_hub,
        vendor_portfolio=vendor,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    commercial_offer_studio = build_commercial_offer_studio(
        executive=executive,
        business_case=business_case,
        pilot_launchpad=pilot_launchpad,
        enterprise_trust_center=enterprise_trust_center,
        productization=productization,
        scenario_hub=scenario_hub,
        value_packs=value_packs,
        vendor_portfolio=vendor,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    buyer_concierge = build_buyer_concierge(
        executive=executive,
        scenario_hub=scenario_hub,
        guided_demo=guided_demo,
        pilot_launchpad=pilot_launchpad,
        enterprise_trust_center=enterprise_trust_center,
        commercial_offer_studio=commercial_offer_studio,
        business_case=business_case,
        productization=productization,
        vendor_portfolio=vendor,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    board_pack = build_board_pack(
        executive=executive,
        buyer_concierge=buyer_concierge,
        commercial_offer_studio=commercial_offer_studio,
        enterprise_trust_center=enterprise_trust_center,
        business_case=business_case,
        scenario_hub=scenario_hub,
        pilot_launchpad=pilot_launchpad,
        demo_command_center=demo_command_center,
        productization=productization,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    outcome_ledger = build_outcome_ledger(
        executive=executive,
        board_pack=board_pack,
        buyer_concierge=buyer_concierge,
        commercial_offer_studio=commercial_offer_studio,
        enterprise_trust_center=enterprise_trust_center,
        business_case=business_case,
        scenario_hub=scenario_hub,
        pilot_launchpad=pilot_launchpad,
        demo_command_center=demo_command_center,
        productization=productization,
        value_packs=value_packs,
        vendor_portfolio=vendor,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    evidence_artifacts = [
        _artifact_summary(
            "platform-doctor", "Platform Doctor", "/platform-doctor", platform
        ),
        _artifact_summary(
            "configuration-intake", "Configuration Intake", "/configurations", intake
        ),
        _artifact_summary("value-packs", "Value Packs", "/value-packs", value_packs),
        _artifact_summary(
            "vendor-portfolio", "Vendor Portfolio", "/vendor-portfolio", vendor
        ),
        _artifact_summary(
            "business-case", "Business Case", "/business-case", business_case
        ),
        _artifact_summary("guided-demo", "Guided Demo", "/guided-demo", guided_demo),
        _artifact_summary(
            "scenario-hub", "Scenario Hub", "/scenario-hub", scenario_hub
        ),
        _artifact_summary(
            "pilot-launchpad", "Pilot Launchpad", "/pilot-launchpad", pilot_launchpad
        ),
        _artifact_summary(
            "demo-command-center",
            "Demo Command Center",
            "/demo-command-center",
            demo_command_center,
        ),
        _artifact_summary(
            "enterprise-trust-center",
            "Enterprise Trust Center",
            "/enterprise-trust-center",
            enterprise_trust_center,
        ),
        _artifact_summary(
            "commercial-offer-studio",
            "Commercial Offer Studio",
            "/commercial-offer-studio",
            commercial_offer_studio,
        ),
        _artifact_summary(
            "buyer-concierge", "Buyer Concierge", "/buyer-concierge", buyer_concierge
        ),
        _artifact_summary("board-pack", "Board Pack", "/board-pack", board_pack),
        _artifact_summary(
            "outcome-ledger", "Outcome Ledger", "/outcome-ledger", outcome_ledger
        ),
    ]
    return build_launch_room(
        executive=executive,
        buyer_concierge=buyer_concierge,
        scenario_hub=scenario_hub,
        demo_command_center=demo_command_center,
        enterprise_trust_center=enterprise_trust_center,
        commercial_offer_studio=commercial_offer_studio,
        board_pack=board_pack,
        outcome_ledger=outcome_ledger,
        business_case=business_case,
        pilot_launchpad=pilot_launchpad,
        buyer_brief=buyer_brief,
        evidence_bundle_artifacts=evidence_artifacts,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )


@router.post("/build")
def build(req: LaunchRoomRequest) -> dict[str, Any]:
    """Build one buyer-facing cockpit over role, proof, trust, approval and outcomes."""

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
        "status": pulse["launch"]["status"],
        "score": pulse["launch"]["score"],
        "phases": 4,
        "role_paths": pulse["concierge"]["persona_cards"],
        "journey_steps": pulse["launch"]["journey_steps"],
        "journey_ready": pulse["launch"]["journey_ready"],
        "governance_gates": pulse["launch"]["governance_gates"],
        "purchase_spine_status": pulse["launch"]["purchase_spine_status"],
        "three_year_ai_rent": pulse["commercial"]["three_year_ai_rent"],
        "proof_routes": pulse["launch"]["proof_routes"],
        "source": pulse["source"],
    }
