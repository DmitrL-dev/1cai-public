"""Swarm BSL Review API — micro-model code analysis."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/swarm", tags=["swarm"])


class SwarmReviewRequest(BaseModel):
    code: str


class SwarmReviewResponse(BaseModel):
    decision: str
    scores: dict[str, float]
    response: str | None
    confidence: float


@router.post("/review", response_model=SwarmReviewResponse)
async def review_code(req: SwarmReviewRequest):
    """Analyze BSL code with Micro-Swarm models."""
    from src.micro_swarm.router import SwarmRouter

    router_instance = SwarmRouter.default()
    result = router_instance.review(req.code)
    return SwarmReviewResponse(
        decision=result.decision.value,
        scores=result.scores,
        response=result.response,
        confidence=result.confidence,
    )


@router.get("/health")
async def swarm_health():
    """Check Swarm service health."""
    from pathlib import Path

    models_dir = Path("data/models")
    models = list(models_dir.glob("*.json")) if models_dir.exists() else []
    return {
        "status": "ok",
        "models_trained": len(models),
        "model_names": [m.stem for m in models],
    }
