from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.artifacts_api import router
from src.services.rentgen import artifact_graph


def test_artifacts_api_crud_link_trace_and_matrix(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    requirement = client.post(
        "/api/v1/artifacts",
        json={
            "type": "requirement",
            "title": "Credit limit validation",
            "owner": "ba",
            "tags": ["sales", "posting"],
        },
    )
    module = client.post(
        "/api/v1/artifacts",
        json={
            "type": "bsl_module",
            "title": "Documents/Order/Ext/ObjectModule.bsl",
            "owner": "developer",
        },
    )

    assert requirement.status_code == 200
    assert module.status_code == 200
    req_id = requirement.json()["id"]
    module_id = module.json()["id"]

    patch = client.patch(
        f"/api/v1/artifacts/{req_id}", json={"status": "reviewed", "priority": "high"}
    )
    link = client.post(
        "/api/v1/artifacts/links",
        json={
            "source_id": req_id,
            "target_id": module_id,
            "type": "implements",
            "rationale": "The requirement touches posting logic.",
        },
    )
    trace = client.get(f"/api/v1/artifacts/{req_id}/trace")
    matrix = client.get("/api/v1/artifacts/matrix")
    listing = client.get("/api/v1/artifacts?type=requirement")
    health = client.get("/api/v1/artifacts/health")

    assert patch.status_code == 200
    assert patch.json()["status"] == "reviewed"
    assert link.status_code == 200
    assert trace.json()["summary"]["links"] == 1
    assert matrix.json()["summary"]["partial"] == 1
    assert listing.json()["total"] == 1
    assert health.json()["artifacts"] == 2


def test_artifacts_api_returns_400_for_bad_type(tmp_path, monkeypatch):
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.post("/api/v1/artifacts", json={"type": "bad", "title": "Bad"})

    assert response.status_code == 400
