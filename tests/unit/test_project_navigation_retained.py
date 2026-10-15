"""Real published-snapshot metadata navigation on the Windows retained backend."""
from dataclasses import asdict, replace
import json

import pytest

import rentgen_core as api
from rentgen_core import cli, metadata, project_navigation as nav
from project_access_test_support import grant_membership, revoke_membership
import test_metadata_plans as fixtures

project, scanner, captured = fixtures.project, fixtures.scanner, fixtures.captured
pytestmark = fixtures.pytestmark


def test_search_and_object_are_bound_to_exact_retained_bytes(captured):
    ctx, _ = captured
    result = nav.search(ctx, query="Products", metadata_type="Catalog", layer_id="base")
    assert result["schema"] == 1 and result["snapshot"] == asdict(ctx.snapshot)
    assert result["returned"] == result["total_matches"] == 1
    preview = result["objects"][0]
    assert preview["source_ref"]["relative_path"] == "Catalogs/Products.xml"
    assert preview["uuid_status"] == "unverified"
    details = nav.object_details(ctx, layer_id="base", relative_path="Catalogs/Products.xml")
    assert details == {**metadata.get_metadata_object(ctx, layer_id="base", relative_path="Catalogs/Products.xml"), "schema": 1}
    assert details["object"]["attributes"]["items"][0]["name"] == "Article"
    pinned_search = nav.search(ctx, query="Products", layer_id="base")
    (ctx.source_root / "Catalogs/Products.xml").write_bytes(b"changed after publication")
    assert nav.search(ctx, query="Products", layer_id="base") == pinned_search
    assert nav.object_details(ctx, layer_id="base", relative_path="Catalogs/Products.xml") == details


def test_read_permission_alone_is_sufficient_and_revocation_is_current(captured):
    ctx, _ = captured
    reader = api.Principal("navigation-read-only", "local_os")
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        grant_membership(tx, reader, {"project:read"})
    selected = replace(ctx, principal=reader)
    assert nav.summary(selected)["snapshot"] == asdict(ctx.snapshot)
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        revoke_membership(tx, reader)
    with pytest.raises(api.CoreError) as error:
        nav.object_details(selected, layer_id="base", relative_path="Catalogs/Products.xml")
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_truncation_remains_visible_and_exact_layer_is_required(captured):
    ctx, _ = captured
    result = nav.search(ctx, limit=1)
    assert result["returned"] <= 1
    assert result["truncated"] == (result["total_matches"] > result["returned"])
    with pytest.raises(api.CoreError) as error:
        nav.search(ctx, layer_id="absent")
    assert error.value.code == "SOURCE_LAYER_NOT_FOUND"
    with pytest.raises(api.CoreError) as error:
        nav.object_details(ctx, layer_id="base", relative_path="Catalogs/Absent.xml")
    assert error.value.code == "METADATA_OBJECT_NOT_FOUND"


@pytest.mark.parametrize("command", ["metadata-summary", "metadata-search", "metadata-object"])
def test_actual_cli_resolves_selected_snapshot_and_returns_same_projection(captured, monkeypatch, capsys, command):
    ctx, _ = captured
    monkeypatch.setattr(cli, "current_local_principal", lambda: ctx.principal)
    argv = [command, "--registry", str(ctx.source_root.parent / "registry.sqlite3"),
            "--project", ctx.project_id, "--snapshot", ctx.snapshot.snapshot_id]
    if command == "metadata-object":
        argv += ["--layer=base", "--path=Catalogs/Products.xml"]
        expected = nav.object_details(ctx, layer_id="base", relative_path="Catalogs/Products.xml")
    elif command == "metadata-search":
        argv += ["--query=Products", "--type=Catalog", "--limit=1"]
        expected = nav.search(ctx, query="Products", metadata_type="Catalog", limit=1)
    else:
        expected = nav.summary(ctx)
    capsys.readouterr()
    assert cli.main(argv) == 0
    output = capsys.readouterr()
    assert not output.err and json.loads(output.out)["result"] == expected
