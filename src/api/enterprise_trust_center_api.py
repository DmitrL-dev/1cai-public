"""Enterprise Trust Center API for CIO, security and procurement proof."""

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
from src.services.rentgen.enterprise_trust_center import build_enterprise_trust_center
from src.services.rentgen.executive_dashboard import build_executive_dashboard
from src.services.rentgen.guided_demo import build_guided_demo
from src.services.rentgen.intake_wizard import build_intake_plan
from src.services.rentgen.offline_readiness import build_offline_readiness
from src.services.rentgen.pilot_launchpad import build_pilot_launchpad
from src.services.rentgen.platform_doctor import build_platform_doctor
from src.services.rentgen.rights_rls import build_rights_rls
from src.services.rentgen.scenario_hub import build_scenario_hub
from src.services.rentgen.security_posture import build_security_posture
from src.services.rentgen.value_packs import build_value_packs
from src.services.rentgen.vendor_portfolio import build_vendor_portfolio

router = APIRouter(prefix="/api/v1/enterprise-trust-center", tags=["Enterprise Trust Center"])


class EnterpriseTrustCenterAssumptions(BaseModel):
    monthly_ai_subscription_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    hourly_rate: int | None = Field(default=None, ge=0, le=2_000_000)
    manual_review_hours_month: int | None = Field(default=None, ge=0, le=20_000)
    incident_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    release_delay_hours_per_item: int | None = Field(default=None, ge=0, le=1_000)
    release_windows_per_month: int | None = Field(default=None, ge=0, le=100)
    currency: str | None = Field(default=None, max_length=12)


class EnterpriseTrustCenterRequest(BaseModel):
    client_name: str = Field(default="Demo client", min_length=1, max_length=200)
    config_path: str | None = Field(default=None, max_length=2000)
    target_platform_version: str | None = Field(default=None, max_length=80)
    analysis_depth: str = Field(default="standard", pattern="^(preview|standard|deep)$")
    governance_limit: int = Field(default=40, ge=1, le=200)
    hotspot_limit: int = Field(default=12, ge=1, le=50)
    security_limit: int = Field(default=120, ge=1, le=500)
    security_module_limit: int = Field(default=1200, ge=1, le=5000)
    rights_role_limit: int = Field(default=60, ge=1, le=300)
    rights_object_limit: int = Field(default=160, ge=1, le=1000)
    assumptions: EnterpriseTrustCenterAssumptions | None = None


def _preview_security_posture(req: EnterpriseTrustCenterRequest) -> dict[str, Any]:
    return {
        "available": True,
        "config_path": req.config_path or "",
        "decision": {
            "status": "watch",
            "score": 72,
            "headline": "Preview depth defers full static security scan to standard/deep mode.",
        },
        "summary": {
            "findings": 0,
            "external_exposure": 0,
            "scanned_modules": 0,
            "scan_limit": req.security_module_limit,
        },
        "recommendations": [],
        "caveats": [
            "Preview depth skips full metadata graph and BSL security scan for first-run speed.",
            "Run standard or deep depth before production security approval.",
        ],
        "markdown": "# Security Posture Preview\n\nFull static scan is deferred to standard/deep depth.",
    }


def _preview_rights_rls(req: EnterpriseTrustCenterRequest) -> dict[str, Any]:
    return {
        "available": True,
        "config_path": req.config_path or "",
        "decision": {
            "status": "watch",
            "score": 72,
            "headline": "Preview depth defers full Rights/RLS matrix to standard/deep mode.",
        },
        "summary": {
            "roles": 0,
            "roles_scanned": 0,
            "dangerous_rights": 0,
            "rls_rules": 0,
            "findings": 0,
            "role_limit": req.rights_role_limit,
            "object_limit": req.rights_object_limit,
        },
        "findings": [],
        "gate": {
            "status": "warn",
            "block_release": False,
            "reasons": ["Preview depth does not build the full Rights/RLS matrix."],
        },
        "recommended_actions": [],
        "caveats": [
            "Preview depth skips the full Rights/RLS matrix for first-run speed.",
            "Run standard or deep depth before production role approval.",
        ],
        "markdown": "# Rights & RLS Preview\n\nFull matrix is deferred to standard/deep depth.",
    }


def _score_floor(report: dict[str, Any], floor: int) -> int:
    try:
        return max(floor, int(float((report.get("decision") or {}).get("score") or report.get("score") or 0)))
    except (TypeError, ValueError):
        return floor


def _soften_preview_risk(report: dict[str, Any], *, headline: str, score_floor: int = 60) -> dict[str, Any]:
    decision = dict(report.get("decision") or {})
    status = str(decision.get("status") or report.get("status") or "")
    if status not in {"risk", "fail", "critical", "blocked"}:
        return report
    softened = dict(report)
    decision["status"] = "watch"
    decision["score"] = _score_floor(report, score_floor)
    decision["headline"] = headline
    softened["decision"] = decision
    caveats = list(softened.get("caveats") or [])
    caveats.append("Preview depth surfaces missing facts as watch; run standard or deep depth to confirm hard blockers.")
    softened["caveats"] = caveats
    return softened


def _build_report(req: EnterpriseTrustCenterRequest) -> dict[str, Any]:
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
    if req.analysis_depth == "preview":
        platform = _soften_preview_risk(
            platform,
            headline="Preview depth keeps platform caveats visible without blocking the first trust handoff.",
            score_floor=60,
        )
    intake = build_intake_plan(source_path=req.config_path, source_type="auto")
    assumptions = req.assumptions.model_dump(exclude_none=True) if req.assumptions else None
    buyer_brief = build_buyer_brief(
        executive=executive,
        monthly_ai_subscription_cost=int((assumptions or {}).get("monthly_ai_subscription_cost") or 120_000),
        currency=str((assumptions or {}).get("currency") or "RUB"),
    )
    value_packs = build_value_packs(executive, buyer_brief=buyer_brief)
    vendor = build_vendor_portfolio(
        executive=executive,
        platform=platform,
        intake=intake,
        buyer_brief=buyer_brief,
        client_name=req.client_name,
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
        buyer_brief=buyer_brief,
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
        buyer_brief=buyer_brief,
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
        buyer_brief=buyer_brief,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
    )
    if req.analysis_depth == "preview":
        scenario_hub = _soften_preview_risk(
            scenario_hub,
            headline="Preview depth keeps scenario caveats visible while the first trust path stays navigable.",
            score_floor=60,
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
    if req.analysis_depth == "preview":
        pilot_launchpad = _soften_preview_risk(
            pilot_launchpad,
            headline="Preview depth keeps pilot caveats visible without blocking the first buyer handoff.",
            score_floor=60,
        )
    demo_command_center = build_demo_command_center(
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
    if req.analysis_depth == "preview":
        demo_command_center = _soften_preview_risk(
            demo_command_center,
            headline="Preview depth keeps demo command caveats visible while standard/deep confirms blockers.",
            score_floor=60,
        )
    offline = build_offline_readiness(strict=False, include_metadata=False)
    if req.analysis_depth == "preview":
        security = _preview_security_posture(req)
        rights = _preview_rights_rls(req)
    else:
        security = build_security_posture(
            config_path=req.config_path,
            limit=req.security_limit,
            module_limit=req.security_module_limit,
        )
        rights = build_rights_rls(
            config_path=req.config_path,
            role_limit=req.rights_role_limit,
            object_limit=req.rights_object_limit,
        )
    return build_enterprise_trust_center(
        executive=executive,
        platform=platform,
        business_case=business_case,
        productization=productization,
        offline_readiness=offline,
        security_posture=security,
        rights_rls=rights,
        demo_command_center=demo_command_center,
        pilot_launchpad=pilot_launchpad,
        scenario_hub=scenario_hub,
        vendor_portfolio=vendor,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
        analysis_depth=req.analysis_depth,
        buyer_brief=buyer_brief,
        scan_limits={
            "governance_limit": req.governance_limit,
            "hotspot_limit": req.hotspot_limit,
            "security_limit": req.security_limit,
            "security_module_limit": req.security_module_limit,
            "rights_role_limit": req.rights_role_limit,
            "rights_object_limit": req.rights_object_limit,
        },
    )


def _quick_health_report() -> dict[str, Any]:
    decision = {"decision": {"status": "ready", "score": 90, "headline": "health"}}
    productization = {
        "status": "pass",
        "score": 90,
        "summary": {"findings": 0, "deliverables": 4},
        "deliverables": [
            {"id": "sbom-inventory-guide", "status": "pass"},
            {"id": "sbom-inventory-service", "status": "pass"},
            {"id": "offline-bundle-guide", "status": "pass"},
            {"id": "offline-bundle-service", "status": "pass"},
        ],
        "findings": [],
    }
    return build_enterprise_trust_center(
        executive=decision,
        platform={**decision, "checks": []},
        business_case=decision,
        productization=productization,
        offline_readiness={"decision": {"status": "pass", "score": 90}, "summary": {"external_env": 0}},
        security_posture={
            "decision": {"status": "pass", "score": 90},
            "summary": {"findings": 0, "external_exposure": 0},
            "recommendations": [],
        },
        rights_rls={
            "decision": {"status": "ready", "score": 90},
            "summary": {"dangerous_rights": 0, "findings": 0},
            "findings": [],
        },
        demo_command_center=decision,
        pilot_launchpad=decision,
        scenario_hub=decision,
        vendor_portfolio={"decision": {"status": "ready", "score": 90}, "work_packages": []},
        evidence_artifacts=[{"id": "enterprise-trust-center"}],
        client_name="Health",
    )


@router.post("/build")
def build(req: EnterpriseTrustCenterRequest) -> dict[str, Any]:
    """Build enterprise trust controls, security answers and procurement proof."""

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
    questionnaire_blocked = 1 if pulse["purchase_status"] == "risk" else 0
    return {
        "status": pulse["status"],
        "score": pulse["score"],
        "controls": 9,
        "failed_controls": questionnaire_blocked,
        "questionnaire_status": "ready" if pulse["purchase_status"] == "ready" else "watch",
        "questionnaire_blocked": questionnaire_blocked,
        "purchase_status": pulse["purchase_status"],
        "three_year_ai_rent": pulse["commercial"]["three_year_ai_rent"],
        "source": pulse["source"],
    }
