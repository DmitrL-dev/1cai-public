from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.ai.mcp.server import (
    TOOLS,
    handle_change_set_analyze,
    handle_change_set_create,
    handle_change_set_select_tests,
    handle_change_set_transition,
)
from src.api import change_sets_api
from src.api.change_sets_api import router
from src.middleware.jwt_user_context import require_auth
from src.services.rentgen import artifact_graph, change_sets, policy_engine


def _principal(username: str):
    """Stand-in authenticated principal (principal_actor reads .username/.user_id)."""
    from types import SimpleNamespace

    return SimpleNamespace(username=username, user_id=username, roles=[])


MODULE = "Documents/Order/Ext/ObjectModule.bsl"


class FakeStore:
    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "risk": 74,
            "maintainability_score": 40,
            "has_n_plus_one": False,
            "has_select_star": False,
            "reasons": [],
        }

    def module_impact(self, module_path, max_depth=5, max_edges=600):
        return {
            "canonical": {"object_name": "Document.Order", "module_kind": "ObjectModule", "source": "fake"},
            "graph_modules": [{"name": "Order.ObjectModule", "fan_in": 3, "fan_out": 4}],
            "entry_subroutines": 2,
            "total": 42,
            "impacted_modules": [{"module": "CommonModules/Sales/Ext/Module.bsl", "edges": 3}],
        }

    def hotspots_for_graph_modules(self, module_names, limit=10):
        return [
            {
                "module_path": "CommonModules/Sales/Ext/Module.bsl",
                "risk": 77,
                "has_n_plus_one": False,
                "has_select_star": True,
            }
        ]


def test_change_set_lifecycle_analysis_tests_and_release(tmp_path, monkeypatch):
    store_path = tmp_path / "change_sets.json"
    artifact_path = tmp_path / "artifact_graph.json"
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")
    record = change_sets.create_change_set(
        {
            "id": "CHG-1",
            "title": "Credit limit validation",
            "owner": "dev",
            "source_requirement_ids": ["REQ-1"],
            "changed_modules": [MODULE],
        },
        path=store_path,
        artifact_path=artifact_path,
    )

    analyzed = change_sets.analyze_change_set(FakeStore(), record["id"], path=store_path, artifact_path=artifact_path)
    tests = change_sets.select_change_set_tests(FakeStore(), record["id"], path=store_path)
    release = change_sets.attach_release_readiness(
        FakeStore(),
        record["id"],
        include_forms=False,
        path=store_path,
    )
    with pytest.raises(ValueError):
        change_sets.transition_change_set(
            record["id"],
            status="approved",
            actor="architect",
            reason="Risk accepted for controlled release.",
            path=store_path,
            artifact_path=artifact_path,
        )
    transitioned = change_sets.transition_change_set(
        record["id"],
        status="approved",
        actor="architect",
        reason="Risk accepted for controlled release with explicit override.",
        allow_policy_failure=True,
        path=store_path,
        artifact_path=artifact_path,
    )
    trace = artifact_graph.trace_artifact("REQ-1", path=artifact_path)
    node_types = {node["type"] for node in trace["nodes"]}

    assert record["id"] == "CHG-1"
    assert analyzed["status"] == "impact_analyzed"
    assert analyzed["risk_summary"]["max_risk"] == 74
    assert tests["status"] == "tests_selected"
    assert tests["test_matrix"]["summary"]["changed_modules"] == 1
    assert release["status"] == "review_ready"
    assert release["release_readiness"]["decision"]["status"] in {"warn", "fail"}
    assert transitioned["status"] == "approved"
    assert transitioned["policy_evaluation"]["status"] == "fail"
    assert trace["summary"]["links"] >= 1
    assert {"change_set", "bsl_module", "test_case", "release"} <= node_types


def test_change_sets_api_exposes_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(change_sets, "STORE_PATH", tmp_path / "change_sets.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")
    monkeypatch.setattr(change_sets_api, "store_or_none", lambda: FakeStore())

    app = FastAPI()
    app.include_router(router)
    # Governance endpoints derive actor/owner from the authenticated principal,
    # never the request body. Inject a known principal via require_auth, and switch
    # identity so the approver differs from the author — otherwise the separation-
    # of-duties check (correctly) blocks self-approval.
    app.dependency_overrides[require_auth] = lambda: _principal("dev")
    client = TestClient(app)

    created = client.post(
        "/api/v1/change-sets",
        json={
            "id": "CHG-API",
            "title": "Credit limit validation",
            "source_requirement_ids": ["REQ-API"],
            "changed_modules": [MODULE],
        },
    )
    analyzed = client.post("/api/v1/change-sets/CHG-API/analyze", json={})
    tests = client.post("/api/v1/change-sets/CHG-API/select-tests", json={})
    release = client.post("/api/v1/change-sets/CHG-API/release-readiness", json={"include_forms": False})

    # Approver differs from the "dev" author so SoD passes; the 400 is the policy
    # gate failing, and the override path then approves.
    app.dependency_overrides[require_auth] = lambda: _principal("architect")
    transitioned = client.post(
        "/api/v1/change-sets/CHG-API/transition",
        json={"status": "approved", "reason": "Ready."},
    )
    transitioned_override = client.post(
        "/api/v1/change-sets/CHG-API/transition",
        json={
            "status": "approved",
            "reason": "Ready with explicit override.",
            "allow_policy_failure": True,
        },
    )
    listing = client.get("/api/v1/change-sets")

    assert created.status_code == 200
    assert analyzed.json()["status"] == "impact_analyzed"
    assert tests.json()["test_matrix"]["summary"]["changed_modules"] == 1
    assert release.json()["release_readiness"]["decision"]["status"] in {"warn", "fail"}
    assert transitioned.status_code == 400
    assert transitioned_override.json()["status"] == "approved"
    assert transitioned_override.json()["policy_evaluation"]["status"] == "fail"
    assert listing.json()["total"] == 1

    # SoD proof: the author ("dev") cannot self-approve.
    app.dependency_overrides[require_auth] = lambda: _principal("dev")
    self_approve = client.post(
        "/api/v1/change-sets/CHG-API/transition",
        json={"status": "approved", "reason": "self-approval attempt"},
    )
    assert self_approve.status_code == 403


@pytest.mark.asyncio
async def test_mcp_change_set_tools_are_registered_and_work(tmp_path, monkeypatch):
    monkeypatch.setattr(change_sets, "STORE_PATH", tmp_path / "change_sets.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")
    monkeypatch.setattr(policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json")
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")
    monkeypatch.setattr("src.api._rentgen_store.store_or_none", lambda: FakeStore())

    names = {tool.name for tool in TOOLS}
    assert {
        "change_set_create",
        "change_set_analyze",
        "change_set_select_tests",
        "change_set_transition",
    } <= names

    created = await handle_change_set_create(
        {
            "id": "CHG-MCP",
            "title": "Credit limit validation",
            "source_requirement_ids": ["REQ-MCP"],
            "changed_modules": [MODULE],
        }
    )
    analyzed = await handle_change_set_analyze({"change_set_id": created["id"]})
    tests = await handle_change_set_select_tests({"change_set_id": created["id"]})
    transitioned = await handle_change_set_transition(
        {
            "change_set_id": created["id"],
            "status": "approved",
            "actor": "architect",
            "allow_policy_failure": True,
        }
    )

    assert analyzed["store"] is True
    assert analyzed["risk_summary"]["max_risk"] == 74
    assert tests["test_matrix"]["summary"]["changed_modules"] == 1
    assert transitioned["status"] == "approved"
