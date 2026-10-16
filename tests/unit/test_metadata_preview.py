from dataclasses import asdict
import hashlib
import shutil

import pytest

import rentgen_core as api
import test_metadata_plans as fixtures
from rentgen_core import metadata_plans as plans
from rentgen_core.metadata_preview import build_preview
from rentgen_core.errors import CoreError
from test_metadata_rename_identity import (
    UNRELATED_FILES,
    UNRELATED_PATH,
    unrelated_uuid,
)
from test_metadata_three_way_materialize import (
    PICTURE,
    PICTURE_BYTES,
    TEMPLATE,
    TEMPLATE_BYTES,
)

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


def _write(root, files):
    for path, raw in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)


def test_rename_keeps_same_name_unrelated_objects_and_uuids(
    captured, project, tmp_path
):
    ctx, request = captured
    _write(ctx.source_root, UNRELATED_FILES)
    fixtures.fixtures.publish(project)
    ctx = project[1].resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    request["snapshot"] = asdict(ctx.snapshot)
    # A same-name attribute in another catalog is not an ambiguous target.
    plan = plans.create_plan(ctx, request)
    run = tmp_path / "preview"
    run.mkdir()
    plans.materialize(ctx, plan, run / "input")
    for phase, name in (("created", "baseline-xml"), ("renamed", "candidate-xml")):
        shutil.copytree(fixtures.FIXTURE.parent / phase, run / name)
        _write(run / name, UNRELATED_FILES)

    preview = build_preview(ctx, plan, run)

    assert sorted(change["path"] for change in preview["edit"]["changes"]) == [
        "Catalogs/Products.xml",
        "Catalogs/Products/Forms/ItemForm/Ext/Form.xml",
    ]
    rows = {
        name: {row["path"]: row for row in preview["inventories"][name]}
        for name in ("original", "baseline", "candidate")
    }
    for path, raw in UNRELATED_FILES.items():
        assert rows["original"][path] == rows["baseline"][path]
        assert rows["baseline"][path] == rows["candidate"][path]
        assert rows["candidate"][path]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert preview["identity"] == {
        "catalog_uuid": request["catalog"]["uuid"],
        "attribute_uuid": request["attribute"]["uuid"],
        "new_name": "SKU",
    }
    candidate = (run / "candidate-xml/Catalogs/Products.xml").read_bytes()
    assert request["attribute"]["uuid"].encode() in candidate
    assert unrelated_uuid(request["attribute"]["uuid"]).encode() not in candidate

    unrelated = run / "candidate-xml" / UNRELATED_PATH
    unrelated.write_bytes(
        unrelated.read_bytes().replace(b"<Name>Article</Name>", b"<Name>SKU</Name>")
    )
    with pytest.raises(CoreError) as error:
        build_preview(ctx, plan, run)
    assert error.value.code == "METADATA_PLAN_INVALID"


def test_changed_binary_resource_is_reported_by_hash_and_never_text_merged(
    captured, project, tmp_path
):
    """IDE-SC-17: no MXL/picture model; a binary change stays opaque bytes."""
    ctx, request = captured
    binaries = {TEMPLATE: TEMPLATE_BYTES, PICTURE: PICTURE_BYTES}
    _write(ctx.source_root, binaries)
    fixtures.fixtures.publish(project)
    ctx = project[1].resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    request["snapshot"] = asdict(ctx.snapshot)
    plan = plans.create_plan(ctx, request)
    run = tmp_path / "preview"
    run.mkdir()
    plans.materialize(ctx, plan, run / "input")
    changed = TEMPLATE_BYTES[:-1] + b"\x01"
    for phase, name in (("created", "baseline-xml"), ("renamed", "candidate-xml")):
        shutil.copytree(fixtures.FIXTURE.parent / phase, run / name)
        _write(run / name, binaries)
    _write(run / "candidate-xml", {TEMPLATE: changed})

    preview = build_preview(ctx, plan, run)

    rows = {change["path"]: change for change in preview["edit"]["changes"]}
    assert PICTURE not in rows
    row = rows[TEMPLATE]
    assert row["kind"] == "modified"
    assert row["text_status"] == "binary_or_non_utf8"
    assert "diff" not in row
    assert row["before"]["sha256"] == hashlib.sha256(TEMPLATE_BYTES).hexdigest()
    assert row["after"]["sha256"] == hashlib.sha256(changed).hexdigest()
    assert row["before"]["size"] == row["after"]["size"]
    assert preview["edit"]["text_complete"] is False
    assert preview["apply"]["status"] == "unavailable"
    assert not any(
        change["path"] in binaries for change in preview["normalization"]["changes"]
    )
