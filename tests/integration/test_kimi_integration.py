"""
Integration tests for Kimi-K2-Thinking client
"""
import os

import pytest

from src.ai.clients.kimi_client import KimiClient, KimiConfig


@pytest.mark.integration
class TestKimiIntegration:
    """Integration tests for Kimi-K2-Thinking"""

    @pytest.fixture
    def api_config(self):
        """Fixture for API mode configuration"""
        config = KimiConfig()
        config.mode = "api"
        config.api_key = os.getenv("KIMI_API_KEY", "")
        return config

    @pytest.fixture
    def local_config(self):
        """Fixture for local mode configuration"""
        config = KimiConfig()
        config.mode = "local"
        config.ollama_url = os.getenv(
            "KIMI_OLLAMA_URL", os.getenv("OLLAMA_HOST", "http://localhost:11434")
        )
        config.local_model = os.getenv("KIMI_LOCAL_MODEL", "kimi-k2-thinking:cloud")
        return config

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("KIMI_API_KEY"),
        reason="KIMI_API_KEY not set, skipping API integration test",
    )
    async def test_api_mode_generate(self, api_config):
        """Test generation in API mode (requires KIMI_API_KEY)"""
        client = KimiClient(config=api_config)

        if not client.is_configured:
            pytest.skip("Kimi API not configured")

        result = await client.generate(
            prompt="Привет! Это тестовый запрос.", temperature=1.0, max_tokens=100
        )

        assert "text" in result
        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0
        assert "usage" in result

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("KIMI_OLLAMA_URL") and not os.getenv("OLLAMA_HOST"),
        reason="Ollama URL not set, skipping local integration test",
    )
    async def test_local_mode_generate(self, local_config):
        """Test generation in local mode (requires Ollama running)"""
        client = KimiClient(config=local_config)

        if not client.is_configured:
            pytest.skip("Kimi local mode not configured")

        # Check if model is loaded
        model_loaded = await client.check_model_loaded()
        if not model_loaded:
            pytest.skip(f"Model {local_config.local_model} not loaded in Ollama")

        result = await client.generate(
            prompt="Привет! Это тестовый запрос.", temperature=1.0, max_tokens=100
        )

        assert "text" in result
        assert isinstance(result["text"], str)
        assert len(result["text"]) > 0
        assert "usage" in result

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("KIMI_API_KEY"),
        reason="KIMI_API_KEY not set, skipping API integration test",
    )
    async def test_api_mode_with_system_prompt(self, api_config):
        """Test generation with custom system prompt"""
        client = KimiClient(config=api_config)

        if not client.is_configured:
            pytest.skip("Kimi API not configured")

        result = await client.generate(
            prompt="Расскажи о себе.",
            system_prompt="Ты помощник для разработчиков 1С.",
            temperature=1.0,
            max_tokens=150,
        )

        assert "text" in result
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("KIMI_API_KEY"),
        reason="KIMI_API_KEY not set, skipping API integration test",
    )
    async def test_api_mode_json_response(self, api_config):
        """Test generation with JSON response format"""
        client = KimiClient(config=api_config)

        if not client.is_configured:
            pytest.skip("Kimi API not configured")

        result = await client.generate(
            prompt="Верни JSON с полями: name и age",
            response_format="json",
            temperature=0.7,
            max_tokens=100,
        )

        assert "text" in result
        # Note: Actual JSON parsing would require additional validation
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.getenv("KIMI_OLLAMA_URL") and not os.getenv("OLLAMA_HOST"),
        reason="Ollama URL not set, skipping local integration test",
    )
    async def test_local_mode_check_model(self, local_config):
        """Test checking if model is loaded in Ollama"""
        client = KimiClient(config=local_config)

        if not client.is_configured:
            pytest.skip("Kimi local mode not configured")

        model_loaded = await client.check_model_loaded()
        # This will be True if model exists, False otherwise
        assert isinstance(model_loaded, bool)

    @pytest.mark.asyncio
    async def test_client_context_manager(self, api_config):
        """Test client as context manager"""
        if not api_config.api_key:
            pytest.skip("Kimi API not configured")

        client = KimiClient(config=api_config)

        async with client:
            assert client.is_configured
            # Client should be usable
            assert client._mode == "api"

        # After context exit, client should be closed
        # (actual cleanup depends on implementation)
