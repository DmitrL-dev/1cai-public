import pytest

from src.ai.agents.developer_agent_secure import (
    DEVELOPER_SECURE_CONTRACT,
    DeveloperAISecure,
)


def test_developer_agent_returns_offline_contract_without_model():
    agent = DeveloperAISecure()

    result = agent.generate_code("Create a login function")

    assert result["success"] is True
    assert result["mode"] == DEVELOPER_SECURE_CONTRACT
    assert result["generation_mode"] == "offline_generation_contract"
    assert result["requires_approval"] is True
    assert result["can_auto_apply"] is False
    assert "AI code synthesis model adapter" in result["required_evidence"]
    assert "example_function" not in result["suggestion"]
    assert "pass" not in result["suggestion"]


def test_developer_agent_does_not_fake_repository_commit():
    agent = DeveloperAISecure()
    generated = agent.generate_code("Create a small helper")

    result = agent.apply_suggestion(
        generated["token"],
        approved_by_user="lead-dev",
    )

    assert result["success"] is False
    assert result["applied"] is False
    assert result["blocked"] is True
    assert result["result"]["mode"] == DEVELOPER_SECURE_CONTRACT
    assert result["result"]["commit_sha"] is None
    assert "abc123" not in str(result)


def test_developer_agent_requires_named_human_approver():
    agent = DeveloperAISecure()
    generated = agent.generate_code("Create a small helper")

    with pytest.raises(ValueError):
        agent.apply_suggestion(generated["token"], approved_by_user=None)
