import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import (
    TOOLS,
    handle_test_run_import_junit,
    handle_test_run_list,
    handle_test_run_record,
)
from src.api.testing_api import router
from src.services.rentgen import artifact_graph, test_evidence

JUNIT_XML = """
<testsuite xmlns="urn:junit" name="Sales">
  <testcase classname="SalesSuite" name="posts_order" time="0.125" />
  <testcase classname="SalesSuite" name="rejects_bad_limit" time="0.050">
    <failure message="Expected validation error" />
  </testcase>
  <testcase classname="SalesSuite" name="legacy_case">
    <skipped message="Disabled until fixture is refreshed" />
  </testcase>
</testsuite>
"""


def test_record_test_run_links_change_set_and_cases(tmp_path):
    store_path = tmp_path / "test_runs.json"
    artifact_path = tmp_path / "artifact_graph.json"
    artifact_graph.create_artifact(
        {"id": "CHG-TEST", "type": "change_set", "title": "Credit limit validation"},
        path=artifact_path,
    )

    run = test_evidence.record_test_run(
        run_id="TR-1",
        title="YAxUnit smoke",
        framework="YAxUnit",
        change_set_id="CHG-TEST",
        command="vrunner xunit --settings xunit.json",
        results=[
            {
                "id": "SalesSuite::posts_order",
                "name": "posts_order",
                "status": "PASSED",
                "duration_ms": "12.5",
            },
            {
                "id": "SalesSuite::rejects_bad_limit",
                "name": "rejects_bad_limit",
                "status": "failed",
                "duration_ms": "bad",
            },
        ],
        evidence=[{"kind": "stdout", "path": "artifacts/xunit.log"}],
        path=store_path,
        artifact_path=artifact_path,
    )
    trace = artifact_graph.trace_artifact("CHG-TEST", path=artifact_path)
    listing = test_evidence.list_test_runs(status="failed", path=store_path)

    assert run["id"] == "TR-1"
    assert run["status"] == "failed"
    assert run["summary"]["passed"] == 1
    assert run["summary"]["failed"] == 1
    assert run["results"][1]["duration_ms"] == 0
    assert run["artifact_sync"]["links"] == 3
    assert listing["total"] == 1
    assert {"test_run", "test_case"} <= {node["type"] for node in trace["nodes"]}


def test_import_junit_xml_supports_namespaces_and_skipped_results(tmp_path):
    run = test_evidence.import_junit_xml(
        xml_text=JUNIT_XML,
        title="Vanessa acceptance",
        framework="JUnit",
        path=tmp_path / "test_runs.json",
        artifact_path=tmp_path / "artifact_graph.json",
    )

    assert run["title"] == "Vanessa acceptance"
    assert run["status"] == "failed"
    assert run["summary"]["total"] == 3
    assert run["summary"]["failed"] == 1
    assert run["summary"]["skipped"] == 1
    assert run["results"][0]["duration_ms"] == 125


def test_testing_api_records_lists_details_and_imports(tmp_path, monkeypatch):
    monkeypatch.setattr(test_evidence, "STORE_PATH", tmp_path / "test_runs.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    created = client.post(
        "/api/v1/testing/runs",
        json={
            "id": "TR-API",
            "title": "API smoke",
            "framework": "YAxUnit",
            "results": [{"id": "Smoke::ok", "name": "ok", "status": "passed"}],
            "dry_run": True,
        },
    )
    listing = client.get("/api/v1/testing/runs?status=passed")
    details = client.get("/api/v1/testing/runs/TR-API")
    imported = client.post(
        "/api/v1/testing/runs/import-junit",
        json={"xml_text": JUNIT_XML, "title": "Imported JUnit"},
    )
    bad_import = client.post(
        "/api/v1/testing/runs/import", json={"xml_text": "<broken"}
    )

    assert created.status_code == 200
    assert created.json()["dry_run"] is True
    assert listing.json()["total"] == 1
    assert details.json()["id"] == "TR-API"
    assert imported.json()["summary"]["total"] == 3
    assert bad_import.status_code == 400


@pytest.mark.asyncio
async def test_mcp_test_evidence_tools_are_registered_and_work(tmp_path, monkeypatch):
    monkeypatch.setattr(test_evidence, "STORE_PATH", tmp_path / "test_runs.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")

    names = {tool.name for tool in TOOLS}
    assert {"test_run_record", "test_run_import_junit", "test_run_list"} <= names

    recorded = await handle_test_run_record(
        {
            "id": "TR-MCP",
            "title": "MCP smoke",
            "framework": "YAxUnit",
            "results": [{"id": "Smoke::ok", "name": "ok", "status": "passed"}],
        }
    )
    imported = await handle_test_run_import_junit(
        {"xml_text": JUNIT_XML, "title": "MCP JUnit"}
    )
    listing = await handle_test_run_list({"limit": 10})

    assert recorded["id"] == "TR-MCP"
    assert imported["summary"]["failed"] == 1
    assert listing["total"] == 2
