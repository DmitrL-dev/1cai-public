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
        title=request.title,
        period_days=request.period_days,
        components=request.components,
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
        revenue=RevenueData(
            this_month=0.0,
            last_month=0.0,
            change_percent=0.0,
            trend="unknown",
            measured=False,
            caveat="Revenue source is not connected.",
        ),
        customers=CustomersData(
            total=0,
            new_this_month=0,
            measured=False,
            caveat="Customer source is not connected.",
        ),
        growth_percent=0.0,
        system_status="not_measured",
        recent_activities=[],
        data_contract={
            "mode": "analytics_dashboard_evidence_contract",
            "coverage": "no_business_sources",
            "generated_at": datetime.utcnow().isoformat(),
        },
        caveats=[
            "Owner dashboard avoids synthetic revenue, customer and activity data."
        ],
    )


@router.get("/dashboard/executive", response_model=ExecutiveDashboardResponse)
async def get_executive_dashboard(
    db_pool: asyncpg.Pool = Depends(get_db_pool),
) -> ExecutiveDashboardResponse:
    """Получает данные для исполнительного дашборда.

    Returns:
        ExecutiveDashboardResponse: KPI, ROI и метрики здоровья системы.
    """
    return ExecutiveDashboardResponse(
        id="exec",
        health={"status": "unknown", "message": "Health source is not connected"},
        roi=MetricData(
            value=0.0,
            change=0.0,
            trend="unknown",
            status="not_measured",
            measured=False,
            caveat="ROI requires cost and value evidence.",
        ),
        users=MetricData(
            value=0.0,
            change=0.0,
            trend="unknown",
            status="not_measured",
            measured=False,
            caveat="User analytics source is not connected.",
        ),
        growth=MetricData(
            value=0.0,
            change=0.0,
            trend="unknown",
            status="not_measured",
            measured=False,
            caveat="Growth requires historical snapshots.",
        ),
        revenue_trend=[],
        alerts=[],
        objectives=[],
        metrics={},
        data_contract={
            "mode": "analytics_dashboard_evidence_contract",
            "coverage": "no_executive_sources",
            "generated_at": datetime.utcnow().isoformat(),
        },
        caveats=[
            "Executive analytics endpoint avoids synthetic KPI, ROI, user and revenue values."
        ],
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
        projects_summary={"total": 0, "completed": 0, "measured": False},
        timeline=[],
        team_workload=[],
        sprint_progress=SprintProgress(
            sprint_number=0,
            tasks_done=0,
            tasks_total=0,
            progress=0.0,
            blockers=0,
            end_date="",
        ),
        data_contract={
            "mode": "analytics_dashboard_evidence_contract",
            "coverage": "no_project_sources",
        },
        caveats=["PM dashboard requires project tracker evidence."],
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
        build_status={"status": "not_measured", "measured": False},
        code_quality={"coverage": 0.0, "coverage_measured": False, "bugs": 0},
        ai_suggestions=[],
        data_contract={
            "mode": "analytics_dashboard_evidence_contract",
            "coverage": "no_developer_sources",
        },
        caveats=[
            "Developer analytics endpoint requires issue, VCS, CI and quality evidence."
        ],
    )
