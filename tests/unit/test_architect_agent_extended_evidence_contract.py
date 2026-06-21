import pytest

from src.ai.agents.architect_agent_extended import (
    ARCHITECT_GRAPH_CONTRACT,
    ArchitectAgentExtended,
)


class FakeGraphClient:
    def execute_query(self, cypher, params=None):
        if "internal_edges" in cypher:
            return [{"total_edges": 4, "internal_edges": 3}]
        if "count(n) as nodes" in cypher:
            return [{"nodes": 4, "edges": 3}]
        if "count(n) as count" in cypher:
            return [{"count": 0}]
        if "nodes(path)" in cypher:
            return []
        return []


def make_agent(client=None) -> ArchitectAgentExtended:
    agent = ArchitectAgentExtended.__new__(ArchitectAgentExtended)
    agent.client = client
    return agent


@pytest.mark.asyncio
async def test_architect_agent_marks_metrics_unknown_without_graph():
    agent = make_agent()

    result = await agent.analyze_system("ERP")

    assert result["analysis"]["mode"] == ARCHITECT_GRAPH_CONTRACT
    assert result["analysis"]["coverage"] == "no_code_graph_connection"
    assert result["architecture"]["overall_score"] is None
    assert result["architecture"]["metrics"]["coupling"] is None
    assert result["architecture"]["metrics"]["cohesion"] is None
    assert result["architecture"]["metrics"]["measured"]["cohesion"] is False
    assert "Neo4j code graph connection" in result["analysis"]["required_evidence"]


@pytest.mark.asyncio
async def test_architect_agent_calculates_cohesion_from_graph_edges():
    agent = make_agent(FakeGraphClient())

    result = await agent.analyze_system("ERP")

    assert result["analysis"]["mode"] == ARCHITECT_GRAPH_CONTRACT
    assert result["analysis"]["coverage"] == "coupling+cohesion"
    assert result["architecture"]["metrics"]["coupling"] == 0.25
    assert result["architecture"]["metrics"]["cohesion"] == 0.75
    assert result["architecture"]["overall_score"] is not None
