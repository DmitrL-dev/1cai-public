import os

os.environ.setdefault("JWT_SECRET", "unit-test-secret-key-please-rotate")

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.ai.mcp.server import (
    TOOLS,
    handle_policy_evaluate,
    handle_policy_waiver_decide,
    handle_policy_waiver_request,
)
from src.api.policies_api import router
from src.middleware.jwt_user_context import JWTUserContextMiddleware
from src.modules.auth.application.service import AuthService
from src.modules.auth.infrastructure.config import AuthSettings
from src.services.rentgen import artifact_graph, policy_engine

JWT_SECRET = "unit-test-secret-key-please-rotate"


RISK_CONTEXT = {
    "risk_summary": {
        "max_risk": 85,
        "total_impact_edges": 350,
    },
    "test_matrix": {"summary": {"gaps": 1}},
    "release_readiness": {"decision": {"status": "fail"}},
}


def test_policy_engine_fails_and_approved_waiver_downgrades(tmp_path):
    evaluations = tmp_path / "policy_evaluations.json"
    waivers = tmp_path / "policy_waivers.json"
    artifacts = tmp_path / "artifact_graph.json"

    failed = policy_engine.evaluate_policy(
        RISK_CONTEXT,
        scope_id="CHG-1",
        evaluations_path=evaluations,
        waivers_path=waivers,
    )
    waiver = policy_engine.create_waiver(
        rule_id="impact.max_risk.high",
        scope_id="CHG-1",
        reason="Temporary accepted risk for controlled release.",
        owner="architect",
        path=waivers,
        artifact_path=artifacts,
    )
    approved = policy_engine.decide_waiver(
        waiver["id"],
        status="approved",
        actor="lead",
        path=waivers,
        artifact_path=artifacts,
    )
    waived = policy_engine.evaluate_policy(
        {"risk_summary": {"max_risk": 85}},
        scope_id="CHG-1",
        evaluations_path=evaluations,
        waivers_path=waivers,
    )
    waiver_artifact = artifact_graph.get_artifact(waiver["id"], path=artifacts)

    assert failed["status"] == "fail"
    assert failed["summary"]["fail"] >= 3
    assert approved["status"] == "approved"
    assert waived["status"] == "pass"
    assert waived["summary"]["waived"] == 1
    assert waiver_artifact["type"] == "waiver"


def _auth_service(demo_users: str) -> AuthService:
    return AuthService(
        AuthSettings(
            jwt_secret=JWT_SECRET,
            access_token_expire_minutes=30,
            demo_users=demo_users,
        )
    )


_TWO_USERS = (
    '[{"username":"architect","password":"pw","user_id":"u-arch",'
    '"roles":["architect"],"permissions":[]},'
    '{"username":"lead","password":"pw","user_id":"u-lead",'
    '"roles":["lead"],"permissions":[]}]'
)


def test_policies_api_exposes_evaluate_and_waivers(tmp_path, monkeypatch):
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    # Waiver mutations now require auth; owner/actor derive from the authenticated
    # principal (not the body). Separation of duties => the owner cannot approve
    # their own waiver, so create as "architect" and approve as "lead".
    auth_service = _auth_service(_TWO_USERS)
    owner_token = auth_service.create_access_token(auth_service.authenticate_user("architect", "pw"))
    approver_token = auth_service.create_access_token(auth_service.authenticate_user("lead", "pw"))

    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware, auth_service=auth_service)
    app.include_router(router)
    client = TestClient(app)

    failed = client.post(
        "/api/v1/policies/evaluate",
        json={"context": RISK_CONTEXT, "scope_id": "CHG-API"},
    )
    waiver = client.post(
        "/api/v1/policies/waivers",
        json={
            "rule_id": "impact.max_risk.high",
            "scope_id": "CHG-API",
            "reason": "Temporary accepted risk.",
        },
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    approved = client.post(
        f"/api/v1/policies/waivers/{waiver.json()['id']}/approve",
        json={"decision_reason": "Approved for test release."},
        headers={"Authorization": f"Bearer {approver_token}"},
    )
    waived = client.post(
        "/api/v1/policies/evaluate",
        json={"context": {"risk_summary": {"max_risk": 85}}, "scope_id": "CHG-API"},
    )
    evaluations = client.get("/api/v1/policies/evaluations")
    waivers = client.get("/api/v1/policies/waivers?status=approved")

    assert failed.json()["status"] == "fail"
    assert waiver.status_code == 200
    assert approved.json()["status"] == "approved"
    assert waived.json()["status"] == "pass"
    assert evaluations.json()["total"] == 2
    assert waivers.json()["total"] == 1


def test_policies_api_blocks_self_approval(tmp_path, monkeypatch):
    """SoD at the API boundary: a waiver owner (authenticated principal) cannot
    approve their own waiver -> 403 (PermissionError mapped in _handle_error)."""
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    auth_service = _auth_service(
        '[{"username":"solo","password":"pw","user_id":"u-solo",'
        '"roles":["architect"],"permissions":[]}]'
    )
    token = auth_service.create_access_token(auth_service.authenticate_user("solo", "pw"))
    headers = {"Authorization": f"Bearer {token}"}

    app = FastAPI()
    app.add_middleware(JWTUserContextMiddleware, auth_service=auth_service)
    app.include_router(router)
    client = TestClient(app)

    waiver = client.post(
        "/api/v1/policies/waivers",
        json={
            "rule_id": "impact.max_risk.high",
            "scope_id": "CHG-SOLO",
            "reason": "Self-approval attempt.",
        },
        headers=headers,
    )
    assert waiver.status_code == 200
    resp = client.post(
        f"/api/v1/policies/waivers/{waiver.json()['id']}/approve",
        json={"decision_reason": "approving my own waiver"},
        headers=headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_mcp_policy_tools_are_registered_and_work(tmp_path, monkeypatch):
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    names = {tool.name for tool in TOOLS}
    assert {"policy_evaluate", "policy_waiver_request", "policy_waiver_decide"} <= names

    failed = await handle_policy_evaluate({"context": RISK_CONTEXT, "scope_id": "CHG-MCP"})
    waiver = await handle_policy_waiver_request(
        {
            "rule_id": "impact.max_risk.high",
            "scope_id": "CHG-MCP",
            "reason": "Temporary accepted risk.",
            "owner": "architect",
        }
    )
    approved = await handle_policy_waiver_decide(
        {"waiver_id": waiver["id"], "status": "approved", "actor": "lead"}
    )
    waived = await handle_policy_evaluate(
        {"context": {"risk_summary": {"max_risk": 85}}, "scope_id": "CHG-MCP"}
    )

    assert failed["status"] == "fail"
    assert approved["status"] == "approved"
    assert waived["summary"]["waived"] == 1


@pytest.mark.asyncio
async def test_mcp_waiver_decide_blocks_self_approval(tmp_path, monkeypatch):
    """SoD on the MCP path: the same principal that requested a waiver
    (owner) must not be able to approve it via handle_policy_waiver_decide.

    The engine's decide_waiver raises PermissionError on self-approval; the
    MCP handler must surface that as a blocked/error result and must NEVER
    report status == "approved".
    """
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    waiver = await handle_policy_waiver_request(
        {
            "rule_id": "impact.max_risk.high",
            "scope_id": "CHG-SELF",
            "reason": "Self-approval attempt over MCP.",
            "owner": "x",
        }
    )
    assert "error" not in waiver, waiver

    # actor == owner ("x") must be rejected. Accept either a structured error
    # result or a raised exception; the security property is that it is not
    # approved.
    try:
        decision = await handle_policy_waiver_decide(
            {"waiver_id": waiver["id"], "status": "approved", "actor": "x"}
        )
    except PermissionError:
        decision = None

    if decision is not None:
        assert decision.get("status") != "approved", decision
        assert "error" in decision or decision.get("status") == "blocked", decision

    # The persisted waiver must remain un-approved.
    stored = policy_engine.list_waivers()["items"]
    target = next(item for item in stored if item["id"] == waiver["id"])
    assert target["status"] != "approved", target
    assert target.get("approved_by") in (None, ""), target

    # Sanity: a different actor (not the owner) CAN approve, proving we did not
    # simply break approvals.
    ok = await handle_policy_waiver_decide(
        {"waiver_id": waiver["id"], "status": "approved", "actor": "reviewer"}
    )
    assert ok["status"] == "approved", ok
