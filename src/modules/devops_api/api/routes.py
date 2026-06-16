from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from src.modules.devops_api.domain.models import (
    EvolutionRequest,
    EvolutionResponse,
    InfrastructureAnalysisResponse,
)
from src.modules.devops_api.services.devops_service import (
    AIEvolutionService,
    DevOpsService,
)

router = APIRouter(tags=["DevOps & AI Evolution"])


def get_devops_service() -> DevOpsService:
    return DevOpsService()


def get_ai_evolution_service() -> AIEvolutionService:
    return AIEvolutionService()


@router.post("/devops/infrastructure/analyze", response_model=InfrastructureAnalysisResponse)
async def analyze_infrastructure(
    compose_file: Optional[str] = Query(None, description="Path to docker-compose.yml")
) -> InfrastructureAnalysisResponse:
    """Analyze Docker infrastructure."""
    try:
        service = get_devops_service()
        result = await service.analyze_infrastructure(compose_file)

        return InfrastructureAnalysisResponse(
            status="success",
            static_analysis=result.get("static_analysis", {}),
            runtime_status=result.get("runtime_containers", []),
            services_status=result.get("services_status", {}),
            recommendations=result.get("recommendations", []),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/devops/infrastructure/status")
async def get_infrastructure_status() -> Dict[str, Any]:
    """Quick infrastructure status check."""
    try:
        service = get_devops_service()
        return await service.get_infrastructure_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/evolve", response_model=EvolutionResponse)
async def evolve_ai(request: Optional[EvolutionRequest] = None) -> EvolutionResponse:
    """Run AI evolution cycle."""
    try:
        if request is None:
            request = EvolutionRequest()

        service = get_ai_evolution_service()
        result = await service.evolve(request.force)

        return EvolutionResponse(
            status=result.get("status", "completed"),
            stage=result.get("stage", "completed"),
            metrics=result.get("metrics"),
            improvements=result.get("improvements", []),
            message=result.get("message", "Evolution completed successfully"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evolution failed: {str(e)}")


@router.get("/ai/evolve/status")
async def get_evolution_status() -> Dict[str, Any]:
    """Get AI evolution status."""
    try:
        service = get_ai_evolution_service()
        return await service.get_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai/evolve/metrics")
async def get_evolution_metrics() -> Dict[str, Any]:
    """Get evolution metrics history."""
    try:
        service = get_ai_evolution_service()
        return await service.get_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
