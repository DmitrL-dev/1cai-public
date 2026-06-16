"""
Metrics API Routes
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.metrics.domain.models import MetricCollectionRequest
from src.modules.metrics.services.metrics_service import MetricsService

logger = StructuredLogger(__name__).logger

router = APIRouter(tags=["Metrics"])
limiter = Limiter(key_func=get_remote_address)


# Dependency
def get_metrics_service() -> MetricsService:
    return MetricsService()


@router.get("/health", summary="Check API health")
async def health_check() -> Dict[str, Any]:
    """Check Metrics API health"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "version": "1.0.0",
    }


@router.post("/collect", summary="Collect metrics")
@limiter.limit("100/minute")
async def collect_metrics(
    request: MetricCollectionRequest,
    service: MetricsService = Depends(get_metrics_service),
) -> Dict[str, Any]:
    """
    Collect metrics from services
    """
    try:
        return service.collect_metrics(request)
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", summary="Get metrics")
async def get_metrics(
    service_name: Optional[str] = None,
    metric_type: Optional[str] = None,
    hours_back: int = 24,
    limit: int = 1000,
    service: MetricsService = Depends(get_metrics_service),
) -> List[Dict[str, Any]]:
    """
    Get metrics with filtering
    """
    try:
        return service.get_metrics(
            service=service_name,
            metric_type=metric_type,
            hours_back=hours_back,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Error getting metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/{service_name}", summary="Get performance metrics")
async def get_performance_metrics(
    service_name: str,
    hours_back: int = 1,
    service: MetricsService = Depends(get_metrics_service),
) -> Dict[str, Any]:
    """
    Get performance metrics for service
    """
    try:
        return service.get_performance_metrics(service_name=service_name, hours_back=hours_back)
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard", summary="Dashboard overview")
async def get_dashboard_overview(
    service: MetricsService = Depends(get_metrics_service),
) -> Dict[str, Any]:
    """
    Get dashboard overview
    """
    try:
        return service.get_dashboard_overview()
    except Exception as e:
        logger.error(f"Error getting dashboard overview: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts", summary="Get active alerts")
async def get_alerts(
    service: MetricsService = Depends(get_metrics_service),
) -> List[Dict[str, Any]]:
    """
    Get active alerts
    """
    try:
        return service.get_alerts()
    except Exception as e:
        logger.error(f"Error getting alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear", summary="Clear old metrics")
async def clear_old_metrics(
    days_back: int = 30,
    service: MetricsService = Depends(get_metrics_service),
) -> Dict[str, Any]:
    """
    Clear old metrics
    """
    try:
        count = service.clear_old_metrics(days_back=days_back)
        return {"success": True, "cleared_count": count}
    except Exception as e:
        logger.error(f"Error clearing metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", summary="Get stats")
async def get_stats(
    service: MetricsService = Depends(get_metrics_service),
) -> Dict[str, Any]:
    """
    Get general stats
    """
    try:
        return service.get_stats()
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
