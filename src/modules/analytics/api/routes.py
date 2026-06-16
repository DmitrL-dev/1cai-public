from datetime import datetime
from typing import List

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from src.database import get_db_pool
from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.analytics.api.schemas import (
    CustomersData,
    DeveloperDashboardResponse,
    ExecutiveDashboardResponse,
    MetricData,
    OwnerDashboardResponse,
    PMDashboardResponse,
    ReportRequest,
    ReportResponse,
    RevenueData,
    SprintProgress,
)
from src.modules.analytics.application.service import AnalyticsService

logger = StructuredLogger(__name__).logger

router = APIRouter(tags=["Analytics & Dashboard"])

# Singleton service instance (for now)
analytics_service = AnalyticsService()

# ==================== ANALYTICS ENDPOINTS ====================


@router.post("/reports", response_model=ReportResponse)
async def generate_report(request: ReportRequest) -> ReportResponse:
    """Генерирует новый аналитический отчет.

    Args:
        request: Параметры отчета (заголовок, период, компоненты).

    Returns:
        ReportResponse: Сгенерированный отчет.
    """
    report = analytics_service.generate_report(
        title=request.title, period_days=request.period_days, components=request.components
    )
    return report


@router.get("/reports", response_model=List[ReportResponse])
async def get_reports() -> List[ReportResponse]:
    """Возвращает список всех сгенерированных отчетов.

    Returns:
        List[ReportResponse]: Список отчетов.
    """
    return analytics_service.get_all_reports()


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report(report_id: str) -> ReportResponse:
    """Получает конкретный отчет по ID.

    Args:
        report_id: ID отчета.

    Returns:
        ReportResponse: Данные отчета.

    Raises:
        HTTPException: Если отчет не найден (404).
    """
    report = analytics_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


# ==================== DASHBOARD ENDPOINTS ====================


@router.get("/dashboard/owner", response_model=OwnerDashboardResponse)
async def get_owner_dashboard() -> OwnerDashboardResponse:
    """Получает данные для дашборда владельца.

    Returns:
        OwnerDashboardResponse: Метрики выручки, клиентов и роста.
    """
    return OwnerDashboardResponse(
        revenue=RevenueData(this_month=150000.0, last_month=120000.0,
                            change_percent=25.0, trend="up"),
        customers=CustomersData(total=1250, new_this_month=45),
        growth_percent=12.0,
        system_status="healthy",
        recent_activities=[
            {
                "id": "1",
                "type": "deployment",
                "message": "VLM Server deployed successfully",
                "timestamp": datetime.now().isoformat(),
                "status": "success",
            },
        ],
    )


@router.get("/dashboard/executive", response_model=ExecutiveDashboardResponse)
async def get_executive_dashboard(db_pool: asyncpg.Pool = Depends(get_db_pool)) -> ExecutiveDashboardResponse:
    """Получает данные для исполнительного дашборда.

    Returns:
        ExecutiveDashboardResponse: KPI, ROI и метрики здоровья системы.
    """
    # Simplified implementation migrating from dashboard_api.py
    return ExecutiveDashboardResponse(
        id="exec",
        health={"status": "good", "message": "All systems operational"},
        roi=MetricData(value=150.0, change=10.0, trend="up", status="good"),
        users=MetricData(value=5000.0, change=500.0, trend="up", status="good"),
        growth=MetricData(value=15.0, change=2.0, trend="up", status="good"),
        revenue_trend=[
            {"month": "Jan", "revenue": 100000},
            {"month": "Feb", "revenue": 120000},
            {"month": "Mar", "revenue": 150000},
        ],
        alerts=[],
        objectives=[],
        metrics={"active_users": 5000},
    )


@router.get("/dashboard/pm", response_model=PMDashboardResponse)
async def get_pm_dashboard() -> PMDashboardResponse:
    """Получает данные для дашборда менеджера проектов.

    Returns:
        PMDashboardResponse: Статус проектов, спринтов и загрузка команды.
    """
    return PMDashboardResponse(
        id="pm",
        projects=[],
        projects_summary={"total": 3, "completed": 2},
        timeline=[],
        team_workload=[],
        sprint_progress=SprintProgress(
            sprint_number=42,
            tasks_done=11,
            tasks_total=11,
            progress=100.0,
            blockers=0,
            end_date=datetime.now().isoformat(),
        ),
    )


@router.get("/dashboard/developer", response_model=DeveloperDashboardResponse)
async def get_developer_dashboard() -> DeveloperDashboardResponse:
    """Получает данные для дашборда разработчика.

    Returns:
        DeveloperDashboardResponse: Задачи, код-ревью и статус сборки.
    """
    return DeveloperDashboardResponse(
        id="dev",
        name="Developer Dashboard",
        assigned_tasks=[],
        code_reviews=[],
        build_status={"status": "success",
            "last_build": datetime.now().isoformat(), "duration": "2m 30s"},
        code_quality={"coverage": 85.0, "bugs": 0},
    )
