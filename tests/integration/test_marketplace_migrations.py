
"""Integration tests for marketplace migrations and repository."""

from __future__ import annotations

import uuid

import pytest

from src.db.marketplace_repository import MarketplaceRepository
from src.security.roles import grant_permission, grant_role

pytestmark = pytest.mark.integration


@pytest.mark.asyncio()
async def test_marketplace_tables_exist(db_pool):
    if db_pool is None:
        pytest.skip("TEST_DATABASE_URL not configured or database unavailable")

    async with db_pool.acquire() as conn:
        tables = await conn.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename = ANY($1::text[])
            """,
            [
                "marketplace_plugins",
                "marketplace_reviews",
                "marketplace_installs",
                "marketplace_favorites",
                "marketplace_complaints",
                "security_audit_log",
                "user_roles",
                "user_permissions",
            ],
        )

    found = {row["tablename"] for row in tables}
    assert "marketplace_plugins" in found
    assert "marketplace_reviews" in found
    assert "marketplace_installs" in found
    assert "marketplace_favorites" in found
    assert "marketplace_complaints" in found
    assert "security_audit_log" in found
    assert "user_roles" in found
    assert "user_permissions" in found


@pytest.mark.asyncio()
async def test_marketplace_repository_crud(db_pool):
    if db_pool is None:
        pytest.skip("TEST_DATABASE_URL not configured or database unavailable")

    repo = MarketplaceRepository(db_pool)
    plugin_id = f"test_plugin_{uuid.uuid4().hex}"

    payload = {
        "name": "Test Plugin",
        "description": "Integration test plugin",
        "category": "ai_agent",
        "version": "1.0.0",
        "status": "pending",
        "visibility": "public",
        "keywords": ["test"],
        "supported_platforms": ["telegram"],
    }

    created = await repo.create_plugin(
        plugin_id=plugin_id,
        owner_id="test-owner",
        owner_username="tester",
        payload=payload,
        download_url=f"https://example.com/{plugin_id}.zip",
    )

    assert created["plugin_id"] == plugin_id
    fetched = await repo.get_plugin(plugin_id)
    assert fetched is not None

    await repo.soft_delete_plugin(plugin_id)

    await grant_role("test-owner", "developer", assigned_by="integration-test")
    await grant_permission(
        "test-owner", "marketplace:submit", assigned_by="integration-test"
    )

    # clean up rows to keep database tidy
    async with db_pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM marketplace_plugins WHERE plugin_id = $1", plugin_id
        )
        await conn.execute("DELETE FROM user_roles WHERE user_id = $1", "test-owner")
        await conn.execute(
            "DELETE FROM user_permissions WHERE user_id = $1", "test-owner"
        )
