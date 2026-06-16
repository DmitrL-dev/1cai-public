
"""
Unit tests for YandexGPTClient.

Покрываем только конфигурацию и поведение при отсутствии кредов.
"""

import pytest

from src.ai.clients.exceptions import LLMNotConfiguredError
from src.ai.clients.yandexgpt_client import YandexGPTClient, YandexGPTConfig


class TestYandexGPTConfig:
    def test_default_model_name(self) -> None:
        config = YandexGPTConfig()
        assert "yandexgpt" in config.model_name


class TestYandexGPTClient:
    def test_is_configured_false_without_credentials(self) -> None:
        config = YandexGPTConfig(api_key=None, folder_id=None)
        client = YandexGPTClient(config=config)
        assert client.is_configured is False

    def test_is_configured_true_with_credentials(self) -> None:
        config = YandexGPTConfig(api_key="key", folder_id="folder")
        client = YandexGPTClient(config=config)
        assert client.is_configured is True

    @pytest.mark.asyncio
    async def test_generate_raises_when_not_configured(self) -> None:
        config = YandexGPTConfig(api_key=None, folder_id=None)
        client = YandexGPTClient(config=config)

        with pytest.raises(LLMNotConfiguredError):
            await client.generate("prompt")
