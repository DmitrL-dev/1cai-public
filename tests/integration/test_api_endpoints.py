
"""
Integration tests for API endpoints
"""

import pytest
from fastapi.testclient import TestClient

# Both test classes below target FastAPI apps from modules that were removed in
# the phase-7 cleanup (src.api.graph_api and src.ai.mcp_server). Those imports
# live inside fixtures, so collection still succeeds, but the fixtures raise
# ModuleNotFoundError at run time. Skip the whole module as obsolete test-rot.
pytestmark = pytest.mark.skip(
    reason="imports modules deleted in phase-7 cleanup (src.api.graph_api, src.ai.mcp_server); obsolete test-rot"
)


@pytest.mark.integration
class TestGraphAPI:
    """Test Graph API endpoints"""

    @pytest.fixture
    def client(self):
        """FastAPI test client"""
        from src.api.graph_api import app

        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_get_configurations(self, client):
        """Test getting configurations"""
        # May fail if Neo4j not running - that's expected
        response = client.get("/api/graph/configurations")

        # Either success or service unavailable
        assert response.status_code in [200, 503]

    def test_stats_overview(self, client):
        """Test statistics endpoint"""
        response = client.get("/api/stats/overview")

        assert response.status_code in [200, 500, 503]

        if response.status_code == 200:
            data = response.json()
            # Should have stats for available services
            assert isinstance(data, dict)


@pytest.mark.integration
class TestMCPServer:
    """Test MCP Server endpoints"""

    @pytest.fixture
    def client(self):
        """MCP Server test client"""
        from src.ai.mcp_server import app

        return TestClient(app)

    def test_mcp_root(self, client):
        """Test MCP server info"""
        response = client.get("/mcp")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["name"] == "1C AI Assistant MCP Server"

    def test_list_tools(self, client):
        """Test listing MCP tools"""
        response = client.get("/mcp/tools")

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) == 4

        # Check tool names
        tool_names = [t["name"] for t in data["tools"]]
        assert "search_metadata" in tool_names
        assert "search_code_semantic" in tool_names
        assert "generate_bsl_code" in tool_names
        assert "analyze_dependencies" in tool_names

    def test_call_tool(self, client):
        """Test calling MCP tool"""
        response = client.post(
            "/mcp/tools/call",
            json={
                "name": "search_metadata",
                "arguments": {"query": "test query", "configuration": "DO"},
            },
        )

        assert response.status_code in [200, 500]
        # 500 is OK if Neo4j not running
