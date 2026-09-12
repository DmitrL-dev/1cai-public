import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4
import shutil

import pytest
import test_metadata_plans as fixtures
from rentgen_core import metadata_plans as plans, metadata_runs as runs
from rentgen_core.edt_execution import write_record
from rentgen_core.errors import CoreError
from rentgen_core.metadata_preview import build_preview

project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)


def test_readback_rejects_tampering_and_incomplete_run_never_restarts(
    captured, monkeypatch
):
    ctx, request = captured
    plan = plans.create_plan(ctx, request)
    operation = str(uuid4())
    run = runs.run_path(ctx, operation)
    run.mkdir(parents=True)
    binding = {
        "schema": 1,
        "project_id": ctx.project_id,
        "operation_id": operation,
        "profile_id": "a" * 64,
        "plan": plan,
    }
    write_record(run / "runtime-request.json", binding)

    def forbidden(*args, **kwargs):
        pytest.fail("An existing operation was restarted")

    monkeypatch.setattr(runs, "edt_session", forbidden)
    with pytest.raises(CoreError) as error:
        asyncio.run(runs.create_preview(ctx, plan, "a" * 64, operation))
    assert error.value.code == "METADATA_RUN_INCOMPLETE"
    plans.materialize(ctx, plan, run / "input")
    shutil.copytree(fixtures.FIXTURE, run / "baseline-xml")
    shutil.copytree(fixtures.FIXTURE.parent / "renamed", run / "candidate-xml")
    expected = runs._result(binding, build_preview(ctx, plan, run))
    write_record(run / "preview.json", expected)
    write_record(
        run / "runtime-closed.json", {"status": "closed", "metadata_verified": False}
    )
    assert runs.get_preview(ctx, operation) == expected
    assert asyncio.run(runs.create_preview(ctx, plan, "a" * 64, operation)) == expected
    expected["preview"]["apply"]["status"] = "accepted"
    (run / "preview.json").write_text(json.dumps(expected), "utf-8")
    with pytest.raises(CoreError):
        runs.get_preview(ctx, operation)


def test_preview_token_must_match_the_typed_intent(captured):
    _, request = captured
    header = "---\naction: preview\nobjectFqn: Catalog.Products.Attribute.Article\nnewName: SKU\nproblems: 0\ncontentHash: 0123456789abcdef\n---\nUntrusted explanation is data."

    def response(text):
        return SimpleNamespace(
            content=[
                SimpleNamespace(type="resource", resource=SimpleNamespace(text=text))
            ]
        )

    assert runs.preview_hash(response(header), request) == "0123456789abcdef"
    for changed in (
        header.replace("newName: SKU", "newName: Other"),
        header.replace("problems: 0", "problems: 1"),
        header.replace("\n---\n", "\ncontentHash: 1111111111111111\n---\n"),
    ):
        with pytest.raises(CoreError):
            runs.preview_hash(response(changed), request)


def _finished_run(captured):
    ctx, request = captured
    plan = plans.create_plan(ctx, request)
    operation = str(uuid4())
    run = runs.run_path(ctx, operation)
    run.mkdir(parents=True)
    binding = {
        "schema": 1,
        "project_id": ctx.project_id,
        "operation_id": operation,
        "profile_id": "a" * 64,
        "plan": plan,
    }
    write_record(run / "runtime-request.json", binding)
    plans.materialize(ctx, plan, run / "input")
    shutil.copytree(fixtures.FIXTURE, run / "baseline-xml")
    shutil.copytree(fixtures.FIXTURE.parent / "renamed", run / "candidate-xml")
    preview = runs._result(binding, build_preview(ctx, plan, run))
    write_record(run / "preview.json", preview)
    write_record(
        run / "runtime-closed.json", {"status": "closed", "metadata_verified": False}
    )
    return ctx, operation, run, preview


def _evidence(preview):
    inventories = preview["preview"]["inventories"]
    passed = {"status": "passed", "counts": {"errors": 0, "failures": 0}}
    return {
        "schema": 1,
        "source": "real 1C/YAxUnit on a new owned file infobase",
        "source_preview_id": preview["preview_id"],
        "platform_sha256": "1" * 64,
        "ibcmd_sha256": "2" * 64,
        "engine_cfe_sha256": "3" * 64,
        "source_inventories": {
            "original": inventories["original"],
            "normalized": inventories["baseline"],
            "renamed": inventories["candidate"],
        },
        "reports": {
            name: passed
            for name in ("seed", "reopen-original", "normalized", "renamed", "restored")
        }
        | {"wrong-uuid": {"status": "failed", "counts": {"errors": 0, "failures": 1}}},
        "records": 3,
        "value_cases": ["unicode", "empty", "length_32"],
        "full_record_reference_preserved": True,
        "schema_restore_preserves_data": True,
        "wrong_uuid_compiles_but_loses_data": True,
        "product_apply_undo": False,
        "unmodified_preview_execution": True,
    }


def test_business_evidence_is_bound_to_preview_and_readable_after_restart(captured):
    ctx, operation, run, preview = _finished_run(captured)
    result = runs.attach_business_evidence(ctx, operation, _evidence(preview))
    assert result["preview"]["business_data_test"]["status"] == "passed"
    assert result["business_evidence"]["records"] == 3
    assert runs.get_preview(ctx, operation) == result
    assert (run / "business-evidence.json").exists()


def test_business_evidence_rejects_rebinding_and_tampering(captured):
    ctx, operation, run, preview = _finished_run(captured)
    evidence = _evidence(preview)
    evidence["source_preview_id"] = "f" * 64
    with pytest.raises(CoreError, match="preview"):
        runs.attach_business_evidence(ctx, operation, evidence)
    evidence = _evidence(preview)
    runs.attach_business_evidence(ctx, operation, evidence)
    (run / "business-evidence.json").write_text("{}", "utf-8")
    with pytest.raises(CoreError):
        runs.get_preview(ctx, operation)
