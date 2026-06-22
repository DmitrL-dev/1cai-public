"""
Unit tests for QwenCoderClient
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.ai.qwen_client import QwenCoderClient


class TestQwenCoderClient:
    """Test Qwen3-Coder client"""

    def test_initialization(self):
        """Test client initialization"""
        client = QwenCoderClient()

        assert client.ollama_url == "http://localhost:11434"
        assert client.model == "qwen2.5-coder:7b"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_generate_code(self, mock_session):
        """Test code generation"""
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "response": "```bsl\nФункция Тест()\n  Возврат 1;\nКонецФункции\n```",
                "eval_count": 100,
            }
        )

        mock_session_instance = AsyncMock()
        mock_session_instance.post.return_value.__aenter__.return_value = mock_response
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        client = QwenCoderClient()
        result = await client.generate_code("Создай функцию Test")

        assert "code" in result
        assert "Функция Тест" in result["code"]
        assert result["model"] == "qwen2.5-coder:7b"

    @pytest.mark.asyncio
    @patch("aiohttp.ClientSession")
    async def test_optimize_code(self, mock_session):
        """Test code optimization"""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "response": "Оптимизированный код:\n```bsl\nФункция Оптимизированная()\nКонецФункции\n```\n\nИзменения:\n1. Улучшена производительность",
                "eval_count": 200,
            }
        )

        mock_session_instance = AsyncMock()
        mock_session_instance.post.return_value.__aenter__.return_value = mock_response
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        client = QwenCoderClient()
        result = await client.optimize_code("Функция Test()\nКонецФункции")

        assert "optimized_code" in result
        assert "explanation" in result
        assert "improvements" in result

    def test_extract_code_from_markdown(self):
        """Test code extraction from markdown"""
        client = QwenCoderClient()

        response = "```bsl\nФункция Test()\n  Возврат 1;\nКонецФункции\n```"
        code = client._extract_code(response)

        assert "Функция Test" in code
        assert "```" not in code

    def test_extract_code_without_markdown(self):
        """Test code extraction without markdown"""
        client = QwenCoderClient()

        response = "Функция Test()\n  Возврат 1;\nКонецФункции"
        code = client._extract_code(response)

        assert code == response.strip()
