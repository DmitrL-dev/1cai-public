"""Navigation boundary/CLI tests with real membership state and injected reads.

Retained Windows IO and real metadata parsing are exercised separately by
test_project_navigation_retained.py and the installed editor gate.
"""
from dataclasses import asdict, replace
import json
from types import SimpleNamespace

import pytest

import rentgen_core as api
from rentgen_core import capabilities, cli, metadata, project_navigation as nav
from rentgen_core.local import LocalRuntime
from project_access_test_support import grant_membership, revoke_membership


@pytest.fixture
def scope(tmp_path):
    owner = api.Principal("navigation-owner", "local_os")
    reader = api.Principal("navigation-reader", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(
        owner, source_root=source, state_root=tmp_path / "state", display_name="Navigation"
    )
    runtime = LocalRuntime(registry.path, graph_reader_factory=object())
    ctx = runtime.state_context(owner, project.project_id)
    with ctx.state.transaction(owner, write=True) as tx:
        grant_membership(tx, reader, {"project:read"})
    ctx = replace(
        ctx, principal=reader,
        snapshot=api.SnapshotRef(project.project_id, "a" * 64, "a" * 64),
    )

    def revoke():
        with ctx.state.transaction(owner, write=True) as tx:
            revoke_membership(tx, reader)

    return SimpleNamespace(ctx=ctx, owner=owner, runtime=runtime, revoke=revoke)


def envelope(scope):
    return {
        "snapshot": asdict(scope.ctx.snapshot), "parser_profiles": ["designer_xml_v1"],
        "identity_status": "source_path_only", "completeness": "unsupported_layers",
        "objects": [], "returned": 0, "total_matches": 0, "truncated": False,
        "layers": [], "source_refs": [], "validation_summary": {"metadata_scan": {}},
    }


@pytest.mark.parametrize("operation", ["summary", "search", "object"])
def test_versioned_projection_preserves_exact_reader_coverage(scope, monkeypatch, operation):
    expected = envelope(scope)
    calls = []
    def read(ctx, *args, **kwargs):
        calls.append((ctx, args, kwargs))
        return expected
    if operation == "summary":
        monkeypatch.setattr(metadata, "metadata_summary", read)
        actual = nav.summary(scope.ctx, layer_id="base")
    elif operation == "search":
        monkeypatch.setattr(metadata, "search_metadata", read)
        actual = nav.search(scope.ctx, query="Товар", metadata_type="Catalog", limit=17)
    else:
        monkeypatch.setattr(metadata, "get_metadata_object", read)
        actual = nav.object_details(scope.ctx, layer_id="base", relative_path="Catalogs/Products.xml")
    assert actual == {**expected, "schema": 1}
    assert actual["completeness"] == "unsupported_layers"
    assert len(calls) == 1 and calls[0][0] is scope.ctx
    assert "schema" not in expected


def test_revoked_membership_precedes_filter_validation_and_reader_io(scope, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Revoked navigation attempted metadata IO")
    monkeypatch.setattr(metadata, "search_metadata", forbidden)
    scope.revoke()
    with pytest.raises(api.CoreError) as error:
        nav.search(scope.ctx, query="\0private-input", layer_id="../private")
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_revocation_during_materialization_does_not_release_result(scope, monkeypatch):
    def read(*args, **kwargs):
        scope.revoke()
        return {**envelope(scope), "objects": ["PRIVATE_METADATA"]}
    monkeypatch.setattr(metadata, "search_metadata", read)
    with pytest.raises(api.CoreError) as error:
        nav.search(scope.ctx)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_reader_cannot_substitute_another_snapshot_even_for_empty_results(scope, monkeypatch):
    result = envelope(scope)
    result["snapshot"] = {**result["snapshot"], "snapshot_id": "b" * 64, "manifest_hash": "b" * 64}
    monkeypatch.setattr(metadata, "metadata_summary", lambda *a, **k: result)
    with pytest.raises(api.CoreError) as error:
        nav.summary(scope.ctx)
    assert error.value.code == "METADATA_RESULT_MISMATCH"


@pytest.mark.parametrize("query", [None, 3, "x" * 257, "\0", "\u202e", "\ud800"], ids=["none", "integer", "long", "nul", "bidi", "surrogate"])
def test_search_rejects_unsafe_filters_without_reader_io(scope, monkeypatch, query):
    monkeypatch.setattr(metadata, "search_metadata", lambda *a, **k: pytest.fail("Invalid filter reached reader"))
    with pytest.raises(api.CoreError) as error:
        nav.search(scope.ctx, query=query)
    assert error.value.code == "INVALID_QUERY_OPTIONS"


@pytest.mark.parametrize("limit", [True, 0, 201, 1.5])
def test_search_limits_are_typed_and_bounded(scope, limit):
    with pytest.raises(api.CoreError) as error:
        nav.search(scope.ctx, limit=limit)
    assert error.value.code == "INVALID_QUERY_OPTIONS"


@pytest.mark.parametrize("layer,path", [(None, "Catalogs/A.xml"), ("../base", "Catalogs/A.xml"), ("base", "../A.xml"), ("base", "/A.xml")])
def test_object_requires_exact_layer_and_relative_locator(scope, layer, path):
    with pytest.raises(api.CoreError):
        nav.object_details(scope.ctx, layer_id=layer, relative_path=path)


def arguments(operation="metadata-search"):
    values = [operation, "--registry", "registry.db", "--project", "project", "--snapshot", "a" * 64]
    if operation == "metadata-object":
        values += ["--layer=base", "--path=Catalogs/A.xml"]
    return values


@pytest.mark.parametrize("operation", sorted(nav.OPERATIONS))
def test_cli_requires_explicit_snapshot_and_rejects_implicit_head(operation):
    values = arguments(operation)
    index = values.index("--snapshot")
    del values[index:index + 2]
    with pytest.raises(api.CoreError) as error:
        cli._parser().parse_args(values)
    assert error.value.code == "INVALID_ARGUMENT"


@pytest.mark.parametrize("option", ["--snapshot", "--registry", "--project", "--query", "--limit", "--layer", "--type"])
def test_cli_rejects_duplicate_selectors_and_filters(option):
    values = arguments()
    if option not in values:
        values += [option, "1"]
    with pytest.raises(api.CoreError) as error:
        cli._parser().parse_args(values + [option, "1"])
    assert error.value.code == "INVALID_ARGUMENT"


@pytest.mark.parametrize("option", ["--apply", "--output", "--source-root", "--profile-id", "--operation-id", "--snap"])
def test_navigation_cli_has_no_mutation_or_caller_file_input(option):
    with pytest.raises(api.CoreError):
        cli._parser().parse_args(arguments() + [option, "PRIVATE_INPUT"])


@pytest.fixture
def command(scope, monkeypatch, capsys):
    monkeypatch.setattr(capabilities, "_platform", "win32")
    monkeypatch.setattr(cli, "current_local_principal", lambda: scope.ctx.principal)
    monkeypatch.setattr(cli, "_runtime", lambda args: scope.runtime)
    requested = []
    def resolve(runtime, principal, project_id, snapshot_id=None, **kwargs):
        requested.append((principal, project_id, snapshot_id))
        assert principal == scope.ctx.principal and project_id == scope.ctx.project_id
        assert snapshot_id == scope.ctx.snapshot.snapshot_id
        return scope.ctx
    monkeypatch.setattr(LocalRuntime, "resolve", resolve)
    def call(operation="metadata-search", extra=()):
        args = [operation, "--registry", str(scope.runtime.registry_path), "--project", scope.ctx.project_id,
                "--snapshot", scope.ctx.snapshot.snapshot_id, *extra]
        code = cli.main(args)
        output = capsys.readouterr()
        assert not output.err
        return code, json.loads(output.out)
    return call, requested


def test_cli_selects_pinned_snapshot_with_read_permission_and_versioned_envelope(scope, command, monkeypatch):
    monkeypatch.setattr(metadata, "search_metadata", lambda *a, **k: envelope(scope))
    call, requested = command
    code, output = call(extra=["--query=Товар", "--limit=17"])
    assert code == 0 and output["result"] == {**envelope(scope), "schema": 1}
    assert requested == [(scope.ctx.principal, scope.ctx.project_id, "a" * 64)]


def test_cli_revocation_after_serialization_redacts_materialized_metadata(scope, command, monkeypatch):
    monkeypatch.setattr(metadata, "search_metadata", lambda *a, **k: {**envelope(scope), "objects": ["PRIVATE_METADATA"]})
    original = json.dumps
    fired = False
    def serialize(value, *args, **kwargs):
        nonlocal fired
        if not fired and isinstance(value, dict) and value.get("result", {}).get("schema") == 1:
            fired = True
            scope.revoke()
        return original(value, *args, **kwargs)
    monkeypatch.setattr(cli.json, "dumps", serialize)
    code, output = command[0]()
    assert fired and code == 2 and output["error"]["code"] == "PROJECT_FORBIDDEN"
    assert "PRIVATE_METADATA" not in original(output) and "result" not in output


def test_cli_enforces_utf8_output_limit_without_partial_result(scope, command, monkeypatch):
    monkeypatch.setattr(metadata, "search_metadata", lambda *a, **k: {**envelope(scope), "objects": ["я" * nav.OUTPUT_LIMIT]})
    code, output = command[0]()
    assert code == 2 and output["error"]["code"] == "OUTPUT_LIMIT_EXCEEDED"
    assert "result" not in output


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_new_navigation_remains_unavailable_before_identity_and_registry_io(monkeypatch, capsys, platform):
    monkeypatch.setattr(capabilities, "_platform", platform)
    monkeypatch.setattr(cli, "current_local_principal", lambda *a, **k: pytest.fail("Unsupported operation read identity"))
    assert cli.main(arguments()) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "CAPABILITY_UNAVAILABLE"
