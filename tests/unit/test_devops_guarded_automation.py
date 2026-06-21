import pytest

from src.modules.devops_api.services.devops_service import (
    AIEvolutionService,
    DevOpsService,
)


@pytest.mark.asyncio
async def test_devops_compose_analysis_returns_route_contract(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        """
services:
  web:
    image: nginx:1.25
    ports:
      - "8080:80"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost"]
  worker:
    image: busybox
    depends_on:
      - web
""".strip(),
        encoding="utf-8",
    )

    result = await DevOpsService().analyze_infrastructure(str(compose))

    assert result["status"] == "success"
    assert result["static_analysis"]["mode"] == "offline-static"
    assert result["static_analysis"]["service_count"] == 2
    assert result["static_analysis"]["healthcheck_coverage"] == 0.5
    assert result["runtime_containers"] == []
    assert result["services_status"]["web"]["has_healthcheck"] is True
    assert result["services_status"]["worker"]["depends_on"] == ["web"]
    assert any(item["target"] == "worker" for item in result["recommendations"])


@pytest.mark.asyncio
async def test_guarded_evolution_metrics_are_disabled_by_policy():
    service = AIEvolutionService()

    evolution = await service.evolve(force=True)
    status = await service.get_status()
    metrics = await service.get_metrics()

    assert evolution["status"] == "disabled_by_policy"
    assert evolution["metrics"]["force_requested"] is True
    assert status["approved_route"] == "/safe-autopilot"
    assert metrics["status"] == "disabled_by_policy"
    assert metrics["metrics"]["autonomous_write_enabled"] is False
