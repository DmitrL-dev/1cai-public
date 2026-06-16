import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import TOOLS, handle_rentgen_requirement_trace
from src.api import requirements_api
from src.services.rentgen.change_plan import build_requirement_impact
from src.services.rentgen.requirements_traceability import (
    build_trace_record,
    get_trace,
    list_traces,
    save_trace,
    transition_trace,
)
from src.services.rentgen.artifact_graph import coverage_matrix, trace_artifact


MODULE = "Documents/Order/Ext/ObjectModule.bsl"


class FakeStore:
    def search(self, term, limit=20):
        return [
            {
                "module_path": MODULE,
                "domain": "sales",
                "maintainability_score": 35,
                "risk": 72,
            }
        ]

    def get_module_risk(self, module_path):
        return {
            "module_path": module_path,
            "risk": 72,
            "maintainability_score": 35,
            "has_n_plus_one": False,
            "has_select_star": False,
        }

    def module_impact(self, module_path, max_depth=3, max_edges=200):
        return {
            "canonical": {
                "object_name": "Document.Order",
                "module_kind": "ObjectModule",
                "source": "fake",
            },
            "graph_modules": [
                {
                    "name": "Order.ObjectModule",
                    "object_name": "Document.Order",
                    "module_kind": "ObjectModule",
                    "fan_in": 2,
                    "fan_out": 3,
                    "n_subs": 4,
                    "max_complexity": 8,
                }
            ],
            "entry_subroutines": 2,
            "total": 42,
            "impacted_modules": [
                {"module": "CommonModules/Sales/Ext/Module.bsl", "edges": 3}
            ],
        }

    def hotspots_for_graph_modules(self, module_names, limit=8):
        return []


def _impact():
    return build_requirement_impact(
        FakeStore(),
        "Order posting must validate customer credit limit",
        limit=3,
        max_depth=2,
        max_edges=100,
    )


def test_requirement_trace_record_links_requirement_to_modules_tests_and_metadata(tmp_path):
    trace_store = tmp_path / "requirements_traces.json"
    artifact_store = tmp_path / "artifact_graph.json"
    impact = _impact()
    record = build_trace_record(
        requirement=impact["requirement"],
        candidate_modules=impact["candidate_modules"],
        change_plan=impact["change_plan"],
        acceptance_criteria=["Posting is blocked when limit is exceeded"],
        title="Credit limit control",
        caveats=impact["caveats"],
    )
    saved = save_trace(record, path=trace_store)
    listing = list_traces(path=trace_store)
    loaded = get_trace(saved["id"], path=trace_store)
    artifact_trace = trace_artifact(saved["id"], path=artifact_store)
    matrix = coverage_matrix(path=artifact_store)

    assert saved["title"] == "Credit limit control"
    assert saved["risk_summary"]["modules"] == 1
    assert saved["risk_summary"]["test_actions"] >= 1
    assert saved["links"]["metadata_objects"][0]["ref"] == "Document.Order"
    assert saved["trace_matrix"][0]["coverage"] in {"planned", "mapped"}
    assert saved["artifact_sync"]["artifact_id"] == saved["id"]
    assert artifact_trace["summary"]["nodes"] >= 3
    assert matrix["summary"]["partial"] + matrix["summary"]["covered"] == 1
    assert listing["total"] == 1
    assert loaded["id"] == saved["id"]
    assert loaded["artifact_sync"]["artifact_id"] == saved["id"]
    assert "Requirement Trace" in saved["markdown"]

    transitioned = transition_trace(
        saved["id"],
        status="approved",
        actor="architect",
        reason="Impact and tests accepted.",
        path=trace_store,
    )

    assert transitioned["status"] == "approved"
    assert transitioned["decision_log"][0]["actor"] == "architect"


def test_requirement_trace_api_persists_and_lists_records(tmp_path, monkeypatch):
    store_path = tmp_path / "requirements_traces.json"
    artifact_store = tmp_path / "artifact_graph.json"
    monkeypatch.setattr(requirements_api, "store_or_none", lambda: FakeStore())
    monkeypatch.setattr("src.services.rentgen.requirements_traceability.STORE_PATH", store_path)
    monkeypatch.setattr("src.services.rentgen.artifact_graph.STORE_PATH", artifact_store)

    app = FastAPI()
    app.include_router(requirements_api.router)
    client = TestClient(app)

    response = client.post(
        "/api/v1/requirements/trace",
        json={
            "title": "Credit limit control",
            "text": "Order posting must validate customer credit limit",
            "acceptance_criteria": ["Posting is blocked when limit is exceeded"],
            "include_its_context": False,
            "save": True,
        },
    )
    assert response.status_code == 200
    trace = response.json()

    traces = client.get("/api/v1/requirements/traces").json()
    details = client.get(f"/api/v1/requirements/traces/{trace['id']}").json()
    transitioned = client.post(
        f"/api/v1/requirements/traces/{trace['id']}/transition",
        json={"status": "approved", "actor": "architect", "reason": "Ready for change set."},
    )
    artifact_trace = client.get(f"/api/v1/requirements/traces/{trace['id']}/artifact-trace").json()

    assert traces["total"] == 1
    assert traces["items"][0]["id"] == trace["id"]
    assert details["title"] == "Credit limit control"
    assert transitioned.status_code == 200
    assert transitioned.json()["status"] == "approved"
    assert artifact_trace["summary"]["nodes"] >= 3


@pytest.mark.asyncio
async def test_mcp_requirement_trace_tool_is_registered(tmp_path, monkeypatch):
    monkeypatch.setattr("src.api._rentgen_store.store_or_none", lambda: FakeStore())
    monkeypatch.setattr(
        "src.services.rentgen.requirements_traceability.STORE_PATH",
        tmp_path / "requirements_traces.json",
    )

    names = {tool.name for tool in TOOLS}
    result = await handle_rentgen_requirement_trace(
        {
            "title": "Credit limit control",
            "text": "Order posting must validate customer credit limit",
            "acceptance_criteria": ["Posting is blocked when limit is exceeded"],
            "include_its_context": False,
            "save": True,
        }
    )

    assert "rentgen_requirement_trace" in names
    assert result["store"] is True
    assert result["links"]["metadata_objects"][0]["ref"] == "Document.Order"
