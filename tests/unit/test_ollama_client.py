
"""
Unit tests for OllamaClient
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ai.clients.exceptions import LLMCallError, LLMNotConfiguredError
from src.ai.clients.ollama_client import OllamaClient, OllamaConfig


class AsyncContextManagerMock:
    """Simple async context manager returning provided value."""

    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class TestOllamaConfig:
    """Тесты для OllamaConfig."""

    def test_config_from_env(self, monkeypatch):
        """Проверка загрузки конфигурации из переменных окружения."""
        monkeypatch.setenv("OLLAMA_HOST", "http://test.ollama:8080")
        monkeypatch.setenv("OLLAMA_MODEL", "test-model")
        monkeypatch.setenv("OLLAMA_TIMEOUT", "120")
        monkeypatch.setenv("OLLAMA_VERIFY_SSL", "false")

        # Создаём конфигурацию явно, так как dataclass defaults загружаются при определении класса
        import os

        config = OllamaConfig(
            base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model_name=os.getenv("OLLAMA_MODEL", "llama3"),
            timeout=int(os.getenv("OLLAMA_TIMEOUT", "60")),
            verify_ssl=os.getenv("OLLAMA_VERIFY_SSL", "true").lower() != "false",
        )
        assert config.base_url == "http://test.ollama:8080"
        assert config.model_name == "test-model"
        assert config.timeout == 120
        assert config.verify_ssl is False

    def test_config_defaults(self):
        """Проверка значений по умолчанию."""
        config = OllamaConfig()
        assert config.base_url == "http://localhost:11434"
        assert config.model_name == "llama3"
        assert config.timeout == 60
        assert config.verify_ssl is True
        assert config.max_retries == 3


class TestOllamaClient:
    """Тесты для OllamaClient."""

    @pytest.mark.asyncio
    async def test_is_configured(self):
        """Проверка свойства is_configured."""
        client = OllamaClient(OllamaConfig(base_url="http://localhost:11434"))
        assert client.is_configured is True

        client_no_config = OllamaClient(OllamaConfig(base_url=""))
        assert client_no_config.is_configured is False

    @pytest.mark.asyncio
    async def test_list_models_success(self):
        """Проверка успешного получения списка моделей."""
        # Создаем правильный мок для aiohttp response
        mock_response_data = {
            "models": [
                {"name": "llama3"},
                {"name": "mistral"},
                {"name": "codellama"},
            ]
        }

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="")
        mock_response.json = AsyncMock(return_value=mock_response_data)

        mock_session = AsyncMock()
        # Fix: get is a sync method returning an async context manager
        mock_session.get = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)
        mock_session.closed = False

        client = OllamaClient(OllamaConfig(base_url="http://localhost:11434"))

        # Мокаем _get_session чтобы вернуть нашу мок-сессию
        async def mock_get_session():
            return mock_session

        client._get_session = mock_get_session

        models = await client.list_models()
        assert len(models) == 3
        assert "llama3" in models
        assert "mistral" in models
        assert "codellama" in models

        await client.close()

    @pytest.mark.asyncio
    async def test_list_models_error(self):
        """Проверка обработки ошибки при получении списка моделей."""
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        mock_session = AsyncMock()
        # Fix: get is a sync method returning an async context manager
        mock_session.get = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)
        mock_session.closed = False

        client = OllamaClient(OllamaConfig(base_url="http://localhost:11434"))

        async def mock_get_session():
            return mock_session

        client._get_session = mock_get_session

        with pytest.raises(LLMCallError) as exc_info:
            await client.list_models()

        assert "HTTP 500" in str(exc_info.value)
        await client.close()

    @pytest.mark.asyncio
    async def test_list_models_not_configured(self):
        """Проверка ошибки при отсутствии конфигурации."""
        client = OllamaClient(OllamaConfig(base_url=""))
        with pytest.raises(LLMNotConfiguredError):
            await client.list_models()

    @pytest.mark.asyncio
    async def test_check_model_available_success(self):
        """Проверка успешной проверки доступности модели."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="")
        mock_response.json = AsyncMock(
            return_value={
                "models": [
                    {"name": "llama3"},
                    {"name": "mistral"},
                ]
            }
        )
        mock_session = AsyncMock()
        # Fix: get is a sync method returning an async context manager
        mock_session.get = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = OllamaClient(OllamaConfig(base_url="http://localhost:11434"))

        async def mock_get_session():
            return mock_session

        client._get_session = mock_get_session

        assert await client.check_model_available("llama3") is True
        assert await client.check_model_available("codellama") is False

        await client.close()

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Проверка успешной генерации текста."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="")
        mock_response.json = AsyncMock(
            return_value={
                "response": "Generated text",
                "prompt_eval_count": 10,
                "eval_count": 20,
            }
        )
        mock_session = AsyncMock()
        # Fix: post is a sync method returning an async context manager
        mock_session.post = MagicMock()
        mock_session.post.return_value = AsyncContextManagerMock(mock_response)
        mock_session.closed = False

        client = OllamaClient(OllamaConfig(base_url="http://localhost:11434"))

        async def mock_get_session():
            return mock_session

        client._get_session = mock_get_session

        result = await client.generate("Test prompt", model_name="llama3")

        assert result["text"] == "Generated text"
        assert result["usage"]["prompt_tokens"] == 10
        assert result["usage"]["completion_tokens"] == 20
        assert result["usage"]["total_tokens"] == 30

        await client.close()

    @pytest.mark.asyncio
    async def test_generate_with_system_prompt(self):
        """Проверка генерации с системным промптом."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="")
        mock_response.json = AsyncMock(
            return_value={
                "response": "Generated text",
                "prompt_eval_count": 15,
                "eval_count": 25,
            }
        )
        mock_session = AsyncMock()
        # Fix: post is a sync method returning an async context manager
        mock_session.post = MagicMock()
        mock_session.post.return_value = AsyncContextManagerMock(mock_response)
        mock_session.closed = False

        client = OllamaClient(OllamaConfig(base_url="http://localhost:11434"))

        async def mock_get_session():
            return mock_session

        client._get_session = mock_get_session

        result = await client.generate(
            "Test prompt",
            system_prompt="You are a helpful assistant",
            model_name="mistral",
        )

        assert result["text"] == "Generated text"
        # Проверяем, что системный промпт был передан
        call_args = mock_session.post.call_args
        assert call_args is not None
        # Проверяем, что в payload есть системный промпт
        if call_args.kwargs.get("json"):
            payload_prompt = call_args.kwargs["json"].get("prompt", "")
            assert "You are a helpful assistant" in payload_prompt

        await client.close()

    @pytest.mark.asyncio
    async def test_generate_not_configured(self):
        """Проверка ошибки при отсутствии конфигурации."""
        client = OllamaClient(OllamaConfig(base_url=""))
        with pytest.raises(LLMNotConfiguredError):
            await client.generate("Test prompt")

    @pytest.mark.asyncio
    async def test_generate_invalid_prompt(self):
        """Проверка валидации промпта."""
        client = OllamaClient(OllamaConfig(base_url="http://localhost:11434"))

        with pytest.raises(ValueError):
            await client.generate("")

        with pytest.raises(ValueError):
            await client.generate("   ")

    @pytest.mark.asyncio
    async def test_generate_long_prompt_truncation(self):
        """Проверка обрезки длинного промпта."""
        long_prompt = "A" * 300000  # Больше max_prompt_length

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="")
        mock_response.json = AsyncMock(
            return_value={
                "response": "Generated text",
                "prompt_eval_count": 100,
                "eval_count": 50,
            }
        )
        mock_session = AsyncMock()
        # Fix: post is a sync method returning an async context manager
        mock_session.post = MagicMock()
        mock_session.post.return_value = AsyncContextManagerMock(mock_response)
        mock_session.closed = False

        client = OllamaClient(OllamaConfig(base_url="http://localhost:11434"))

        async def mock_get_session():
            return mock_session

        client._get_session = mock_get_session

        result = await client.generate(long_prompt)

        # Проверяем, что промпт был обрезан
        call_args = mock_session.post.call_args
        assert call_args is not None
        # Проверяем, что переданный промпт обрезан до max_prompt_length
        if call_args.kwargs.get("json"):
            payload_prompt = call_args.kwargs["json"].get("prompt", "")
            assert len(payload_prompt) <= 200000  # max_prompt_length

        await client.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Проверка работы context manager."""
        async with OllamaClient(
            OllamaConfig(base_url="http://localhost:11434")
        ) as client:
            assert client.is_configured is True

        # После выхода из контекста сессия должна быть закрыта
        assert client._session is None or client._session.closed
