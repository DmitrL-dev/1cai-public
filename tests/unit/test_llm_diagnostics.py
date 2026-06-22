import httpx

from scripts.diagnostics import check_llm_endpoints as diag


def test_iterate_providers_filters_subset():
    providers = {"openai": {}, "gigachat": {}}
    names = [name for name, _ in diag.iterate_providers(providers, ["OPENAI"])]
    assert names == ["openai"]


def test_check_provider_skips_without_urls():
    checker = diag.LLMEndpointChecker()
    result = checker.check_provider("local", {})
    assert result.status == "skipped"
    assert result.message == "No base_url/health_url provided"


def test_check_provider_handles_request_error(monkeypatch):
    checker = diag.LLMEndpointChecker(timeout=0.1)

    class DummyClient:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def request(self, *_):
            raise httpx.RequestError("boom", request=None)

    monkeypatch.setattr(diag.httpx, "Client", DummyClient)
    result = checker.check_provider("openai", {"base_url": "http://example.com"})
    assert result.status == "error"
    assert "boom" in result.message


def test_check_provider_success(monkeypatch):
    checker = diag.LLMEndpointChecker(timeout=0.1)

    class DummyResponse:
        status_code = 200
        text = ""

        class Elapsed:
            def total_seconds(self):
                return 0.01

        elapsed = Elapsed()

    class DummyClient:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def request(self, *_):
            return DummyResponse()

    monkeypatch.setattr(diag.httpx, "Client", DummyClient)
    result = checker.check_provider("openai", {"base_url": "http://example.com"})
    assert result.status == "ok"
    assert result.http_status == 200
    assert result.latency_ms is not None
