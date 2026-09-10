import shutil

import pytest

import test_metadata_plans as fixtures
from rentgen_core import metadata_plans as plans
from rentgen_core.metadata_preview import build_preview
from rentgen_core.errors import CoreError

project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)


def test_two_diffs_retain_unknown_deletions_and_form_changes(captured, tmp_path):
    ctx, request = captured
    plan = plans.create_plan(ctx, request)
    run = tmp_path / "preview"
    run.mkdir()
    plans.materialize(ctx, plan, run / "input")
    shutil.copytree(fixtures.FIXTURE, run / "baseline-xml")
    shutil.copytree(fixtures.FIXTURE.parent / "renamed", run / "candidate-xml")
    preview = build_preview(ctx, plan, run)
    # The test source also contains an unrelated module. Losing it on import must
    # be visible, never silently folded into the requested rename.
    assert any(
        c["kind"] == "deleted" and c["path"].endswith("Module.bsl")
        for c in preview["normalization"]["changes"]
    )
    assert any(
        c["path"].endswith("Ext/Form.xml") and "Объект.SKU" in c["diff"]
        for c in preview["edit"]["changes"]
    )
    assert preview["apply"]["status"] == "unavailable"
    assert preview["platform_check"] == "not_run"
    target = run / "candidate-xml/Catalogs/Products.xml"
    target.write_bytes(
        target.read_bytes().replace(
            request["attribute"]["uuid"].encode(),
            b"00000000-0000-0000-0000-000000000001",
        )
    )
    with pytest.raises(CoreError):
        build_preview(ctx, plan, run)
