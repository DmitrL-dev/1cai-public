"""
Unit tests for GigaChatClient.

Мы не ходим в реальное API, а проверяем только:
- корректность признака is_configured;
- поведение generate() при отсутствии конфигурации.
"""

import pytest

from src.ai.clients.exceptions import LLMNotConfiguredError
from src.ai.clients.gigachat_client import GigaChatClient, GigaChatConfig


class TestGigaChatConfig:
    def test_default_config_has_urls(self) -> None:
        config = GigaChatConfig()
        assert "gigachat" in config.base_url.lower()
        assert "oauth" in config.token_url.lower()


class TestGigaChatClient:
    def test_is_configured_false_without_credentials(self) -> None:
        config = GigaChatConfig(
            client_id=None,
            client_secret=None,
            access_token=None,
        )
        client = GigaChatClient(config=config)
        assert client.is_configured is False

    def test_is_configured_true_with_access_token(self) -> None:
        config = GigaChatConfig(access_token="test-token")
        client = GigaChatClient(config=config)
        assert client.is_configured is True

    def test_is_configured_true_with_client_credentials(self) -> None:
        config = GigaChatConfig(
            client_id="id",
            client_secret="secret",
            token_url="https://example.com/oauth",
        )
        client = GigaChatClient(config=config)
        assert client.is_configured is True

    @pytest.mark.asyncio
    async def test_generate_raises_when_not_configured(self) -> None:
        config = GigaChatConfig(
            client_id=None,
            client_secret=None,
            access_token=None,
        )
        client = GigaChatClient(config=config)

        with pytest.raises(LLMNotConfiguredError):
            await client.generate("test")
