"""
BA Sessions API Routes
"""
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Body,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.ba_sessions.domain.models import (
    EnablementPlanRequest,
    GuideRequest,
    JourneyMapRequest,
    KPIGenerationRequest,
    PresentationRequest,
    ProcessModelRequest,
    SyncBPMNRequest,
    SyncRequirementsRequest,
    TraceabilityRequest,
)
from src.modules.ba_sessions.services.analytics_service import AnalyticsService
from src.modules.ba_sessions.services.documentation_service import DocumentationService
from src.modules.ba_sessions.services.integration_service import IntegrationService
from src.modules.ba_sessions.services.modeling_service import ModelingService
from src.modules.ba_sessions.services.session_service import SessionService
from src.modules.ba_sessions.services.traceability_service import TraceabilityService
from src.security.auth import get_auth_service

logger = StructuredLogger(__name__).logger

router = APIRouter(tags=["BA Sessions"])

# Initialize services
session_service = SessionService()
traceability_service = TraceabilityService()
analytics_service = AnalyticsService()
modeling_service = ModelingService()
integration_service = IntegrationService()
documentation_service = DocumentationService()


# === Sessions ===


@router.websocket("/ws/{session_id}")
async def ba_session_ws(
    websocket: WebSocket,
    session_id: str,
    user_id: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default="analyst"),
    topic: Optional[str] = Query(default=None),
    token: Optional[str] = Query(default=None),
):
    """WebSocket endpoint for collaborative BA sessions."""
    if token:
        try:
            principal = get_auth_service().decode_token(token)
            user_id = user_id or principal.user_id
            if principal.roles:
                role = principal.roles[0]
        except Exception as exc:
            logger.warning("Failed to decode token for BA session: %s", exc)
    if not user_id:
        user_id = "anonymous"
    try:
        await session_service.join_session(
            session_id,
            websocket,
            user_id=user_id,
            role=role or "analyst",
            topic=topic,
        )
        await session_service.broadcast(
            session_id,
            {
                "type": "system",
                "event": "user_joined",
                "user_id": user_id,
                "role": role,
            },
            sender="system",
        )

        while True:
            data = await websocket.receive_json()
            message_type = data.get("type") or "message"
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            elif message_type == "leave":
                await websocket.close()
                break
            else:
                await session_service.broadcast(
                    session_id,
                    data,
                    sender=user_id,
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("BA session websocket error: %s", exc)
    finally:
        await session_service.leave_session(session_id, user_id)
        await session_service.broadcast(
            session_id,
            {"type": "system", "event": "user_left", "user_id": user_id},
            sender="system",
        )


@router.get("/")
async def list_sessions():
    """List active BA sessions."""
    return {"sessions": session_service.list_sessions()}


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get state for a BA session."""
    state = session_service.get_session_state(session_id)
    if not state:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})
    return state


# === Traceability & Compliance ===


@router.post("/traceability/matrix")
async def build_traceability_matrix(request: TraceabilityRequest) -> Dict[str, Any]:
    """Build traceability matrix."""
    try:
        return await traceability_service.build_traceability_matrix(
            request.requirement_ids,
            request.include_code,
            request.include_tests,
            request.include_incidents,
            request.use_graph,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to build traceability matrix: {str(e)}"
        )


@router.post("/traceability/risk-register")
async def build_risk_register(
    requirement_ids: List[str] = Body(..., description="List of requirement IDs"),
    include_incidents: bool = Body(default=True, description="Include incidents"),
) -> Dict[str, Any]:
    """Build Risk Register."""
    try:
        return await traceability_service.build_risk_register(
            requirement_ids, include_incidents
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to build risk register: {str(e)}"
        )


@router.post("/traceability/full-report")
async def build_full_traceability_report(
    requirement_ids: List[str] = Body(..., description="List of requirement IDs"),
) -> Dict[str, Any]:
    """Build full traceability report."""
    try:
        return await traceability_service.build_full_traceability_report(
            requirement_ids
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build full traceability report: {str(e)}",
        )


# === Analytics & KPI ===


@router.post("/analytics/kpi")
async def generate_kpis(request: KPIGenerationRequest) -> Dict[str, Any]:
    """Generate KPIs."""
    try:
        return await analytics_service.generate_kpis(
            request.initiative_name,
            request.feature_id,
            request.include_technical,
            request.include_business,
            request.use_graph,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate KPIs: {str(e)}"
        )


# === Process & Journey Modelling ===


@router.post("/process/model")
async def generate_process_model(request: ProcessModelRequest) -> Dict[str, Any]:
    """Generate process model."""
    try:
        return await modeling_service.generate_process_model(
            request.description,
            request.requirement_id,
            request.format,
            request.use_graph,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate process model: {str(e)}"
        )


@router.post("/process/journey-map")
async def generate_journey_map(request: JourneyMapRequest) -> Dict[str, Any]:
    """Generate Customer Journey Map."""
    try:
        return await modeling_service.generate_journey_map(
            request.journey_description,
            request.stages,
            request.format,
            request.use_graph,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate journey map: {str(e)}"
        )


@router.post("/process/validate")
async def validate_process(
    process_model: Dict[str, Any] = Body(..., description="Process model"),
) -> Dict[str, Any]:
    """Validate process model."""
    try:
        return await modeling_service.validate_process_model(process_model)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to validate process: {str(e)}"
        )


# === Integrations ===


@router.post("/integrations/sync-requirements-jira")
async def sync_requirements_to_jira(request: SyncRequirementsRequest) -> Dict[str, Any]:
    """Sync requirements to Jira."""
    try:
        return await integration_service.sync_requirements_to_jira(
            request.requirement_ids,
            request.project_key,
            request.issue_type,
            request.use_graph,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to sync requirements to Jira: {str(e)}"
        )


@router.post("/integrations/sync-bpmn-confluence")
async def sync_bpmn_to_confluence(request: SyncBPMNRequest) -> Dict[str, Any]:
    """Sync BPMN to Confluence."""
    try:
        return await integration_service.sync_bpmn_to_confluence(
            request.process_model,
            request.space_key,
            request.parent_page_id,
            request.use_graph,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to sync BPMN to Confluence: {str(e)}"
        )


@router.post("/integrations/sync-kpi-confluence")
async def sync_kpi_to_confluence(
    kpi_report: Dict[str, Any] = Body(..., description="KPI Report"),
    space_key: Optional[str] = Body(default=None, description="Confluence space key"),
    parent_page_id: Optional[str] = Body(default=None, description="Parent page ID"),
    use_graph: bool = Body(default=True, description="Use Unified Change Graph"),
) -> Dict[str, Any]:
    """Sync KPI to Confluence."""
    try:
        return await integration_service.sync_kpi_to_confluence(
            kpi_report, space_key, parent_page_id, use_graph
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to sync KPI to Confluence: {str(e)}"
        )


@router.post("/integrations/sync-traceability-confluence")
async def sync_traceability_to_confluence(
    traceability_report: Dict[str, Any] = Body(..., description="Traceability Report"),
    space_key: Optional[str] = Body(default=None, description="Confluence space key"),
    parent_page_id: Optional[str] = Body(default=None, description="Parent page ID"),
    use_graph: bool = Body(default=True, description="Use Unified Change Graph"),
) -> Dict[str, Any]:
    """Sync Traceability to Confluence."""
    try:
        return await integration_service.sync_traceability_to_confluence(
            traceability_report, space_key, parent_page_id, use_graph
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync traceability to Confluence: {str(e)}",
        )


# === Documentation & Enablement ===


@router.post("/enablement/plan")
async def generate_enablement_plan(request: EnablementPlanRequest) -> Dict[str, Any]:
    """Generate enablement plan."""
    try:
        return await documentation_service.generate_enablement_plan(
            request.feature_name,
            request.audience,
            request.include_examples,
            request.use_graph,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate enablement plan: {str(e)}"
        )


@router.post("/enablement/guide")
async def generate_guide(request: GuideRequest) -> Dict[str, Any]:
    """Generate guide."""
    try:
        return await documentation_service.generate_guide(
            request.topic,
            request.format,
            request.include_code_examples,
            request.use_graph,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate guide: {str(e)}"
        )


@router.post("/enablement/presentation")
async def generate_presentation(request: PresentationRequest) -> Dict[str, Any]:
    """Generate presentation outline."""
    try:
        return await documentation_service.generate_presentation(
            request.topic,
            request.audience,
            request.duration_minutes,
            request.use_graph,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate presentation: {str(e)}"
        )


@router.post("/enablement/onboarding-checklist")
async def generate_onboarding_checklist(
    role: str = Body(default="BA", description="Role"),
    include_practical_tasks: bool = Body(
        default=True, description="Include practical tasks"
    ),
    use_graph: bool = Body(default=True, description="Use Unified Change Graph"),
) -> Dict[str, Any]:
    """Generate onboarding checklist."""
    try:
        return await documentation_service.generate_onboarding_checklist(
            role, include_practical_tasks, use_graph
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate onboarding checklist: {str(e)}"
        )
