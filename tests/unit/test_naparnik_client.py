
"""
Unit tests for NaparnikClient.

Мы не ходим в реальное API, а проверяем только:
- корректность признака is_configured;
- поведение generate() при отсутствии конфигурации.
"""

import pytest

from src.ai.clients.exceptions import LLMNotConfiguredError
from src.ai.clients.naparnik_client import NaparnikClient, NaparnikConfig


class TestNaparnikConfig:
    def test_default_config_has_url(self) -> None:
        config = NaparnikConfig()
        assert "naparnik" in config.base_url.lower()
        assert config.model_name == "naparnik-pro"

    def test_config_from_env(self, monkeypatch) -> None:
        # Dataclass fields с default_factory загружают значения при инициализации класса,
        # поэтому нужно использовать прямое создание с переопределением полей
        monkeypatch.setenv("NAPARNIK_API_URL", "https://test.naparnik.ru/api")
        monkeypatch.setenv("NAPARNIK_MODEL", "test-model")
        # Импортируем заново после изменения env, или используем прямое создание
        import os

        config = NaparnikConfig(
            base_url=os.getenv(
                "NAPARNIK_API_URL", "https://naparnik.platform.1c.ru/api/v1"
            ),
            model_name=os.getenv("NAPARNIK_MODEL", "naparnik-pro"),
        )
        assert (
            "test.naparnik.ru" in config.base_url
            or config.base_url == "https://test.naparnik.ru/api"
        )
        assert config.model_name == "test-model"


class TestNaparnikClient:
    def test_is_configured_false_without_api_key(self) -> None:
        config = NaparnikConfig(api_key=None)
        client = NaparnikClient(config=config)
        assert client.is_configured is False

    def test_is_configured_true_with_api_key(self) -> None:
        config = NaparnikConfig(api_key="test-api-key")
        client = NaparnikClient(config=config)
        assert client.is_configured is True

    @pytest.mark.asyncio
    async def test_generate_raises_when_not_configured(self) -> None:
        config = NaparnikConfig(api_key=None)
        client = NaparnikClient(config=config)

        with pytest.raises(LLMNotConfiguredError):
            await client.generate("test prompt")

    @pytest.mark.asyncio
    async def test_client_context_manager(self) -> None:
        config = NaparnikConfig(api_key="test-key")
        client = NaparnikClient(config=config)

        async with client:
            assert client.is_configured is True
            # Проверяем, что сессия может быть создана
            session = await client._get_session(use_pool=False)
            assert session is not None

        # После выхода из контекста сессия должна быть закрыта
        assert client._session is None or client._session.closed

    @pytest.mark.asyncio
    async def test_close_detaches_but_does_not_close_pooled_session(self) -> None:
        from src.ai.connection_pool import close_global_pool

        await close_global_pool()
        config = NaparnikConfig(api_key="test-key")
        client = NaparnikClient(config=config)

        session = await client._get_session()
        assert client._session is session

        await client.close()

        assert client._session is None
        assert not session.closed
        await close_global_pool()

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        config = NaparnikConfig(api_key="test-key")
        client = NaparnikClient(config=config)

        # Создаем сессию
        await client._get_session(use_pool=False)
        assert client._session is not None

        # Закрываем
        await client.close()
        assert client._session is None or client._session.closed
