import pytest

from src.modules.dashboard.services.developer_service import DeveloperService
from src.modules.dashboard.services.executive_service import ExecutiveService


class FakeExecutiveConnection:
    async def fetchval(self, query: str):
        normalized = " ".join(query.split()).lower()
        if normalized == "select 1":
            return 1
        if "from users" in normalized:
            return 7
        return 0


@pytest.mark.asyncio
async def test_executive_dashboard_does_not_emit_synthetic_money_or_growth():
    service = ExecutiveService()

    dashboard = await service.get_dashboard(FakeExecutiveConnection())
    serialized = str(dashboard)

    assert dashboard["data_contract"]["mode"] == "dashboard_evidence_contract"
    assert dashboard["roi"]["measured"] is False
    assert dashboard["roi"]["value"] == 0
    assert dashboard["users"]["value"] == 7
    assert dashboard["growth"]["measured"] is False
    assert dashboard["revenue_trend"] == []
    assert dashboard["alerts"] == []
    assert dashboard["objectives"] == []
    assert dashboard["usage_stats"]["measured"] is False
    assert "45200" not in serialized
    assert "Budget at 85%" not in serialized


@pytest.mark.asyncio
async def test_developer_dashboard_does_not_emit_synthetic_tasks_or_quality():
    service = DeveloperService()

    dashboard = await service.get_dashboard()
    serialized = str(dashboard)

    assert dashboard["data_contract"]["coverage"] == "no_developer_sources"
    assert dashboard["assigned_tasks"] == []
    assert dashboard["code_reviews"] == []
    assert dashboard["build_status"]["measured"] is False
    assert dashboard["code_quality"]["coverage_measured"] is False
    assert dashboard["ai_suggestions"] == []
    assert "Implement user authentication" not in serialized
    assert "Optimize database query" not in serialized
