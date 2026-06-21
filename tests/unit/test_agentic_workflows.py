from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.ai.mcp.server import (
    TOOLS,
    handle_agentic_action_gate,
    handle_agentic_plan_create,
    handle_agentic_plan_review,
)
from src.api.agentic_api import router
from src.middleware.jwt_user_context import require_auth
from src.services.rentgen import agentic_workflows, artifact_graph, policy_engine, test_evidence


def _principal(username: str):
    """Stand-in authenticated principal (principal_actor reads .username/.user_id)."""
    from types import SimpleNamespace

    return SimpleNamespace(username=username, user_id=username, roles=[])


def test_agentic_plan_review_and_action_gate(tmp_path, monkeypatch):
    store = tmp_path / "agentic_workflows.json"
    artifacts = tmp_path / "artifact_graph.json"
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")
    artifact_graph.create_artifact({"id": "REQ-AGENT", "type": "requirement", "title": "Agent source"}, path=artifacts)

    plan = agentic_workflows.create_agentic_plan(
        {
            "id": "PLAN-1",
            "title": "Implement posting validation",
            "mode": "act",
            "source_artifact_ids": ["REQ-AGENT"],
            "steps": [{"title": "Write BSL", "action_type": "bsl_write", "risk": "high"}],
        },
        path=store,
        artifact_path=artifacts,
    )
    reviewed = agentic_workflows.review_agentic_plan(plan["id"], path=store, artifact_path=artifacts)
    blocked = agentic_workflows.action_gate(action_type="bsl_write", plan_id=plan["id"], risk="high", path=store)
    allowed = agentic_workflows.action_gate(action_type="analysis", risk="low", path=store)

    assert reviewed["review"]["status"] == "fail"
    assert any(item["code"] == "act-without-approved-plan" for item in reviewed["review"]["findings"])
    assert blocked["allowed"] is False
    assert "confirmation_required" in blocked["reasons"]
    assert allowed["allowed"] is True


def test_agentic_api_exposes_plan_review_and_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_workflows, "STORE_PATH", tmp_path / "agentic_workflows.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")
    monkeypatch.setattr(test_evidence, "STORE_PATH", tmp_path / "test_runs.json")
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")

    app = FastAPI()
    app.include_router(router)
    # Plan author = authenticated principal; review must be by a different
    # principal or the separation-of-duties check blocks self-review.
    app.dependency_overrides[require_auth] = lambda: _principal("dev")
    client = TestClient(app)

    created = client.post(
        "/api/v1/agentic/plans",
        json={
            "id": "PLAN-API",
            "title": "Review metadata drift",
            "mode": "plan",
            "steps": [{"title": "Import metadata", "action_type": "metadata_write", "risk": "high"}],
        },
    )
    app.dependency_overrides[require_auth] = lambda: _principal("architect")
    reviewed = client.post("/api/v1/agentic/plans/PLAN-API/review")
    gate = client.post("/api/v1/agentic/action-gate", json={"action_type": "metadata_write", "plan_id": "PLAN-API", "risk": "high"})
    listing = client.get("/api/v1/agentic/plans")

    assert created.status_code == 200
    assert reviewed.json()["review"]["status"] in {"pass", "warn"}
    assert gate.json()["allowed"] is False
    assert listing.json()["total"] == 1

    # SoD proof: the plan author ("dev") cannot self-review.
    app.dependency_overrides[require_auth] = lambda: _principal("dev")
    self_review = client.post("/api/v1/agentic/plans/PLAN-API/review")
    assert self_review.status_code == 403


@pytest.mark.asyncio
async def test_mcp_agentic_tools_are_registered_and_work(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic_workflows, "STORE_PATH", tmp_path / "agentic_workflows.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")
    monkeypatch.setattr(test_evidence, "STORE_PATH", tmp_path / "test_runs.json")
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")

    names = {tool.name for tool in TOOLS}
    assert {"agentic_plan_create", "agentic_plan_review", "agentic_action_gate"} <= names

    plan = await handle_agentic_plan_create({"id": "PLAN-MCP", "title": "MCP plan", "mode": "plan"})
    review = await handle_agentic_plan_review({"plan_id": plan["id"]})
    gate = await handle_agentic_action_gate({"action_type": "external_command", "plan_id": plan["id"], "risk": "high"})

    assert plan["id"] == "PLAN-MCP"
    assert review["review"]["status"] in {"pass", "warn"}
    assert gate["allowed"] is False
