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
