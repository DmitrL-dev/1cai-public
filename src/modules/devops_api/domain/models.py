from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class InfrastructureAnalysisResponse(BaseModel):
    """Infrastructure analysis response"""

    status: str
    static_analysis: Dict[str, Any]
    runtime_status: list
    services_status: Dict[str, Any]
    recommendations: list


class EvolutionRequest(BaseModel):
    """AI evolution request"""

    force: bool = Field(
        default=False, description="Force evolution even if system is healthy")


class EvolutionResponse(BaseModel):
    """AI evolution response"""

    status: str
    stage: str
    metrics: Optional[Dict[str, Any]] = None
    improvements: list = []
    message: str
