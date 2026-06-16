import pytest
from unittest.mock import AsyncMock, MagicMock
from src.infrastructure.repositories.marketplace import MarketplaceRepository

@pytest.mark.asyncio
async def test_get_plugin_stats_analytics():
    # Mock pool and connection
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    repo = MarketplaceRepository(pool=mock_pool)
    
    # Mock DB response
    # Simulate: 
    # - 100 total downloads
    # - 50 active installs
    # - 20 downloads in last 30 days
    # - 10 downloads in previous 30 days (Trend should be UP)
    mock_row = {
        "plugin_id": "test-plugin",
        "downloads": 100,
        "installs_active": 50,
        "avg_rating": 4.5,
        "rating": 4.5,
        "rating_dist": '{"5": 10, "4": 2}',
        "reviews_count": 12,
        "favorites_count": 5,
        "downloads_30d": 20,
        "downloads_prev_30d": 10
    }
    
    # Configure fetchrow to return the mock row
    mock_conn.fetchrow.return_value = mock_row
    
    stats = await repo.get_plugin_stats("test-plugin")
    
    assert stats is not None
    assert stats["downloads_last_30_days"] == 20
    assert stats["downloads_trend"] == "up" # 20 > 10 * 1.1
    assert stats["installs_active"] == 50

@pytest.mark.asyncio
async def test_get_plugin_stats_trend_down():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    repo = MarketplaceRepository(pool=mock_pool)
    
    # Simulate DOWN trend
    # 10 downloads last 30 days
    # 20 downloads previous 30 days
    mock_row = {
        "plugin_id": "test-plugin",
        "downloads": 100,
        "installs_active": 50,
        "avg_rating": 4.5,
        "rating": 4.5,
        "rating_dist": None,
        "reviews_count": 12,
        "favorites_count": 5,
        "downloads_30d": 10,
        "downloads_prev_30d": 20
    }
    mock_conn.fetchrow.return_value = mock_row
    
    stats = await repo.get_plugin_stats("test-plugin")
    
    assert stats["downloads_trend"] == "down" # 10 < 20 * 0.9

@pytest.mark.asyncio
async def test_get_plugin_stats_trend_stable():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    repo = MarketplaceRepository(pool=mock_pool)
    
    # Simulate STABLE trend
    # 10 downloads last 30 days
    # 10 downloads previous 30 days
    mock_row = {
        "plugin_id": "test-plugin",
        "downloads": 100,
        "installs_active": 50,
        "avg_rating": 4.5,
        "rating": 4.5,
        "rating_dist": None,
        "reviews_count": 12,
        "favorites_count": 5,
        "downloads_30d": 10,
        "downloads_prev_30d": 10
    }
    mock_conn.fetchrow.return_value = mock_row
    
    stats = await repo.get_plugin_stats("test-plugin")
    
    assert stats["downloads_trend"] == "stable"
