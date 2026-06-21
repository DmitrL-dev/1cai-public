
"""
Unit tests for LLM Gateway
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.services.llm_gateway import LLMGateway
from src.services.llm_provider_manager import LLMProviderManager, ProviderConfig


@pytest.fixture
def mock_provider_manager():
    """Mock LLM Provider Manager"""
    manager = Mock(spec=LLMProviderManager)
    manager.providers = {
        "gigachat": ProviderConfig(
            name="gigachat",
            provider_type="remote",
            priority=60,
            base_url="https://gigachat.devices.sberbank.ru/api",
            enabled=True,
            metadata={"models": [{"name": "gigachat"}]},
        ),
        "yandex-gpt": ProviderConfig(
            name="yandex-gpt",
            provider_type="remote",
            priority=55,
            base_url="https://llm.api.cloud.yandex.net",
            enabled=True,
            metadata={"models": [{"name": "yandexgpt-lite"}]},
        ),
    }
    manager.fallback_matrix = {
        "developer": {"primary": "gigachat", "chain": ["yandex-gpt"]}
    }
    manager.health_config = {
        "interval_seconds": 60,
        "failure_threshold": 3,
        "recovery_threshold": 2,
    }
    manager.has_configuration = Mock(return_value=True)
    manager.get_provider = Mock(side_effect=lambda name: manager.providers.get(name))
    manager.get_fallback_chain = Mock(
        side_effect=lambda role: manager.fallback_matrix.get(role)
    )
    manager.get_active_provider = Mock(return_value=None)
    manager.available_providers = Mock(return_value=list(manager.providers.values()))
    return manager


@pytest.fixture
def gateway(mock_provider_manager):
    """Create LLM Gateway instance"""
    return LLMGateway(
        manager=mock_provider_manager,
        enable_cache=False,
        enable_health_monitoring=False,
        enable_circuit_breaker=False,
    )


@pytest.mark.asyncio
async def test_gateway_initialization(gateway):
    """Test gateway initialization"""
    assert gateway.manager is not None
    assert gateway.simulation_config is not None


@pytest.mark.asyncio
async def test_no_provider_returns_offline_fallback_not_placeholder():
    manager = Mock(spec=LLMProviderManager)
    manager.has_configuration = Mock(return_value=True)
    manager.get_active_provider = Mock(return_value=None)
    manager.get_fallback_chain = Mock(return_value=None)
    manager.get_provider = Mock(return_value=None)

    gateway = LLMGateway(
        manager=manager,
        enable_cache=False,
        enable_health_monitoring=False,
        enable_circuit_breaker=False,
    )

    response = await gateway.generate("Explain local Rentgen value")

    assert response.response.startswith("[LLM offline fallback]")
    assert response.metadata["offline"] is True
    assert response.metadata["fallback"] is True
    assert response.metadata["fallback_reason"] == "no_provider_available"
    assert "placeholder" not in response.metadata
    assert "placeholder" not in response.response.lower()


@pytest.mark.asyncio
async def test_build_provider_chain(gateway):
    """Test building provider chain"""
    chain = gateway._build_provider_chain("developer")
    assert len(chain) > 0
    assert chain[0].name == "gigachat"


@pytest.mark.asyncio
async def test_resolve_model_name(gateway):
    """Test model name resolution"""
    provider = gateway.manager.providers["gigachat"]
    model_name = gateway._resolve_model_name(provider)
    assert model_name == "gigachat"


@pytest.mark.asyncio
async def test_simulation_mode(gateway):
    """Test simulation mode"""
    gateway.simulation_config = {
        "mode": "simulation",
        "scenarios": [
            {
                "name": "test-scenario",
                "match": {"role": "developer"},
                "response": {
                    "provider": "test-provider",
                    "model": "test-model",
                    "text": "Test response",
                },
            }
        ],
    }

    response = await gateway.generate("test prompt", role="developer")
    assert response.provider == "test-provider"
    assert response.response == "Test response"


@pytest.mark.asyncio
async def test_call_gigachat_provider(gateway):
    """Test calling GigaChat provider"""
    provider = gateway.manager.providers["gigachat"]

    mock_client = AsyncMock()
    mock_client.generate = AsyncMock(
        return_value={
            "text": "Test response",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            "raw": {},
        }
    )
    gateway.get_client = Mock(return_value=mock_client)

    response = await gateway._call_provider(provider, "test prompt")

    gateway.get_client.assert_called_once_with("gigachat")
    assert response.provider == "gigachat"
    assert response.response == "Test response"
    assert "usage" in response.metadata


@pytest.mark.asyncio
async def test_call_yandexgpt_provider(gateway):
    """Test calling YandexGPT provider"""
    provider = gateway.manager.providers["yandex-gpt"]

    mock_client = AsyncMock()
    mock_client.generate = AsyncMock(
        return_value={"text": "Yandex response", "usage": {}, "raw": {}}
    )
    gateway.get_client = Mock(return_value=mock_client)

    response = await gateway._call_provider(provider, "test prompt")

    gateway.get_client.assert_called_once_with("yandex-gpt")
    assert response.provider == "yandex-gpt"
    assert response.response == "Yandex response"


@pytest.mark.asyncio
async def test_fallback_chain(gateway):
    """Test fallback to next provider on failure"""
    mock_gigachat = AsyncMock()
    mock_gigachat.generate = AsyncMock(side_effect=Exception("Provider error"))

    mock_yandex = AsyncMock()
    mock_yandex.generate = AsyncMock(
        return_value={"text": "Fallback response", "usage": {}, "raw": {}}
    )

    gateway.get_client = Mock(
        side_effect=lambda name: (
            mock_gigachat if name == "gigachat" else mock_yandex
        )
    )

    response = await gateway.generate("test prompt", role="developer")

    assert response.provider == "yandex-gpt"
    assert response.response == "Fallback response"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Superseded by get_client-based offline fallback contract test.")
async def test_offline_fallback(gateway):
    """Test offline fallback when all providers fail"""
    with patch(
        "src.services.llm_gateway._get_gigachat_client"
    ) as mock_get_gigachat, patch(
        "src.services.llm_gateway._get_yandexgpt_client"
    ) as mock_get_yandex, patch(
        "src.services.llm_gateway._get_ollama_client"
    ) as mock_get_ollama:
        # All providers fail
        mock_gigachat = AsyncMock()
        mock_gigachat.is_configured = True
        mock_gigachat.generate = AsyncMock(side_effect=Exception("Error"))
        mock_get_gigachat.return_value = mock_gigachat

        mock_yandex = AsyncMock()
        mock_yandex.is_configured = True
        mock_yandex.generate = AsyncMock(side_effect=Exception("Error"))
        mock_get_yandex.return_value = mock_yandex

        # Ollama also fails
        mock_ollama = AsyncMock()
        mock_ollama.generate = AsyncMock(side_effect=Exception("Error"))
        mock_get_ollama.return_value = mock_ollama

        response = await gateway.generate("test prompt")

        assert response.provider == "offline"
        assert (
            "недоступны" in response.response.lower()
            or "unavailable" in response.response.lower()
        )


@pytest.mark.asyncio
async def test_offline_fallback_uses_get_client_contract(gateway):
    """Test offline fallback when all role providers and Ollama fail."""
    mock_gigachat = AsyncMock()
    mock_gigachat.generate = AsyncMock(side_effect=Exception("Error"))

    mock_yandex = AsyncMock()
    mock_yandex.generate = AsyncMock(side_effect=Exception("Error"))

    mock_ollama = AsyncMock()
    mock_ollama.generate = AsyncMock(side_effect=Exception("Error"))

    gateway.get_client = Mock(
        side_effect=lambda name: {
            "gigachat": mock_gigachat,
            "yandex-gpt": mock_yandex,
            "ollama": mock_ollama,
        }.get(name)
    )

    response = await gateway.generate("test prompt", role="developer")

    assert response.provider == "offline"
    assert response.metadata["offline"] is True
    assert response.metadata["fallback"] is True
    assert response.metadata["fallback_reason"] == "all_providers_unavailable"
    assert response.response


@pytest.mark.asyncio
async def test_cache_integration(gateway):
    """Test cache integration"""
    gateway.cache = Mock()
    gateway.cache.get = Mock(return_value=None)
    gateway.cache.set = Mock()

    mock_client = AsyncMock()
    mock_client.generate = AsyncMock(
        return_value={"text": "Cached response", "usage": {}, "raw": {}}
    )
    gateway.get_client = Mock(return_value=mock_client)

    await gateway.generate("test prompt", role="developer")

    # Check cache was called
    assert gateway.cache.get.called
    assert gateway.cache.set.called


def test_build_cache_key(gateway):
    """Test cache key generation"""
    key1 = gateway._build_cache_key("test", "developer", 0.7, 2048, None)
    key2 = gateway._build_cache_key("test", "developer", 0.7, 2048, None)
    key3 = gateway._build_cache_key("different", "developer", 0.7, 2048, None)

    assert key1 == key2  # Same inputs = same key
    assert key1 != key3  # Different inputs = different key
