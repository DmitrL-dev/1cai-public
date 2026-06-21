from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.cicd_client import CICDClient, CIPlatform


def _mock_session(mock_session_cls):
    session = MagicMock()
    mock_session_cls.return_value.__aenter__.return_value = session
    return session


def _mock_response(status=200, payload=None):
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=payload or {})
    response.text = AsyncMock(return_value="")
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_gitlab_trigger_pipeline():
    client = CICDClient(CIPlatform.GITLAB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        session = _mock_session(mock_session_cls)
        response = _mock_response(status=201, payload={"id": 456, "status": "pending"})
        session.post.return_value.__aenter__.return_value = response

        result = await client.trigger_pipeline("123", ref="main")

        assert result["id"] == 456
        assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_github_trigger_pipeline():
    client = CICDClient(CIPlatform.GITHUB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        session = _mock_session(mock_session_cls)
        response = _mock_response(status=204)
        session.post.return_value.__aenter__.return_value = response

        result = await client.trigger_pipeline("owner/repo", ref="main")

        assert result["status"] == "triggered"
        assert result["web_url"] == "https://github.com/owner/repo/actions"


@pytest.mark.asyncio
async def test_gitlab_get_status():
    client = CICDClient(CIPlatform.GITLAB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        session = _mock_session(mock_session_cls)
        response = _mock_response(status=200, payload={"id": 456, "status": "success"})
        session.get.return_value.__aenter__.return_value = response

        result = await client.get_pipeline_status("123", "456")

        assert result["id"] == 456
        assert result["status"] == "success"


@pytest.mark.asyncio
async def test_github_get_status():
    client = CICDClient(CIPlatform.GITHUB, "token")

    with patch("aiohttp.ClientSession") as mock_session_cls:
        session = _mock_session(mock_session_cls)
        response = _mock_response(
            status=200,
            payload={
                "id": 456,
                "status": "completed",
                "conclusion": "success",
                "html_url": "http://github.com",
            },
        )
        session.get.return_value.__aenter__.return_value = response

        result = await client.get_pipeline_status("owner/repo", "456")

        assert result["id"] == "456"
        assert result["conclusion"] == "success"
        assert result["web_url"] == "http://github.com"