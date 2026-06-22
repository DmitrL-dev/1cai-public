"""
Router Configuration for 1C AI Stack

Содержит все роутеры модулей и их регистрацию.
"""

import logging

from fastapi import APIRouter, Depends

from src.middleware.jwt_user_context import require_auth

logger = logging.getLogger(__name__)

# Routers that mutate or expose governance / enterprise / audit / IAM state
# MUST require an authenticated principal. We attach require_auth at
# registration time so enforcement is central and cannot be forgotten by an
# individual endpoint. Health/readiness sub-routes inside these modules are
# intentionally light, but the whole governance surface is privileged, so we
# guard it uniformly rather than leaving holes.
_AUTH_REQUIRED_DIRECT_ROUTERS = {
    "Approvals",
    "Artifacts",
    "Change Sets",
    "Baselines",
    "Policies",
    "Testing Evidence",
    "Test Factory",
    "Audit",
    "Enterprise",
    "Agentic",
    "Safe Autopilot",
    "Team Governance",
    "Requirements Impact",
    "Metadata Graph",
    "Release Readiness",
    "Architecture Review",
    "Offline Readiness",
    "Operations",
    "Lock Radar",
    "Extension Safety",
    "Platform Doctor",
    "Update War Room",
    "Rights & RLS",
    "Vendor Portfolio",
    "Value Packs",
    "Business Case",
    "Board Pack",
    "Buyer Concierge",
    "Commercial Offer Studio",
    "Demo Command Center",
    "Enterprise Trust Center",
    "Guided Demo",
    "Killer Demo",
    "Launch Room",
    "Outcome Ledger",
    "Scenario Hub",
    "Pilot Launchpad",
    "Evidence Bundle",
    "Management",
    "EDT MCP Bridge",
    "Productization",
    # Read caller-supplied filesystem paths / disclose ITS docs / run local
    # compute — must not be anonymous (closes the unauth LFI on Performer and
    # IP-disclosure on ITS RAG). Copilot Coverage stays public (static GET catalog).
    "Performer",
    "ITS RAG",
    "Swarm",
}

_LEGACY_OPTIONAL_MODULE_ROUTERS = {
    "dashboard",
    "bpmn",
    "oauth",
    "analytics",
    "knowledge_base",
    "council",
    "ml",
}

_PUBLIC_MODULE_ROUTERS = {
    # Token issuance must remain public; protected endpoints inside the auth
    # router keep their own dependencies.
    "auth",
    # OAuth callbacks are invoked by external providers and cannot carry our
    # bearer token. User-initiated OAuth operations are protected inside the
    # router with get_current_user_id.
    "oauth",
}


def _dependencies_for_module_router(name: str) -> list:
    if name in _PUBLIC_MODULE_ROUTERS:
        return []
    return [Depends(require_auth)]


def get_module_routers() -> list[tuple[str, APIRouter]]:
    """Возвращает список роутеров модулей."""
    routers = []

    # Core Module Routers
    router_imports = [
        ("dashboard", "src.modules.dashboard.api.routes", "router"),
        ("copilot", "src.modules.copilot.api.routes", "router"),
        ("marketplace", "src.modules.marketplace.api.routes", "router"),
        ("code_review", "src.modules.code_review.api.routes", "router"),
        # ("test_generation", ...) — UNMOUNTED (rc0 audit): legacy pre-Рентген module
        # off the token-free product path; module retained, re-enable if needed.
        ("websocket", "src.modules.websocket.api.routes", "router"),
        ("bpmn", "src.modules.bpmn_api.api.routes", "router"),
        # Auth & Admin
        ("auth", "src.modules.auth.api.routes", "router"),
        ("oauth", "src.modules.auth.api.oauth_routes", "router"),
        ("admin_dashboard", "src.modules.admin_dashboard.api.routes", "router"),
        ("admin_audit", "src.api.admin_audit", "router"),
        ("admin_roles", "src.api.admin_roles", "router"),
        # AI & Analytics
        ("analytics", "src.modules.analytics.api.routes", "router"),
        # ("assistants", ...) and ("ba_sessions", ...) — UNMOUNTED (rc0 audit): legacy
        # pre-Рентген AI modules off the token-free path; modules retained.
        # DevOps & Infra
        ("devops", "src.modules.devops_api.api.routes", "router"),
        ("monitoring", "src.api.monitoring", "router"),
        ("metrics", "src.modules.metrics.api.routes", "router"),
        # Security
        # ("security", "src.modules.security.api.routes", "router"),  # DELETED Phase 7 — dead module
        ("risk", "src.modules.risk.api.routes", "router"),
        # Knowledge & Docs
        # ("wiki", ...) — DELETED: stub module (43 LOC, returns empty [])
        ("knowledge_base", "src.modules.knowledge_base.api.routes", "router"),
        # ("technical_writer", ...) — DELETED Phase 7
        # Integration
        # ("github", ...) — UNMOUNTED (rc0 audit): legacy integration off the token-free path
        # (\"graph\", ...) — DELETED: broken imports (neo4j/qdrant removed from stack)
        # Project & Code
        # ("project_manager", ...) — DELETED Phase 7
        # ("scenario_hub", ...) — DELETED Phase 7 (no __init__, dead)
        # ("code_approval", ...) — UNMOUNTED (rc0 audit): legacy off the token-free path
        ("code_analyzers", "src.modules.code_analyzers.api.routes", "router"),
        # ("sql_optimizer", ...) — DELETED Phase 7
        # Other
        ("tenant", "src.modules.tenant_management.api.routes", "router"),
        # orchestrator_api / council_api UNMOUNTED (rc0 audit): legacy pre-Рентген
        # AI-orchestration HTTP surface, NOT called by the product portal (the
        # token-free path uses copilot/swarm/coverage only). Implementations are
        # retained under src/ai/ but no longer exposed as live routes — this shrinks
        # the attack surface the audit flagged. Re-enable by uncommenting if needed.
        # ("orchestrator", "src.api.orchestrator_api", "router"),
        # ("council", "src.api.council_api", "router"),
        ("ml", "src.modules.ml.api.routes", "router"),
        # Graph & Analysis — rentgen is mounted directly on app (see below)
        # to avoid gateway catch-all /{service}/{path:path} interception
        # Gateway MUST be last — its catch-all route intercepts everything
        ("gateway", "src.modules.gateway.api.routes", "router"),
    ]

    for name, module_path, attr_name in router_imports:
        try:
            module = __import__(module_path, fromlist=[attr_name])
            router = getattr(module, attr_name)
            routers.append((name, router))
        except ImportError as e:
            if name in _LEGACY_OPTIONAL_MODULE_ROUTERS:
                logger.info("Legacy optional router '%s' not mounted: %s", name, e)
            else:
                logger.warning(f"Router '{name}' not available: {e}")
        except Exception as e:
            logger.error(f"Failed to load router '{name}': {e}")

    return routers


def get_optional_routers() -> list[tuple[str, APIRouter]]:
    """Возвращает опциональные роутеры (могут отсутствовать)."""
    routers = []

    # Revolutionary Components removed (cleanup/phase-1-dead-code)

    # Archi API
    try:
        from src.api.archi_api import router as archi_router

        routers.append(("archi", archi_router))
        logger.info("Archi API router loaded")
    except ImportError:
        pass

    return routers


def register_routers(app, api_v1_router: APIRouter):
    """Регистрирует все роутеры в приложении."""
    routers = get_module_routers() + get_optional_routers()

    for name, router in routers:
        try:
            api_v1_router.include_router(
                router, dependencies=_dependencies_for_module_router(name)
            )
        except Exception as e:
            logger.warning(f"Failed to register router '{name}': {e}")

    # Mount rentgen DIRECTLY on app (before api_v1_router) to avoid
    # gateway's catch-all /{service}/{path:path} interception
    try:
        from src.api.rentgen_api import router as rentgen_router

        app.include_router(rentgen_router, prefix="/api/v1")
        logger.info("Rentgen router mounted directly on app at /api/v1/rentgen")
    except ImportError as e:
        logger.warning(f"Rentgen router not available: {e}")

    # Quality API — same pattern as rentgen (direct mount to avoid gateway catch-all)
    try:
        from src.api.quality_api import router as quality_router

        app.include_router(quality_router, prefix="/api/v1")
        logger.info("Quality router mounted directly on app at /api/v1/quality")
    except ImportError as e:
        logger.warning(f"Quality router not available: {e}")

    # Performer / ITS / Swarm routers already include their full /api/v1 prefix.
    # Mount them directly for the same gateway-bypass reason as rentgen/quality.
    for name, module_path in (
        ("Performer", "src.api.performer_api"),
        ("ITS RAG", "src.api.its_rag_api"),
        ("Swarm", "src.api.swarm_api"),
        ("Copilot Coverage", "src.api.copilot_coverage_api"),
        # Public read-only operability (no secrets): cache stats + optional LLM
        # generation-layer provider status. Health-style, intentionally unauthenticated.
        ("Cache Metrics", "src.api.cache_api"),
        ("LLM Providers", "src.api.llm_api"),
        ("Requirements Impact", "src.api.requirements_api"),
        ("Metadata Graph", "src.api.metadata_api"),
        ("Release Readiness", "src.api.release_readiness_api"),
        ("Architecture Review", "src.api.architecture_api"),
        ("Offline Readiness", "src.api.offline_readiness_api"),
        ("Team Governance", "src.api.team_governance_api"),
        ("Operations", "src.api.operations_api"),
        ("Lock Radar", "src.api.lock_radar_api"),
        ("Extension Safety", "src.api.extension_safety_api"),
        ("Platform Doctor", "src.api.platform_doctor_api"),
        ("Update War Room", "src.api.update_war_room_api"),
        ("Rights & RLS", "src.api.rights_rls_api"),
        ("Vendor Portfolio", "src.api.vendor_portfolio_api"),
        ("Value Packs", "src.api.value_packs_api"),
        ("Business Case", "src.api.business_case_api"),
        ("Board Pack", "src.api.board_pack_api"),
        ("Buyer Concierge", "src.api.buyer_concierge_api"),
        ("Commercial Offer Studio", "src.api.commercial_offer_studio_api"),
        ("Demo Command Center", "src.api.demo_command_center_api"),
        ("Enterprise Trust Center", "src.api.enterprise_trust_center_api"),
        ("Guided Demo", "src.api.guided_demo_api"),
        ("Killer Demo", "src.api.killer_demo_api"),
        ("Launch Room", "src.api.launch_room_api"),
        ("Outcome Ledger", "src.api.outcome_ledger_api"),
        ("Scenario Hub", "src.api.scenario_hub_api"),
        ("Pilot Launchpad", "src.api.pilot_launchpad_api"),
        ("Evidence Bundle", "src.api.evidence_bundle_api"),
        ("Management", "src.api.management_api"),
        ("EDT MCP Bridge", "src.api.edt_mcp_api"),
        ("Approvals", "src.api.approval_api"),
        ("Artifacts", "src.api.artifacts_api"),
        ("Change Sets", "src.api.change_sets_api"),
        ("Baselines", "src.api.baselines_api"),
        ("Policies", "src.api.policies_api"),
        ("Testing Evidence", "src.api.testing_api"),
        ("Test Factory", "src.api.test_factory_api"),
        ("Audit", "src.api.audit_api"),
        ("Enterprise", "src.api.enterprise_api"),
        ("Agentic", "src.api.agentic_api"),
        ("Safe Autopilot", "src.api.safe_autopilot_api"),
        ("Productization", "src.api.productization_api"),
    ):
        try:
            module = __import__(module_path, fromlist=["router"])
            if name in _AUTH_REQUIRED_DIRECT_ROUTERS:
                app.include_router(module.router, dependencies=[Depends(require_auth)])
                logger.info("%s router mounted directly on app (auth required)", name)
            else:
                app.include_router(module.router)
                logger.info("%s router mounted directly on app", name)
        except ImportError as e:
            logger.warning("%s router not available: %s", name, e)

    app.include_router(api_v1_router)
    logger.info(f"Registered {len(routers)} routers under /api/v1")

    # API v2 (optional)
    try:
        from fastapi import APIRouter
        from fastapi.responses import JSONResponse

        from src.api.v2.router import router as api_v2_router_impl

        api_v2_router = APIRouter(
            prefix="/api/v2",
            tags=["API v2"],
            default_response_class=JSONResponse,
        )
        api_v2_router.include_router(api_v2_router_impl)
        app.include_router(api_v2_router)
        logger.info("API v2 router registered")
    except ImportError:
        logger.info("API v2 not available")
