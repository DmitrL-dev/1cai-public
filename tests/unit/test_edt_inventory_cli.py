"""Snapshot-bound EDT inventory transport; synthetic data, no native acceptance."""

from dataclasses import asdict
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

import rentgen_core as api
from rentgen_core import cli, edt_inventory
from rentgen_core.local import LocalRuntime
from project_access_test_support import force_legacy_membership
import test_project_core_publication as fixtures

project, scanner, pytestmark = fixtures.project, fixtures.scanner, fixtures.pytestmark
LIMITS = {
    "max_xml_bytes": 4 * 1024**2,
    "max_nodes": 50_000,
    "max_depth": 64,
    "max_inventory": 20_000,
    "max_collection": 200,
    "max_total_bytes": 64 * 1024**2,
    "max_asset_bytes": 16 * 1024**2,
    "max_mdo_files": 2048,
    "max_identities": 20_000,
}
FIXTURE = Path(__file__).resolve().parents[2] / "packaging/fixtures/edt-inventory-v1"


def arguments():
    return [
        "edt-inventory",
        "--registry",
        "registry.db",
        "--project",
        "project",
        "--snapshot",
        "a" * 64,
    ]


def test_parser_defaults_and_help(capsys):
    parsed = cli._parser().parse_args(arguments())
    assert parsed.snapshot == "a" * 64
    assert parsed.layer_id is None
    assert (
        {name: getattr(parsed, name) for name in LIMITS}
        == asdict(edt_inventory.EDTInventoryLimits())
        == LIMITS
    )
    assert not hasattr(parsed, "operation_id")
    with pytest.raises(SystemExit) as error:
        cli._parser().parse_args(["edt-inventory", "--help"])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert "--snapshot SNAPSHOT" in help_text
    assert all("--" + name.replace("_", "-") in help_text for name in LIMITS)


@pytest.mark.parametrize("name", ["registry", "project", "snapshot"])
def test_parser_requires_explicit_binding(name):
    args = arguments()
    index = args.index("--" + name)
    del args[index : index + 2]
    with pytest.raises(api.CoreError, match="required"):
        cli._parser().parse_args(args)


@pytest.mark.parametrize(
    "name", ["registry", "project", "snapshot", "layer_id", *LIMITS]
)
def test_parser_rejects_repeated_options(name):
    option = "--" + name.replace("_", "-")
    args = arguments()
    if option not in args:
        args += [option, "1"]
    with pytest.raises(api.CoreError) as error:
        cli._parser().parse_args(args + [option, "1"])
    assert error.value.code == "INVALID_ARGUMENT"


@pytest.mark.parametrize(
    "option",
    [
        "--output",
        "--apply",
        "--operation-id",
        "--workspace",
        "--profile-id",
        "--base-json",
        "--current-json",
        "--upstream-json",
        "--source-root",
        "--snap",
    ],
)
def test_parser_has_no_write_native_or_caller_file_options(option):
    with pytest.raises(api.CoreError) as error:
        cli._parser().parse_args(arguments() + [option, "PRIVATE_PAYLOAD"])
    assert error.value.code == "INVALID_ARGUMENT"


@pytest.fixture
def local(project, monkeypatch, capsys):
    ctx, resolver, _, _ = project
    shutil.copytree(FIXTURE / "base", ctx.source_root, dirs_exist_ok=True)
    api.configure_source_layers(
        ctx, (api.SourceLayerSpec("base", 0, "base", ".", "edt"),), expected_revision=1
    )
    fixtures.publish(project)
    selected = resolver.resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    monkeypatch.setattr(cli, "current_windows_principal", lambda: ctx.principal)
    args = [
        "edt-inventory",
        "--registry",
        str(ctx.source_root.parent / "registry.sqlite3"),
        "--project",
        ctx.project_id,
        "--snapshot",
        selected.snapshot.snapshot_id,
    ]

    def call(*extra, snapshot=None):
        argv = list(args)
        if snapshot is not None:
            argv[-1] = snapshot
        capsys.readouterr()  # Publication diagnostics belong to fixture setup.
        code = cli.main(argv + list(extra))
        output = capsys.readouterr()
        assert not output.err
        return code, json.loads(output.out)

    def permissions(values):
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, values)

    return SimpleNamespace(ctx=selected, call=call, permissions=permissions, args=args)


def assert_error(result, code):
    status, output = result
    assert status == 2
    assert output["error"]["code"] == code
    assert "result" not in output
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)


def test_execution_returns_unchanged_inventory_with_read_permission_only(local):
    expected = edt_inventory.edt_metadata_inventory(local.ctx)
    local.permissions({"project:read"})
    code, output = local.call()
    assert code == 0
    assert output["result"] == expected
    assert expected["snapshot"] == asdict(local.ctx.snapshot)
    assert len(expected["objects"]) == 17


def test_execution_calls_inventory_once_with_selected_context_and_typed_limits(
    local, monkeypatch
):
    calls = []

    def inventory(ctx, **kwargs):
        calls.append((ctx, kwargs))
        return {"coverage": "partial"}

    monkeypatch.setattr(edt_inventory, "edt_metadata_inventory", inventory)
    code, output = local.call("--layer-id", "base", "--max-identities", "17")
    assert code == 0
    assert output["result"] == {"coverage": "partial"}
    assert len(calls) == 1
    assert calls[0][0].snapshot == local.ctx.snapshot
    assert calls[0][1] == {
        "layer_id": "base",
        "limits": edt_inventory.EDTInventoryLimits(max_identities=17),
    }


@pytest.mark.parametrize("name", LIMITS)
@pytest.mark.parametrize("value", [0, -1, "true", "above"])
def test_invalid_limits_precede_resolution(local, monkeypatch, name, value):
    monkeypatch.setattr(
        LocalRuntime, "resolve", lambda *a, **kw: pytest.fail("Resolved invalid limits")
    )
    actual = LIMITS[name] + 1 if value == "above" else value
    assert_error(
        local.call("--" + name.replace("_", "-"), str(actual)),
        "INVALID_ARGUMENT" if value == "true" else "INVALID_QUERY_OPTIONS",
    )


@pytest.mark.parametrize(
    "granted",
    [set(), {"analysis:run"}, {"source:edit"}, {"analysis:run", "source:edit"}],
)
def test_denial_precedes_resolution(local, monkeypatch, granted):
    local.permissions(granted)
    monkeypatch.setattr(
        LocalRuntime, "resolve", lambda *a, **kw: pytest.fail("Resolved denied request")
    )
    assert_error(local.call(), "PROJECT_FORBIDDEN")


@pytest.mark.parametrize("failure", [False, True])
def test_resolution_failure_is_redacted_and_reauthorized(local, monkeypatch, failure):
    def resolve(*a, **kw):
        if failure:
            local.permissions(set())
        raise api.CoreError(
            "SNAPSHOT_NOT_FOUND", "PRIVATE_PAYLOAD", details={"path": "PRIVATE_PAYLOAD"}
        )

    monkeypatch.setattr(LocalRuntime, "resolve", resolve)
    assert_error(local.call(), "PROJECT_FORBIDDEN" if failure else "SNAPSHOT_NOT_FOUND")


def test_missing_snapshot_never_falls_back_to_head(local):
    assert_error(local.call(snapshot="f" * 64), "SNAPSHOT_NOT_FOUND")


def test_missing_layer_is_payload_free(local):
    status, output = local.call("--layer-id", "PRIVATE_PAYLOAD")
    assert status == 2
    assert output["error"]["details"] == {}
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)
    assert "result" not in output


def test_live_changes_and_new_head_do_not_change_selected_inventory(local, project):
    before = local.call()
    source = local.ctx.source_root / "Catalogs/Products/Products.mdo"
    source.write_bytes(source.read_bytes().replace(b"Products", b"PRIVATE_PAYLOAD"))
    fixtures.publish(project)
    after = local.call()
    assert before[0] == after[0] == 0
    assert before[1]["result"] == after[1]["result"]


@pytest.mark.parametrize(
    "case,code",
    [
        ("malformed.mdo", "XML_INVALID"),
        ("foreign-namespace.mdo", "EDT_INVENTORY_UNSUPPORTED"),
        ("duplicate", "EDT_IDENTITY_DUPLICATE"),
    ],
)
def test_retained_invalid_documents_fail_without_payload(local, project, case, code):
    source = local.ctx.source_root / "Catalogs/Products/Products.mdo"
    if case == "duplicate":
        raw = source.read_bytes()
        raw = raw.replace(
            b"10000000-0000-4000-8000-000000000020",
            b"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
    else:
        raw = (FIXTURE / "negative" / case).read_bytes()
    source.write_bytes(raw)
    result = fixtures.publish(project)
    assert_error(local.call(snapshot=result.snapshot.snapshot_id), code)


@pytest.mark.parametrize("revoke", [False, True])
def test_engine_errors_are_redacted_and_reauthorized(local, monkeypatch, revoke):
    def inventory(*a, **kw):
        if revoke:
            local.permissions(set())
        raise api.CoreError(
            "EDT_IDENTITY_INVALID",
            "PRIVATE_PAYLOAD",
            details={"source": "PRIVATE_PAYLOAD"},
        )

    monkeypatch.setattr(edt_inventory, "edt_metadata_inventory", inventory)
    assert_error(
        local.call(), "PROJECT_FORBIDDEN" if revoke else "EDT_IDENTITY_INVALID"
    )


def test_output_cap_returns_no_partial_inventory(local, monkeypatch):
    monkeypatch.setattr(
        edt_inventory,
        "edt_metadata_inventory",
        lambda *a, **kw: {"source": "PRIVATE_PAYLOAD" + "x" * (8 * 1024**2)},
    )
    assert_error(local.call(), "OUTPUT_LIMIT_EXCEEDED")


def test_revocation_after_serialization_suppresses_result(local, monkeypatch):
    original = cli.json.dumps

    def dumps(value, **kwargs):
        encoded = original(value, **kwargs)
        if isinstance(value, dict) and "result" in value:
            local.permissions(set())
        return encoded

    monkeypatch.setattr(cli.json, "dumps", dumps)
    assert_error(local.call(), "PROJECT_FORBIDDEN")


@pytest.mark.parametrize("name", LIMITS)
def test_boolean_limits_fail_before_resolution(local, monkeypatch, name):
    args = cli._parser().parse_args(local.args)
    setattr(args, name, True)
    monkeypatch.setattr(
        LocalRuntime, "resolve", lambda *a, **kw: pytest.fail("Resolved boolean limit")
    )
    with pytest.raises(api.CoreError) as error:
        cli._execute(args)
    assert error.value.code == "INVALID_QUERY_OPTIONS"


def test_revocation_after_state_auth_precedes_resolution(local, monkeypatch):
    original = LocalRuntime.state_context

    def state_context(*args, **kwargs):
        ctx = original(*args, **kwargs)
        local.permissions(set())
        return ctx

    monkeypatch.setattr(LocalRuntime, "state_context", state_context)
    monkeypatch.setattr(
        LocalRuntime,
        "resolve",
        lambda *a, **kw: pytest.fail("Resolved revoked request"),
    )
    assert_error(local.call(), "PROJECT_FORBIDDEN")


def test_revocation_during_shared_read_session_precedes_next_source_read(
    local, monkeypatch
):
    from rentgen_core.sources import SnapshotReadSession

    original = SnapshotReadSession.read_source
    reads = []

    def read(session, ref):
        raw = original(session, ref)
        reads.append(ref)
        local.permissions(set())
        return raw

    monkeypatch.setattr(SnapshotReadSession, "read_source", read)
    assert_error(local.call(), "PROJECT_FORBIDDEN")
    assert len(reads) == 1


def test_unpublished_context_is_not_inventory_input(local, monkeypatch):
    state = LocalRuntime(Path(local.args[2])).state_context(
        local.ctx.principal, local.ctx.project_id, permissions={"project:read"}
    )
    monkeypatch.setattr(LocalRuntime, "resolve", lambda *a, **kw: state)
    monkeypatch.setattr(
        edt_inventory,
        "edt_metadata_inventory",
        lambda *a, **kw: pytest.fail("Read unpublished context"),
    )
    assert_error(local.call(), "SNAPSHOT_REQUIRED")


def test_foreign_published_snapshot_is_not_resolved(local, project):
    from rentgen_core.registry import ProjectRegistry

    source = local.ctx.source_root.parent / "other-source"
    source.mkdir()
    shutil.copytree(FIXTURE / "base", source, dirs_exist_ok=True)
    registry = ProjectRegistry(Path(local.args[2]))
    other = registry.register(
        local.ctx.principal,
        source_root=source,
        state_root=source.parent / "other-state",
        display_name="Other",
    )
    resolver = project[1]
    ctx = resolver.resolve_context(local.ctx.principal, api.Explicit(other.project_id))
    api.configure_source_layers(
        ctx, (api.SourceLayerSpec("base", 0, "base", ".", "edt"),), expected_revision=1
    )
    result = fixtures.publish((ctx, resolver, None, project[3]))
    assert_error(local.call(snapshot=result.snapshot.snapshot_id), "SNAPSHOT_NOT_FOUND")


def test_all_lowered_limits_reach_library(local, monkeypatch):
    calls = []
    monkeypatch.setattr(
        edt_inventory, "edt_metadata_inventory", lambda *a, **kw: calls.append(kw) or {}
    )
    options = [
        value for name in LIMITS for value in ("--" + name.replace("_", "-"), "1")
    ]
    assert local.call(*options)[0] == 0
    assert asdict(calls[0]["limits"]) == dict.fromkeys(LIMITS, 1)


def test_scope_is_selected_before_inventory_read(local, monkeypatch):
    scope = cli._ProposalScope()

    def inventory(ctx, **kwargs):
        assert scope.context is ctx
        assert scope.permissions == frozenset({"project:read"})
        assert ctx.snapshot == local.ctx.snapshot
        return {}

    monkeypatch.setattr(edt_inventory, "edt_metadata_inventory", inventory)
    result = cli._execute(cli._parser().parse_args(local.args), proposal_scope=scope)
    assert result.context is scope.context
    assert result.output_limit == 8 * 1024**2


@pytest.mark.parametrize("option", ["--max-mdo-files", "--max-identities"])
def test_lowered_budget_fails_without_partial_inventory(local, option):
    assert_error(local.call(option, "1"), "METADATA_LIMIT_EXCEEDED")


def test_revocation_after_error_serialization_suppresses_stale_error(
    local, monkeypatch
):
    original = cli.json.dumps
    serialized = []

    def dumps(value, **kwargs):
        encoded = original(value, **kwargs)
        if (
            isinstance(value, dict)
            and value.get("error", {}).get("code") == "SNAPSHOT_NOT_FOUND"
        ):
            serialized.append(True)
            local.permissions(set())
        return encoded

    monkeypatch.setattr(cli.json, "dumps", dumps)
    assert_error(local.call(snapshot="f" * 64), "PROJECT_FORBIDDEN")
    assert serialized == [True]
