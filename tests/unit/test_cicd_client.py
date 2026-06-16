import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.integrations.cicd_client import CICDClient, CIPlatform


@pytest.mark.asyncio
async def test_gitlab_trigger_pipeline():
    client = CICDClient(CIPlatform.GITLAB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        # Mock the session context manager
        mock_session = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        assert result["id"] == 456
        assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_github_trigger_pipeline():
    client = CICDClient(CIPlatform.GITHUB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = MagicMock()


@pytest.mark.asyncio
async def test_gitlab_get_status():
    client = CICDClient(CIPlatform.GITLAB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_ctx = AsyncMock()


@pytest.mark.asyncio
async def test_github_get_status():
    client = CICDClient(CIPlatform.GITHUB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_cls.return_value = mock_session_ctx


import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.integrations.cicd_client import CICDClient, CIPlatform


@pytest.mark.asyncio
async def test_gitlab_trigger_pipeline():
    client = CICDClient(CIPlatform.GITLAB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        # Mock the session context manager
        mock_session = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        assert result["id"] == 456
        assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_github_trigger_pipeline():
    client = CICDClient(CIPlatform.GITHUB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = MagicMock()


@pytest.mark.asyncio
async def test_gitlab_get_status():
    client = CICDClient(CIPlatform.GITLAB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_ctx = AsyncMock()


@pytest.mark.asyncio
async def test_github_get_status():
    client = CICDClient(CIPlatform.GITHUB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_cls.return_value = mock_session_ctx

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "id": 456,
            "status": "completed",
            "conclusion": "success",
            "html_url": "http://github.com",
        }
        mock_response.raise_for_status = MagicMock()

        mock_get_ctx = AsyncMock()
        mock_get_ctx.__aenter__.return_value = mock_response
        mock_session.get.return_value = mock_get_ctx

        result = await client.get_pipeline_status("owner/repo", "456")
        assert result["conclusion"] == "success"
