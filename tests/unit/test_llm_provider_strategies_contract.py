import pytest

from src.ai.strategies import llm_providers


class UnconfiguredClient:
    is_configured = False

    async def generate(self, **kwargs):
        raise AssertionError("generate must not be called without configuration")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("strategy_cls", "client_name"),
    [
        (llm_providers.GigaChatStrategy, "GigaChatClient"),
        (llm_providers.YandexGPTStrategy, "YandexGPTClient"),
        (llm_providers.NaparnikStrategy, "NaparnikClient"),
        (llm_providers.OllamaStrategy, "OllamaClient"),
        (llm_providers.TabnineStrategy, "TabnineClient"),
    ],
)
async def test_llm_provider_strategy_returns_offline_contract_when_not_configured(
    monkeypatch, strategy_cls, client_name
):
    monkeypatch.setattr(
        llm_providers,
        client_name,
        lambda config: UnconfiguredClient(),
    )

    strategy = strategy_cls()
    result = await strategy.execute("Проверь запрос", {"role": "architect"})

    assert result["status"] == "llm_provider_not_configured"
    assert result["mode"] == "offline_provider_contract"
    assert result["coverage"] == "no_credentials"
    assert result["response"] == ""
    assert result["context_keys"] == ["role"]
    assert result["caveats"]
