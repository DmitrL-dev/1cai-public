import pytest

from src.api.copilot_coverage_api import get_copilot_coverage


@pytest.mark.asyncio
async def test_coverage_map_is_framed_as_subscription_escape() -> None:
    report = await get_copilot_coverage()

    assert report["product"] == "1C Rentgen Subscription Escape Map"
    assert "AI-подписка" in report["positioning"]
    assert "Copilot" not in report["product"]
    assert all("Copilot" not in item["title"] for item in report["items"])
