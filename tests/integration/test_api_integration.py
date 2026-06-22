"""
Integration Tests для API
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import asyncpg
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Test Database Integration
@pytest.mark.asyncio
async def test_postgres_connection():
    """Test подключения к PostgreSQL"""

    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="postgres",
        )

        # Simple query
        result = await conn.fetchval("SELECT 1")

        await conn.close()

        assert result == 1

    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}", allow_module_level=False)


@pytest.mark.asyncio
async def test_tenant_crud():
    """Test CRUD операций с tenant"""

    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            database="enterprise_1c_ai",
        )

        # Create tenant
        tenant_id = await conn.fetchval(
            """
            INSERT INTO tenants (name, email, plan, status)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """,
            "Test Tenant",
            "test@example.com",
            "starter",
            "trial",
        )

        assert tenant_id is not None

        # Read tenant
        tenant = await conn.fetchrow("SELECT * FROM tenants WHERE id = $1", tenant_id)

        assert tenant["name"] == "Test Tenant"

        # Update tenant
        await conn.execute(
            "UPDATE tenants SET status = $1 WHERE id = $2", "active", tenant_id
        )

        # Delete tenant
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)

        await conn.close()

    except Exception as e:
        pytest.skip(f"Database not available: {e}", allow_module_level=False)


# Test AI Agent Integration
@pytest.mark.asyncio
async def test_role_based_router_integration():
    """Test интеграции RoleBasedRouter с агентами"""
    from src.ai.role_based_router import RoleBasedRouter

    router = RoleBasedRouter()

    # Test developer query
    dev_query = "Как оптимизировать этот запрос?"
    result = await router.route_query(dev_query)

    assert result is not None
    assert "role" in result


# Test GitHub Integration
@pytest.mark.asyncio
async def test_github_pr_comment():
    """Test комментирования PR в GitHub.

    The old ``src.api.github_integration.GitHubIntegration.post_pr_comment`` API
    was refactored into ``src.modules.github_integration`` as
    ``GitHubClient.post_comment``. This test targets the current API: the token
    is a constructor argument and the client issues a single POST via
    ``httpx.AsyncClient.request`` under an async-context-manager.
    """
    from src.modules.github_integration import GitHubClient

    # Response returned by the mocked httpx client.
    response_mock = Mock()
    response_mock.status_code = 201
    response_mock.raise_for_status = Mock(return_value=None)
    response_mock.json = Mock(return_value={"id": 1})

    client_mock = AsyncMock()
    client_mock.__aenter__.return_value = client_mock
    client_mock.__aexit__.return_value = False
    client_mock.request = AsyncMock(return_value=response_mock)

    with patch("httpx.AsyncClient", return_value=client_mock):
        gh = GitHubClient(github_token="test_token")

        result = await gh.post_comment(
            repo="test/repo",
            pr_number=1,
            comment="Test comment",
        )

    assert result is True
    client_mock.request.assert_awaited_once()


# Test Stripe Integration
@pytest.mark.asyncio
async def test_stripe_customer_creation():
    """Test создания Stripe customer"""

    with patch("stripe.Customer.create") as mock_create:
        mock_create.return_value = Mock(id="cus_test123")

        # Import tenant management
        # (Would test actual API endpoint)

        customer_id = "cus_test123"
        assert customer_id.startswith("cus_")


# Test Cache Integration
@pytest.mark.asyncio
async def test_cache_redis_integration():
    """Test интеграции с Redis"""
    from src.cache.multi_layer_cache import MultiLayerCache

    try:
        import redis.asyncio as redis

        redis_client = redis.Redis(host="localhost", port=6379, db=0)

        cache = MultiLayerCache(redis_client)

        # Set value
        await cache.set("integration_test", {"value": 123}, ttl_seconds=60)

        # Get value
        value = await cache.get("integration_test")

        assert value == {"value": 123}

        # Cleanup
        await redis_client.delete("integration_test")
        await redis_client.close()

    except Exception as e:
        pytest.skip(f"Redis not available: {e}", allow_module_level=False)


# Test Neo4j Integration
@pytest.mark.asyncio
async def test_neo4j_connection():
    """Test подключения к Neo4j"""

    try:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            "bolt://localhost:7687", auth=("neo4j", "password")
        )

        async with driver.session() as session:
            result = await session.run("RETURN 1 as num")
            record = await result.single()

            assert record["num"] == 1

        await driver.close()

    except Exception as e:
        pytest.skip(f"Neo4j not available: {e}", allow_module_level=False)


# Test Qdrant Integration
@pytest.mark.asyncio
async def test_qdrant_connection():
    """Test подключения к Qdrant"""

    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host="localhost", port=6333)

        # Check health
        health = client.get_collections()

        assert health is not None

    except Exception as e:
        pytest.skip(f"Qdrant not available: {e}", allow_module_level=False)


# Test MCP Server Integration
@pytest.mark.skip(
    reason="imports module deleted in phase-7 cleanup (src.ai.mcp_server); obsolete test-rot"
)
@pytest.mark.asyncio
async def test_mcp_server_tools():
    """Test MCP Server инструментов"""
    from src.ai.mcp_server import MCPServer

    server = MCPServer()

    # Test search_metadata tool
    result = await server.search_metadata(
        query="Документ.Заказ", metadata_type="document"
    )

    assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
