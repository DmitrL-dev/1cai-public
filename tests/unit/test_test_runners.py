import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.ai.mcp.server import (
    TOOLS,
    handle_test_result_import_file,
    handle_test_runner_plan,
    handle_test_runner_run,
)
from src.api.testing_api import router
from src.services.rentgen import (
    artifact_graph,
    change_sets,
    policy_engine,
    test_evidence,
    test_runners,
)

JUNIT_XML = """
<testsuite name="Runner">
  <testcase classname="RunnerSuite" name="ok" time="0.010" />
  <testcase classname="RunnerSuite" name="bad">
    <failure message="boom" />
  </testcase>
</testsuite>
"""


def test_runner_plan_and_dry_run_record_are_stored(tmp_path):
    store_path = tmp_path / "test_runs.json"
    artifact_path = tmp_path / "artifact_graph.json"

    plan = test_runners.build_runner_plan(
        "yaxunit",
        test_files=["test_parsers.bsl"],
        output_dir=str(tmp_path / "out"),
    )
    dry_run = test_runners.run_test_adapter(
        "yaxunit",
        test_files=["test_parsers.bsl"],
        output_dir=str(tmp_path / "out"),
        path=store_path,
        artifact_path=artifact_path,
    )

    assert plan["adapter"] == "yaxunit"
    assert plan["dry_run"] is True
    assert "--dry-run" in plan["command"]
    assert dry_run["executed"] is False
    assert dry_run["run"]["dry_run"] is True
    assert dry_run["run"]["status"] == "warning"
    assert test_evidence.get_test_run(dry_run["run"]["id"], path=store_path) is not None


def test_import_result_files_and_evidence_bundle(tmp_path):
    store_path = tmp_path / "test_runs.json"
    artifact_path = tmp_path / "artifact_graph.json"
    junit_path = tmp_path / "report.xml"
    junit_path.write_text(JUNIT_XML, encoding="utf-8")
    allure_dir = tmp_path / "allure"
    allure_dir.mkdir()
    (allure_dir / "broken-result.json").write_text(
        '{"uuid":"a1","name":"broken_case","status":"broken","statusDetails":{"message":"broken"},"time":{"duration":33}}',
        encoding="utf-8",
    )

    junit = test_runners.import_result_file(
        str(junit_path),
        title="JUnit file",
        change_set_id="CHG-JUNIT",
        path=store_path,
        artifact_path=artifact_path,
    )
    allure = test_runners.import_result_file(
        str(allure_dir),
        result_format="allure",
        title="Allure dir",
        path=store_path,
        artifact_path=artifact_path,
    )
    bundle = test_runners.create_evidence_bundle(
        junit["id"],
        attachment_paths=[str(junit_path), str(tmp_path / "missing.log")],
        bundle_root=tmp_path / "bundles",
    )

    assert junit["status"] == "failed"
    assert junit["summary"]["failed"] == 1
    assert allure["summary"]["error"] == 1
    assert bundle["summary"]["present"] == 1
    assert bundle["summary"]["missing"] == 1
    assert bundle["files"][0]["sha256"]


def test_testing_api_exposes_runner_and_file_import(tmp_path, monkeypatch):
    monkeypatch.setattr(test_evidence, "STORE_PATH", tmp_path / "test_runs.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")
    monkeypatch.setattr(test_runners, "DEFAULT_BUNDLE_ROOT", tmp_path / "bundles")
    junit_path = tmp_path / "report.xml"
    junit_path.write_text(JUNIT_XML, encoding="utf-8")

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    catalog = client.get("/api/v1/testing/runners")
    plan = client.post(
        "/api/v1/testing/runners/plan",
        json={"adapter": "yaxunit", "test_files": ["test_parsers.bsl"]},
    )
    dry_run = client.post(
        "/api/v1/testing/runners/run",
        json={"adapter": "yaxunit", "test_files": ["test_parsers.bsl"]},
    )
    imported = client.post(
        "/api/v1/testing/results/import-file",
        json={"result_path": str(junit_path), "title": "API JUnit"},
    )
    bundle = client.post(
        f"/api/v1/testing/runs/{dry_run.json()['run']['id']}/bundle",
        json={"attachment_paths": [str(junit_path)]},
    )

    assert catalog.json()["defaults"]["dry_run"] is True
    assert plan.json()["adapter"] == "yaxunit"
    assert dry_run.json()["executed"] is False
    assert imported.json()["summary"]["failed"] == 1
    assert bundle.json()["summary"]["present"] == 1


@pytest.mark.asyncio
async def test_mcp_runner_tools_are_registered_and_work(tmp_path, monkeypatch):
    monkeypatch.setattr(test_evidence, "STORE_PATH", tmp_path / "test_runs.json")
    monkeypatch.setattr(artifact_graph, "STORE_PATH", tmp_path / "artifact_graph.json")
    junit_path = tmp_path / "report.xml"
    junit_path.write_text(JUNIT_XML, encoding="utf-8")

    names = {tool.name for tool in TOOLS}
    assert {"test_runner_plan", "test_runner_run", "test_result_import_file"} <= names

    plan = await handle_test_runner_plan(
        {"adapter": "yaxunit", "test_files": ["test_parsers.bsl"]}
    )
    dry_run = await handle_test_runner_run(
        {"adapter": "yaxunit", "test_files": ["test_parsers.bsl"]}
    )
    imported = await handle_test_result_import_file(
        {"result_path": str(junit_path), "title": "MCP JUnit"}
    )

    assert plan["adapter"] == "yaxunit"
    assert dry_run["run"]["dry_run"] is True
    assert imported["summary"]["failed"] == 1


def test_change_set_policy_blocks_failed_test_evidence(tmp_path, monkeypatch):
    change_store = tmp_path / "change_sets.json"
    artifact_store = tmp_path / "artifact_graph.json"
    test_store = tmp_path / "test_runs.json"
    monkeypatch.setattr(
        policy_engine, "EVALUATIONS_PATH", tmp_path / "policy_evaluations.json"
    )
    monkeypatch.setattr(policy_engine, "WAIVERS_PATH", tmp_path / "policy_waivers.json")
    change_sets.create_change_set(
        {
            "id": "CHG-FAILED-TESTS",
            "title": "Posting validation",
            "changed_modules": ["Documents/Order/Ext/ObjectModule.bsl"],
        },
        path=change_store,
        artifact_path=artifact_store,
    )
    test_evidence.record_test_run(
        run_id="TR-FAILED",
        title="Failed regression",
        framework="YAxUnit",
        change_set_id="CHG-FAILED-TESTS",
        results=[{"id": "Regression::bad", "name": "bad", "status": "failed"}],
        path=test_store,
        artifact_path=artifact_store,
    )

    with pytest.raises(ValueError):
        change_sets.transition_change_set(
            "CHG-FAILED-TESTS",
            status="approved",
            actor="qa",
            path=change_store,
            artifact_path=artifact_store,
        )
    evaluations = policy_engine.list_evaluations(
        path=tmp_path / "policy_evaluations.json"
    )
    matched_rules = {
        item["rule_id"]
        for item in evaluations["items"][0]["results"]
        if item.get("matched")
    }

    assert "tests.evidence.failed_run" in matched_rules
