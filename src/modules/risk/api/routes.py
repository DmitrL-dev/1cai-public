from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.modules.risk.domain.models import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    RiskRecord,
)
from src.modules.risk.services.risk_service import RiskService

router = APIRouter(tags=["Risk Management"])


def get_risk_service() -> RiskService:
    return RiskService()


@router.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint."""
    return {
        "service": "Risk Management API",
        "version": "1.0.0",
        "status": "active",
        "description": "1C project risk management",
    }


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check."""
    service = get_risk_service()
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "service": "Risk Management API",
        "version": "1.0.0",
        "risks_tracked": service.db.count(),
    }


@router.post("/risk-assessment", response_model=RiskAssessmentResponse)
async def assess_risks(request: RiskAssessmentRequest) -> RiskAssessmentResponse:
    """Assess project risks."""
    try:
        service = get_risk_service()
        result = await service.assess_risks(request.requirements, request.context, request.architecture)
        return RiskAssessmentResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risks")
async def list_risks() -> Dict[str, Any]:
    """List all tracked risks."""
    service = get_risk_service()
    risks = await service.list_risks()
    return {
        "risks": [
            {
                "id": risk.id,
                "category": risk.category,
                "description": risk.description,
                "impact": risk.impact,
                "probability": risk.probability,
                "status": risk.status,
                "created_at": risk.created_at.isoformat(),
            }
            for risk in risks
        ],
        "total_count": len(risks),
    }


@router.post("/risks")
async def create_risk(risk: RiskRecord) -> Dict[str, Any]:
    """Create new risk record."""
    try:
        service = get_risk_service()
        await service.create_risk(risk)
        return {
            "status": "success",
            "risk_id": risk.id,
            "message": "Risk successfully created",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risks/{risk_id}")
async def get_risk(risk_id: str) -> Dict[str, Any]:
    """Get risk information."""
    service = get_risk_service()
    risk = await service.get_risk(risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")

    return {
        "risk": {
            "id": risk.id,
            "category": risk.category,
            "description": risk.description,
            "impact": risk.impact,
            "probability": risk.probability,
            "mitigation_plan": risk.mitigation_plan,
            "owner": risk.owner,
            "status": risk.status,
            "created_at": risk.created_at.isoformat(),
        }
    }


@router.put("/risks/{risk_id}/status")
async def update_risk_status(risk_id: str, status: str) -> Dict[str, Any]:
    """Update risk status."""
    service = get_risk_service()
    success = await service.update_risk_status(risk_id, status)
    if not success:
        raise HTTPException(status_code=404, detail="Risk not found")

    return {"status": "success", "risk_id": risk_id, "new_status": status}


@router.get("/metrics/overview")
async def risk_metrics_overview() -> Dict[str, Any]:
    """Risk metrics overview."""
    service = get_risk_service()
    return await service.get_metrics()
