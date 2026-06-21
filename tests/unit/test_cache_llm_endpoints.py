"""In-process tests for the public operability endpoints implemented to close the rc0
audit gap: ``/api/v1/cache/metrics`` and ``/api/v1/llm/providers``.

Verifies the real contract (the same keys the legacy CLI/e2e suite asserts), that no
secrets leak from the provider listing, and that the legacy ``/api/...`` paths resolve via
the app's ``/api/*`` -> ``/api/v1/*`` rewrite. Runs in CI without any services.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import cache_api, llm_api


def _client(*modules) -> TestClient:
    app = FastAPI()
    for module in modules:
        app.include_router(module.router)
    return TestClient(app)


def test_cache_metrics_contract() -> None:
    resp = _client(cache_api).get("/api/v1/cache/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "type" in data or "error" in data  # matches the CLI contract


def test_cache_metrics_reports_real_stats() -> None:
    data = _client(cache_api).get("/api/v1/cache/metrics").json()
    assert data["type"] == "multi_layer_in_process"
    # real cache stats present (zero until used) — not fabricated
    assert "hits" in data and "misses" in data


def test_llm_providers_contract() -> None:
    resp = _client(llm_api).get("/api/v1/llm/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data and "total" in data
    assert isinstance(data["providers"], list)
    assert data["total"] == len(data["providers"])


def test_llm_providers_configured_and_leaks_no_secrets() -> None:
    data = _client(llm_api).get("/api/v1/llm/providers").json()
    # config/llm_providers.yaml ships providers -> total > 0 honestly
    assert data["total"] > 0
    allowed = {"name", "type", "priority", "enabled", "status", "self_hosted"}
    for provider in data["providers"]:
        assert set(provider).issubset(allowed)
        for secret_field in ("base_url", "metadata", "api_key", "token", "key"):
            assert secret_field not in provider


def test_endpoints_reachable_in_real_app_via_both_prefixes() -> None:
    # Mounted on the real app: canonical /api/v1/... AND the legacy /api/... path
    # (the latter through the /api/* -> /api/v1/* rewrite), both unauthenticated.
    from src.main import app as real_app

    client = TestClient(real_app)
    for path in (
        "/api/v1/cache/metrics",
        "/api/cache/metrics",
        "/api/v1/llm/providers",
        "/api/llm/providers",
    ):
        assert client.get(path).status_code == 200, path
