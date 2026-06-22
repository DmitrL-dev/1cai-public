import pytest

from src.ai.agents.technology_selector import TECH_SELECTOR_CONTRACT, TechnologySelector


@pytest.mark.asyncio
async def test_technology_selector_uses_catalog_for_cost_complexity_and_alternatives():
    selector = TechnologySelector()

    result = await selector.recommend_technology_stack(
        {
            "scale": "high",
            "load": "10000 requests/day",
            "performance": "< 2s",
            "integration_type": "event-driven",
        },
        {
            "budget": "medium",
            "team_skills": ["Python", "PostgreSQL"],
            "existing_tech": ["1C ERP", "PostgreSQL"],
            "deployment": "on-premise",
        },
    )

    assert result["mode"] == TECH_SELECTOR_CONTRACT
    assert result["coverage"] == "local_technology_catalog"
    assert result["recommended_stack"]["integration_bus"]["option"] == "Apache Kafka"
    assert result["estimated_cost"] in {"Low", "Medium", "High"}
    assert result["implementation_complexity"] in {"Low", "Medium", "High"}
    assert "RabbitMQ" in result["alternatives"]["integration_bus"]
    assert result["caveats"]


@pytest.mark.asyncio
async def test_technology_selector_marks_missing_decision_evidence():
    selector = TechnologySelector()

    result = await selector.recommend_technology_stack({}, {})

    assert result["mode"] == TECH_SELECTOR_CONTRACT
    assert result["estimated_cost"] == "Unknown"
    assert result["implementation_complexity"] == "Unknown"
    assert "target scale" in result["required_evidence"]
    assert "team skill matrix" in result["required_evidence"]
