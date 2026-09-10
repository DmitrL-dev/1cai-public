"""Metadata intent binds captured bytes and real object ownership, not live paths."""
from dataclasses import asdict
from pathlib import Path
import shutil
from uuid import uuid4

import pytest
import rentgen_core as api
import test_project_core_publication as fixtures
from project_access_test_support import force_legacy_membership
from rentgen_core import metadata_plans as plans
from rentgen_core.source_configuration import SourceLayerSpec

project, scanner, pytestmark = fixtures.project, fixtures.scanner, fixtures.pytestmark
FIXTURE = (
    Path(__file__).resolve().parents[2] / "packaging/fixtures/edt-metadata-v1/created"
)


@pytest.fixture
def captured(project):
    ctx, resolver, _, _ = project
    shutil.copytree(FIXTURE, ctx.source_root, dirs_exist_ok=True)
    api.configure_source_layers(
        ctx,
        (SourceLayerSpec("base", 0, "base", ".", "designer_xml"),),
        expected_revision=1,
    )
    fixtures.publish(project)
    ctx = resolver.resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    request = {
        "schema": 1,
        "operation": "rename_catalog_attribute",
        "snapshot": asdict(ctx.snapshot),
        "layer_id": "base",
        "catalog": {"name": "Products", "uuid": "fb28b18e-d2a3-4f48-8390-c0d609c9e7c0"},
        "attribute": {
            "name": "Article",
            "uuid": "eb298009-8fc5-4a2f-8812-902daeed99df",
        },
        "new_name": "SKU",
    }
    return ctx, request


def test_plan_and_materialization_ignore_later_live_edits(captured, tmp_path):
    ctx, request = captured
    plan = plans.create_plan(ctx, request)
    live = ctx.source_root / "Catalogs/Products.xml"
    expected = live.read_bytes()
    live.write_bytes(b"subsequent live change")
    assert plans.create_plan(ctx, request) == plan
    target = tmp_path / "materialized"
    inventory = plans.materialize(ctx, plan, target)
    assert (target / "Catalogs/Products.xml").read_bytes() == expected
    assert len(inventory) == plan["input_files"]
    assert plan["source_ref"]["snapshot"] == request["snapshot"]


@pytest.mark.parametrize(
    "key", ["catalog", "attribute", "snapshot", "layer_id", "new_name"]
)
def test_false_identity_wrong_snapshot_layer_and_noop_are_refused(captured, key):
    ctx, request = captured
    if key in {"catalog", "attribute"}:
        request[key]["uuid"] = str(uuid4())
    elif key == "snapshot":
        request[key]["snapshot_id"] = "a" * 64
        request[key]["manifest_hash"] = "a" * 64
    elif key == "layer_id":
        request[key] = "extension"
    else:
        request[key] = "article"
    with pytest.raises(api.CoreError):
        plans.create_plan(ctx, request)


def test_tampered_plan_does_not_materialize_anything(captured, tmp_path):
    ctx, request = captured
    plan = plans.create_plan(ctx, request)
    plan["input_digest"] = "0" * 64
    target = tmp_path / "must-not-exist"
    with pytest.raises(api.CoreError):
        plans.materialize(ctx, plan, target)
    assert not target.exists()


def test_authorization_precedes_request_parsing(captured):
    ctx, _ = captured
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:read"})
    with pytest.raises(api.CoreError) as error:
        plans.create_plan(ctx, None)
    assert error.value.code == "PROJECT_FORBIDDEN"


@pytest.mark.parametrize("change", ["duplicate_uuid", "foreign_namespace"])
def test_ambiguous_or_foreign_metadata_is_not_an_edit_target(captured, project, change):
    ctx, request = captured
    catalog = ctx.source_root / "Catalogs/Products.xml"
    if change == "duplicate_uuid":
        (ctx.source_root / "Unrecognized.xml").write_bytes(catalog.read_bytes())
    else:
        catalog.write_bytes(
            catalog.read_bytes().replace(
                b"http://v8.1c.ru/8.3/MDClasses",
                b"https://example.invalid/foreign-metadata",
            )
        )
    fixtures.publish(project)
    selected = project[1].resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    request["snapshot"] = asdict(selected.snapshot)
    with pytest.raises(api.CoreError):
        plans.create_plan(selected, request)
