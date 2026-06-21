from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import (
    business_case_api,
    enterprise_trust_center_api,
    value_packs_api,
    vendor_portfolio_api,
)


def _executive():
    return {
        "decision": {"status": "ready", "score": 87, "headline": "Enterprise value path is ready."},
        "kpis": {"red_areas": 0, "review_queue": 1},
        "risk_summary": {"high_hotspots": 0},
    }


def _client(module) -> TestClient:
    app = FastAPI()
    app.include_router(module.router)
    return TestClient(app)


def _assert_fast_contract(payload: dict, expected_keys: set[str]) -> None:
    assert payload["source"] == "management-fast-pulse"
    assert payload["purchase_status"] == "ready"
    assert payload["three_year_ai_rent"] == "4 320 000 RUB"
    assert payload["status"] == "ready"
    assert payload["score"] == 87
    assert expected_keys <= set(payload)


def _assert_liveness_only(payload: dict, forbidden_keys: set[str]) -> None:
    # business_case / value_packs /health are liveness-only by design (honesty
    # review #30/#31): a fast health check has no honest cheap source for these
    # modules' business figures (the real numbers come from the deep builder a
    # fast check must NOT call), and the old hardcoded values contradicted /build.
    # So liveness must be number-free and must NOT expose the fast-pulse contract.
    assert payload.get("status") == "ok"
    assert "source" not in payload
    assert "score" not in payload
    assert "purchase_status" not in payload
    assert "three_year_ai_rent" not in payload
    assert not (forbidden_keys & set(payload))


def _fail_deep_build(*args, **kwargs):
    raise AssertionError("health must not call deep enterprise/value builders")


def test_business_case_health_is_fast(monkeypatch):
    # /health stays fast: assert it calls NONE of the deep builders and returns
    # liveness only (no fabricated business numbers). raising=False keeps the test
    # robust if an unused builder import was dropped from the module.
    monkeypatch.setattr(business_case_api, "store_or_none", lambda: None, raising=False)
    monkeypatch.setattr(business_case_api, "build_executive_dashboard", _fail_deep_build, raising=False)
    monkeypatch.setattr(business_case_api, "build_platform_doctor", _fail_deep_build, raising=False)
    monkeypatch.setattr(business_case_api, "build_intake_plan", _fail_deep_build, raising=False)
    monkeypatch.setattr(business_case_api, "build_value_packs", _fail_deep_build, raising=False)
    monkeypatch.setattr(business_case_api, "build_vendor_portfolio", _fail_deep_build, raising=False)
    monkeypatch.setattr(business_case_api, "build_business_case", _fail_deep_build, raising=False)

    response = _client(business_case_api).get("/api/v1/business-case/health")

    assert response.status_code == 200
    _assert_liveness_only(response.json(), {"first_year_visible_value", "levers"})


def test_vendor_portfolio_health_is_fast(monkeypatch):
    monkeypatch.setattr(vendor_portfolio_api, "store_or_none", lambda: None)
    monkeypatch.setattr(vendor_portfolio_api, "build_executive_dashboard", lambda *args, **kwargs: _executive())
    monkeypatch.setattr(vendor_portfolio_api, "build_platform_doctor", _fail_deep_build)
    monkeypatch.setattr(vendor_portfolio_api, "build_intake_plan", _fail_deep_build)
    monkeypatch.setattr(vendor_portfolio_api, "build_vendor_portfolio", _fail_deep_build)

    response = _client(vendor_portfolio_api).get("/api/v1/vendor-portfolio/health")

    assert response.status_code == 200
    _assert_fast_contract(response.json(), {"work_packages", "portfolio_segments"})


def test_value_packs_health_is_fast(monkeypatch):
    monkeypatch.setattr(value_packs_api, "store_or_none", lambda: None, raising=False)
    monkeypatch.setattr(value_packs_api, "build_executive_dashboard", _fail_deep_build, raising=False)
    monkeypatch.setattr(value_packs_api, "build_value_packs", _fail_deep_build, raising=False)

    response = _client(value_packs_api).get("/api/v1/value-packs/health")

    assert response.status_code == 200
    _assert_liveness_only(response.json(), {"packs", "pilot_ready"})


def test_enterprise_trust_center_health_is_fast(monkeypatch):
    monkeypatch.setattr(enterprise_trust_center_api, "store_or_none", lambda: None)
    monkeypatch.setattr(enterprise_trust_center_api, "build_executive_dashboard", lambda *args, **kwargs: _executive())
    monkeypatch.setattr(enterprise_trust_center_api, "_quick_health_report", _fail_deep_build)
    monkeypatch.setattr(enterprise_trust_center_api, "_build_report", _fail_deep_build)

    response = _client(enterprise_trust_center_api).get("/api/v1/enterprise-trust-center/health")

    assert response.status_code == 200
    _assert_fast_contract(
        response.json(),
        {"controls", "failed_controls", "questionnaire_status", "questionnaire_blocked"},
    )
