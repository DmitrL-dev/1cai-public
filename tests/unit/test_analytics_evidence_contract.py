import pytest

from src.modules.analytics.api.routes import (
    get_developer_dashboard,
    get_executive_dashboard,
    get_owner_dashboard,
    get_pm_dashboard,
)
from src.modules.analytics.application.service import AnalyticsService
from src.modules.analytics.domain.models import MetricType


def test_analytics_roi_is_not_monetized_without_value_model():
    service = AnalyticsService()
    service.collect_metric("rentgen", MetricType.PERFORMANCE, 100)
    service.collect_metric("rentgen", MetricType.PERFORMANCE, 80)
    service.collect_metric("rentgen", MetricType.QUALITY, 70)
    service.collect_metric("rentgen", MetricType.QUALITY, 90)
    service.collect_metric("rentgen", MetricType.COST, 1000)

    result = service.calculate_roi("rentgen", period_days=30)

    assert result["roi_measured"] is False
    assert result["coverage"] == "missing_value_model"
    assert result["estimated_costs"] == 1000
    assert result["cost_savings"] == 0.0
    assert result["roi_percent"] == 0.0
    assert result["caveat"]


@pytest.mark.asyncio
async def test_analytics_dashboards_return_not_measured_contracts():
    owner = await get_owner_dashboard()
    executive = await get_executive_dashboard()
    pm = await get_pm_dashboard()
    developer = await get_developer_dashboard()
    serialized = "\n".join(
        [
            owner.model_dump_json(),
            executive.model_dump_json(),
            pm.model_dump_json(),
            developer.model_dump_json(),
        ]
    )

    assert owner.data_contract["coverage"] == "no_business_sources"
    assert owner.revenue.measured is False
    assert executive.roi.measured is False
    assert executive.revenue_trend == []
    assert pm.projects_summary["measured"] is False
    assert pm.sprint_progress.sprint_number == 0
    assert developer.build_status["measured"] is False
    assert developer.code_quality["coverage_measured"] is False
    assert "150000" not in serialized
    assert "5000" not in serialized
    assert "VLM Server deployed successfully" not in serialized
