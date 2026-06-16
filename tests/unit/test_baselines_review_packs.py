from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.ai.mcp.server import (
    TOOLS,
    handle_baseline_create,
    handle_review_pack_create,
    handle_review_pack_decide,
)
from src.api.baselines_api import router
from src.services.rentgen import artifact_graph, baselines


def _seed_artifacts(path):
    req = artifact_graph.create_artifact(
        {"id": "REQ-1", "type": "requirement", "title": "Credit limit", "status": "approved"},
        path=path,
    )
    chg = artifact_graph.create_artifact(
        {"id": "CHG-1", "type": "change_set", "title": "Credit limit change", "status": "review_ready"},
        path=path,
    )
    artifact_graph.link_artifacts(
        source_id=req["id"],
        target_id=chg["id"],
        link_type="implements",
        path=path,
    )
    return req, chg


def test_baseline_and_review_pack_service(tmp_path):
    artifact_store = tmp_path / "artifact_graph.json"
    baseline_store = tmp_path / "baselines.json"
    review_store = tmp_path / "review_packs.json"
    req, chg = _seed_artifacts(artifact_store)

    baseline = baselines.create_baseline(
        baseline_id="BASE-1",
        title="Release 1 baseline",
        artifact_ids=[req["id"], chg["id"]],
        change_set_ids=[chg["id"]],
        path=baseline_store,
        artifact_path=artifact_store,
    )
    review_pack = baselines.create_review_pack(
        review_pack_id="RP-1",
        title="Release 1 review",
        artifact_ids=[req["id"], chg["id"]],
        reviewers=["architect"],
        path=review_store,
        artifact_path=artifact_store,
    )
    commented = baselines.add_review_comment(
        "RP-1",
        actor="architect",
        message="Looks ready.",
        artifact_id=chg["id"],
        path=review_store,
    )
    decided = baselines.decide_review_pack(
        "RP-1",
        actor="architect",
        decision="approved",
        reason="Scope and tests accepted.",
        path=review_store,
        artifact_path=artifact_store,
    )
    trace = artifact_graph.trace_artifact("BASE-1", path=artifact_store)

    assert baseline["status"] == "sealed"
    assert len(baseline["evidence_hash"]) == 64
    assert review_pack["status"] == "open"
    assert commented["comments"][0]["artifact_id"] == chg["id"]
    assert decided["status"] == "approved"
    assert trace["summary"]["links"] >= 2
    assert {"baseline", "requirement", "change_set"} <= {node["type"] for node in trace["nodes"]}


def test_baseline_id_is_immutable(tmp_path):
    artifact_store = tmp_path / "artifact_graph.json"
    baseline_store = tmp_path / "baselines.json"
    req, _ = _seed_artifacts(artifact_store)

    baselines.create_baseline(
        baseline_id="BASE-IMMUTABLE",
        title="Release baseline",
        artifact_ids=[req["id"]],
        path=baseline_store,
        artifact_path=artifact_store,
    )

    with pytest.raises(ValueError):
        baselines.create_baseline(
            baseline_id="BASE-IMMUTABLE",
            title="Release baseline replacement",
            artifact_ids=[req["id"]],
            path=baseline_store,
            artifact_path=artifact_store,
        )


def test_baselines_api_exposes_workflow(tmp_path, monkeypatch):
    artifact_store = tmp_path / "artifact_graph.json"
    monkeypatch.setattr(artifact_graph, "STORE_PATH", artifact_store)
    monkeypatch.setattr(baselines, "BASELINES_PATH", tmp_path / "baselines.json")
    monkeypatch.setattr(baselines, "REVIEW_PACKS_PATH", tmp_path / "review_packs.json")
    req, chg = _seed_artifacts(artifact_store)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    baseline = client.post(
        "/api/v1/baselines",
        json={"id": "BASE-API", "title": "Release baseline", "artifact_ids": [req["id"], chg["id"]]},
    )
    review_pack = client.post(
        "/api/v1/review-packs",
        json={
            "id": "RP-API",
            "title": "Release review",
            "artifact_ids": [req["id"], chg["id"]],
            "reviewers": ["architect"],
        },
    )
    comment = client.post(
        "/api/v1/review-packs/RP-API/comment",
        json={"actor": "architect", "message": "Ready.", "artifact_id": chg["id"]},
    )
    approve = client.post(
        "/api/v1/review-packs/RP-API/approve",
        json={"actor": "architect", "reason": "Accepted."},
    )
    baselines_list = client.get("/api/v1/baselines")
    packs_list = client.get("/api/v1/review-packs?status=approved")

    assert baseline.status_code == 200
    assert baseline.json()["status"] == "sealed"
    assert review_pack.json()["status"] == "open"
    assert comment.json()["comments"][0]["message"] == "Ready."
    assert approve.json()["status"] == "approved"
    assert baselines_list.json()["total"] == 1
    assert packs_list.json()["total"] == 1


@pytest.mark.asyncio
async def test_mcp_baseline_and_review_pack_tools(tmp_path, monkeypatch):
    artifact_store = tmp_path / "artifact_graph.json"
    monkeypatch.setattr(artifact_graph, "STORE_PATH", artifact_store)
    monkeypatch.setattr(baselines, "BASELINES_PATH", tmp_path / "baselines.json")
    monkeypatch.setattr(baselines, "REVIEW_PACKS_PATH", tmp_path / "review_packs.json")
    req, chg = _seed_artifacts(artifact_store)

    names = {tool.name for tool in TOOLS}
    assert {"baseline_create", "review_pack_create", "review_pack_decide"} <= names

    baseline = await handle_baseline_create(
        {"id": "BASE-MCP", "title": "Release baseline", "artifact_ids": [req["id"], chg["id"]]}
    )
    review_pack = await handle_review_pack_create(
        {"id": "RP-MCP", "title": "Release review", "artifact_ids": [req["id"], chg["id"]]}
    )
    decision = await handle_review_pack_decide(
        {"review_pack_id": "RP-MCP", "decision": "approved", "actor": "architect"}
    )

    assert baseline["status"] == "sealed"
    assert review_pack["status"] == "open"
    assert decision["status"] == "approved"
