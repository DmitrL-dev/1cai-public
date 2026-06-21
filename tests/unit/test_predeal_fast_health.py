from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import (
    demo_command_center_api,
    guided_demo_api,
    pilot_launchpad_api,
    scenario_hub_api,
)


def _executive():
    return {
        "decision": {"status": "ready", "score": 88, "headline": "Demo path is ready."},
        "kpis": {"red_areas": 0, "review_queue": 0},
        "risk_summary": {"high_hotspots": 0},
    }


def _assert_fast_health(module, path: str, expected_keys: set[str], monkeypatch):
    monkeypatch.setattr(module, "store_or_none", lambda: None)
    monkeypatch.setattr(module, "build_executive_dashboard", lambda *args, **kwargs: _executive())

    def fail_deep_build(_req):
        raise AssertionError("health must not call deep pre-deal build")

    monkeypatch.setattr(module, "_build_report", fail_deep_build)

    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app)

    response = client.get(path)

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "management-fast-pulse"
    assert payload["purchase_status"] == "ready"
    assert payload["three_year_ai_rent"] == "4 320 000 RUB"
    assert expected_keys <= set(payload)


def test_pilot_launchpad_health_is_fast(monkeypatch):
    _assert_fast_health(
        pilot_launchpad_api,
        "/api/v1/pilot-launchpad/health",
        {"offers", "acceptance_checks", "activation_ready", "activation_gates"},
        monkeypatch,
    )


def test_demo_command_center_health_is_fast(monkeypatch):
    _assert_fast_health(
        demo_command_center_api,
        "/api/v1/demo-command-center/health",
        {"stages", "total_minutes"},
        monkeypatch,
    )


def test_guided_demo_health_is_fast(monkeypatch):
    _assert_fast_health(
        guided_demo_api,
        "/api/v1/guided-demo/health",
        {"steps", "total_minutes"},
        monkeypatch,
    )


def test_scenario_hub_health_is_fast(monkeypatch):
    _assert_fast_health(
        scenario_hub_api,
        "/api/v1/scenario-hub/health",
        {"scenarios", "roles", "recommended"},
        monkeypatch,
    )
