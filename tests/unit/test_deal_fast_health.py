from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import (
    board_pack_api,
    commercial_offer_studio_api,
    killer_demo_api,
    outcome_ledger_api,
)


def _executive():
    return {
        "decision": {"status": "ready", "score": 86, "headline": "Buyer path is ready."},
        "kpis": {"red_areas": 0, "review_queue": 1},
        "risk_summary": {"high_hotspots": 0},
    }


def _assert_fast_health(module, path: str, expected_keys: set[str], monkeypatch):
    monkeypatch.setattr(module, "store_or_none", lambda: None)
    monkeypatch.setattr(module, "build_executive_dashboard", lambda *args, **kwargs: _executive())

    def fail_deep_build(_req):
        raise AssertionError("health must not call deep deal build")

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


def test_board_pack_health_is_fast(monkeypatch):
    _assert_fast_health(
        board_pack_api,
        "/api/v1/board-pack/health",
        {"decision_items", "recommended_offer"},
        monkeypatch,
    )


def test_commercial_offer_health_is_fast(monkeypatch):
    _assert_fast_health(
        commercial_offer_studio_api,
        "/api/v1/commercial-offer-studio/health",
        {"offers", "deal_risks"},
        monkeypatch,
    )


def test_outcome_ledger_health_is_fast(monkeypatch):
    _assert_fast_health(
        outcome_ledger_api,
        "/api/v1/outcome-ledger/health",
        {"outcome_tiles", "success_metrics", "governance_gates", "governance_windows"},
        monkeypatch,
    )


def test_killer_demo_health_is_fast(monkeypatch):
    _assert_fast_health(
        killer_demo_api,
        "/api/v1/killer-demo/health",
        {"stages", "demo_modes", "close_ready", "checkout_gates"},
        monkeypatch,
    )
