from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.archi_api import health_check, router
from src.api.dependencies import get_archi_exporter, get_graph_service


class _GraphService:
    def __init__(self, fail: bool = False):
        self.fail = fail

    async def execute_query(self, query, params):
        if self.fail:
            raise RuntimeError("neo4j offline")
        return [{"test": 1}]


class _ArchiExporter:
    async def export_to_archimate(
        self, output_path, filters, max_nodes, max_relationships
    ):
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(
                """<?xml version="1.0" encoding="utf-8"?>
<model xmlns="http://www.opengroup.org/xsd/archimate/3.0/">
  <elements>
    <element identifier="e1" type="ApplicationComponent" />
    <element identifier="e2" type="ApplicationFunction" />
  </elements>
  <relationships>
    <relationship identifier="r1" type="Flow" source="e1" target="e2" />
  </relationships>
</model>
"""
            )
        return output_path


def _client(service):
    if hasattr(health_check, "_cache"):
        health_check._cache.clear()
    app = FastAPI()
    app.dependency_overrides[get_graph_service] = lambda: service
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def _export_client(exporter):
    app = FastAPI()
    app.dependency_overrides[get_archi_exporter] = lambda: exporter
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_archi_health_is_legacy_optional_when_graphservice_is_offline():
    client = _client(_GraphService(fail=True))

    response = client.get("/api/v1/archi/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "legacy_optional_unavailable"
    assert payload["core"] is False
    assert payload["mode"] == "legacy_optional"
    assert "Neo4j GraphService" in payload["requires"]


def test_archi_health_reports_optional_ready_when_graphservice_responds():
    client = _client(_GraphService())

    response = client.get("/api/v1/archi/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "legacy_optional_ready"
    assert payload["core"] is False


def test_archi_export_counts_generated_archimate_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = _export_client(_ArchiExporter())

    response = client.post(
        "/api/v1/archi/export", json={"output_filename": "unit.archimate"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["file_path"].endswith("unit.archimate")
    assert payload["elements_count"] == 2
    assert payload["relationships_count"] == 1
