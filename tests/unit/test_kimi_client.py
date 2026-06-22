"""
Unit tests for Kimi-K2-Thinking client
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ai.clients.exceptions import LLMCallError, LLMNotConfiguredError
from src.ai.clients.kimi_client import DEFAULT_OLLAMA_URL, KimiClient, KimiConfig


class AsyncContextManagerMock:
    """Simple async context manager returning provided value."""

    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class TestKimiConfig:
    """Test KimiConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        config = KimiConfig()
        assert config.mode == "auto"
        assert config.base_url == "https://api.moonshot.cn/v1"
        assert config.model_name == "moonshotai/Kimi-K2-Thinking"
        assert config.temperature == 1.0
        assert config.max_tokens == 4096
        assert config.timeout == 300.0

    def test_config_from_env(self, monkeypatch):
        """Test configuration from environment variables"""
        monkeypatch.setenv("KIMI_MODE", "local")
        monkeypatch.setenv("KIMI_API_KEY", "test_key")
        monkeypatch.setenv("KIMI_TEMPERATURE", "0.8")

        config = KimiConfig()
        assert config.mode == "local"
        assert config.api_key == "test_key"
        assert config.temperature == 0.8


class TestKimiClient:
    """Test KimiClient class"""

    def test_client_init_api_mode(self):
        """Test client initialization in API mode"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"

        client = KimiClient(config=config)
        assert client._mode == "api"
        assert client.is_configured is True
        assert client.is_local is False

    def test_client_init_local_mode(self):
        """Test client initialization in local mode"""
        config = KimiConfig()
        config.mode = "local"
        config.ollama_url = "http://localhost:11434"

        client = KimiClient(config=config)
        assert client._mode == "local"
        assert client.is_configured is True
        assert client.is_local is True

    def test_client_not_configured_api(self):
        """Test client not configured in API mode"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = None

        client = KimiClient(config=config)
        assert client.is_configured is False

    def test_client_not_configured_local(self):
        """Test client not configured in local mode"""
        config = KimiConfig()
        config.mode = "local"
        config.ollama_url = ""

        client = KimiClient(config=config)
        assert client.is_configured is False

    def test_client_auto_mode_prefers_api(self):
        """Auto mode should prefer API when key is available"""
        config = KimiConfig()
        config.mode = "auto"
        config.api_key = "test_key"
        config.ollama_url = DEFAULT_OLLAMA_URL

        client = KimiClient(config=config)
        assert client._mode == "api"

    def test_client_auto_mode_prefers_local_custom_url(self):
        """Auto mode should switch to local when custom Ollama URL provided"""
        config = KimiConfig()
        config.mode = "auto"
        config.api_key = ""
        config.ollama_url = "http://custom-ollama:11434"

        client = KimiClient(config=config)
        assert client._mode == "local"

    def test_client_auto_mode_respects_default_env(self, monkeypatch):
        """Auto mode should respect KIMI_DEFAULT_MODE"""
        monkeypatch.setenv("KIMI_DEFAULT_MODE", "local")
        config = KimiConfig()
        config.mode = "auto"
        config.api_key = ""
        config.ollama_url = DEFAULT_OLLAMA_URL

        client = KimiClient(config=config)
        assert client._mode == "local"

    @pytest.mark.asyncio
    async def test_generate_not_configured_api(self):
        """Test generate raises error when not configured in API mode"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = None

        client = KimiClient(config=config)

        with pytest.raises(LLMNotConfiguredError):
            await client.generate("test prompt")

    @pytest.mark.asyncio
    async def test_generate_not_configured_local(self):
        """Test generate raises error when not configured in local mode"""
        config = KimiConfig()
        config.mode = "local"
        config.ollama_url = ""

        client = KimiClient(config=config)

        with pytest.raises(LLMNotConfiguredError):
            await client.generate("test prompt")

    @pytest.mark.asyncio
    async def test_generate_invalid_prompt(self):
        """Test generate with invalid prompt"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"

        client = KimiClient(config=config)

        with pytest.raises(ValueError, match="Prompt must be a non-empty string"):
            await client.generate("")

        with pytest.raises(ValueError, match="Prompt must be a non-empty string"):
            await client.generate(None)

    @pytest.mark.asyncio
    async def test_generate_prompt_too_long(self):
        """Test generate with prompt exceeding max length"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"

        client = KimiClient(config=config)
        long_prompt = "a" * 300000  # Exceeds max_prompt_length

        with patch.object(client, "_generate_api") as mock_generate:
            mock_generate.return_value = {"text": "response"}
            result = await client.generate(long_prompt)
            # Should truncate prompt
            assert len(mock_generate.call_args[1]["prompt"]) <= 200000

    @pytest.mark.asyncio
    async def test_generate_api_mode_success(self):
        """Test successful generation in API mode"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"

        client = KimiClient(config=config)

        mock_response = {
            "text": "Test response",
            "reasoning_content": "Test reasoning",
            "tool_calls": [],
            "usage": {"total_tokens": 100},
            "finish_reason": "stop",
        }

        with patch.object(
            client, "_generate_api", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = mock_response
            result = await client.generate("test prompt")

            assert result == mock_response
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_local_mode_success(self):
        """Test successful generation in local mode"""
        config = KimiConfig()
        config.mode = "local"
        config.ollama_url = "http://localhost:11434"

        client = KimiClient(config=config)

        mock_response = {
            "text": "Test response",
            "reasoning_content": "",
            "tool_calls": [],
            "usage": {"total_tokens": 100},
            "finish_reason": "stop",
        }

        with patch.object(
            client, "_generate_local", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = mock_response
            result = await client.generate("test prompt")

            assert result == mock_response
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_api_mode_with_tools(self):
        """Test generation with tools in API mode"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"

        client = KimiClient(config=config)

        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        with patch.object(
            client, "_generate_api", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = {"text": "response"}
            await client.generate("test prompt", tools=tools)

            call_kwargs = mock_generate.call_args[1]
            assert call_kwargs["tools"] == tools

    @pytest.mark.asyncio
    async def test_generate_local_mode_with_tools_warning(self):
        """Test generation with tools in local mode should warn"""
        config = KimiConfig()
        config.mode = "local"
        config.ollama_url = "http://localhost:11434"

        client = KimiClient(config=config)

        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        with patch.object(
            client, "_generate_local", new_callable=AsyncMock
        ) as mock_generate:
            mock_generate.return_value = {"text": "response"}
            with patch("src.ai.clients.kimi_client.logger") as mock_logger:
                await client.generate("test prompt", tools=tools)
                # Should warn about tools not supported in local mode
                mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_check_model_loaded_api_mode(self):
        """Test check_model_loaded in API mode returns True"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"

        client = KimiClient(config=config)
        result = await client.check_model_loaded()
        assert result is True

    @pytest.mark.asyncio
    async def test_check_model_loaded_local_mode_success(self):
        """Test check_model_loaded in local mode when model exists"""
        config = KimiConfig()
        config.mode = "local"
        config.ollama_url = "http://localhost:11434"
        config.local_model = "kimi-k2-thinking:cloud"

        client = KimiClient(config=config)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"models": [{"name": "kimi-k2-thinking:cloud"}]}
        )

        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        with patch.object(client, "_get_ollama_session", return_value=mock_session):
            result = await client.check_model_loaded()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_model_loaded_local_mode_not_found(self):
        """Test check_model_loaded in local mode when model doesn't exist"""
        config = KimiConfig()
        config.mode = "local"
        config.ollama_url = "http://localhost:11434"
        config.local_model = "kimi-k2-thinking:cloud"

        client = KimiClient(config=config)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={"models": [{"name": "other-model"}]}
        )

        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        with patch.object(client, "_get_ollama_session", return_value=mock_session):
            result = await client.check_model_loaded()

        assert result is False

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing HTTP client"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"

        client = KimiClient(config=config)

        # Mock client
        mock_httpx_client = AsyncMock()
        client._client = mock_httpx_client

        mock_aio_session = AsyncMock()
        mock_aio_session.closed = False
        client._ollama_session = mock_aio_session

        await client.close()
        mock_httpx_client.aclose.assert_called_once()
        assert client._client is None
        mock_aio_session.close.assert_awaited_once()
        assert client._ollama_session is None

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test client as context manager"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"

        client = KimiClient(config=config)
        mock_httpx_client = AsyncMock()
        client._client = mock_httpx_client

        mock_aio_session = AsyncMock()
        mock_aio_session.closed = False
        client._ollama_session = mock_aio_session

        async with client:
            assert client._client is not None

        mock_httpx_client.aclose.assert_called_once()
        mock_aio_session.close.assert_awaited_once()


class TestKimiClientGenerateAPI:
    """Test _generate_api method"""

    @pytest.mark.asyncio
    async def test_generate_api_success(self):
        """Test successful API generation"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"
        config.base_url = "https://api.moonshot.cn/v1"
        config.model_name = "moonshotai/Kimi-K2-Thinking"

        client = KimiClient(config=config)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "Test response",
                        "reasoning_content": "Test reasoning",
                        "tool_calls": [],
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"total_tokens": 100},
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.object(client, "_get_client", return_value=mock_client):
                result = await client._generate_api(
                    prompt="test prompt",
                    system_prompt="You are a helpful assistant",
                    temperature=1.0,
                    max_tokens=4096,
                )

                assert result["text"] == "Test response"
                assert result["reasoning_content"] == "Test reasoning"
                assert result["usage"]["total_tokens"] == 100

    @pytest.mark.asyncio
    async def test_generate_api_http_error(self):
        """Test API generation with HTTP error"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = "test_key"

        client = KimiClient(config=config)

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "Invalid request"}}

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_response.raise_for_status.side_effect = Exception("HTTP 400")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with patch.object(client, "_get_client", return_value=mock_client):
                with pytest.raises(LLMCallError):
                    await client._generate_api(prompt="test prompt")


class TestKimiClientChatWithTools:
    """Test chat_with_tools method"""

    @pytest.mark.asyncio
    async def test_chat_with_tools_not_configured(self):
        """Test chat_with_tools when not configured"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = None

        client = KimiClient(config=config)

        with pytest.raises(LLMNotConfiguredError):
            await client.chat_with_tools(
                messages=[{"role": "user", "content": "test"}], tools=[], tool_map={}
            )

    @pytest.mark.asyncio
    async def test_chat_with_tools_local_mode_fallback(self):
        """Test chat_with_tools in local mode falls back to simple generation"""
        config = KimiConfig()
        config.mode = "local"
        config.ollama_url = "http://localhost:11434"

        client = KimiClient(config=config)

        messages = [{"role": "user", "content": "test message"}]
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        mock_result = {"text": "response", "usage": {"total_tokens": 50}}

        with patch.object(client, "generate", new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_result
            result = await client.chat_with_tools(messages, tools, {})

            assert result["text"] == "response"
            assert result["iterations"] == 1
            assert result["tool_calls"] == []
