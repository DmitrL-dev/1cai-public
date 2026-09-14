"""Read-only transport of producer JSON objects, including revocation boundaries."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

import rentgen_core as api
from rentgen_core import cli, edt_identity_three_way as planner
from rentgen_core.local import LocalRuntime
from project_access_test_support import force_legacy_membership
from test_edt_identity_three_way import LIMITS, PROJECT, inventory
import test_project_core_publication as publication

project, scanner = publication.project, publication.scanner


def arguments():
    return [
        "edt-inventory-plan",
        "--registry",
        "registry.db",
        "--project",
        PROJECT,
        "--base-json",
        "base.json",
        "--current-json",
        "current.json",
        "--upstream-json",
        "upstream.json",
    ]


def test_parser_defaults_and_help(capsys):
    args = cli._parser().parse_args(arguments())
    assert {name: getattr(args, name) for name in LIMITS} == LIMITS
    assert args.base_json == Path("base.json")
    assert not hasattr(args, "snapshot")
    with pytest.raises(SystemExit) as error:
        cli._parser().parse_args(["edt-inventory-plan", "--help"])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    assert all("--" + name.replace("_", "-") in help_text for name in LIMITS)


@pytest.mark.parametrize(
    "name", ["registry", "project", "base-json", "current-json", "upstream-json"]
)
def test_parser_requires_all_inputs(name):
    args = arguments()
    index = args.index("--" + name)
    del args[index : index + 2]
    with pytest.raises(api.CoreError) as error:
        cli._parser().parse_args(args)
    assert error.value.code == "INVALID_ARGUMENT"


@pytest.mark.parametrize(
    "name",
    ["registry", "project", "base_json", "current_json", "upstream_json", *LIMITS],
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
        "--apply",
        "--output",
        "--workspace",
        "--operation-id",
        "--snapshot",
        "--source-root",
        "--profile-id",
        "--materialize",
        "--base",
    ],
)
def test_no_write_native_snapshot_or_abbreviated_options(option):
    with pytest.raises(api.CoreError) as error:
        cli._parser().parse_args(arguments() + [option, "PRIVATE_PAYLOAD"])
    assert error.value.code == "INVALID_ARGUMENT"


@pytest.fixture
def local(tmp_path, monkeypatch, capsys):
    if os.name != "nt":
        pytest.skip("Windows registry contract")
    principal = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    registered = registry.register(
        principal,
        source_root=source,
        state_root=tmp_path / "state",
        display_name="Identity plan",
    )
    ctx = LocalRuntime(registry.path).state_context(principal, registered.project_id)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: principal)
    paths = [tmp_path / (label + ".json") for label in ("base", "current", "upstream")]
    values = [
        json.loads(json.dumps(inventory(version)).replace(PROJECT, ctx.project_id))
        for version in "abc"
    ]

    def write(items):
        for path, value in zip(paths, items):
            path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    write(values)

    def permissions(values):
        with ctx.state.transaction(principal, write=True) as tx:
            force_legacy_membership(tx, principal, values)

    def call(*extra):
        args = arguments()
        args[2], args[4] = str(registry.path), ctx.project_id
        args[6], args[8], args[10] = map(str, paths)
        code = cli.main(args + list(extra))
        output = capsys.readouterr()
        assert output.err == ""
        return code, json.loads(output.out)

    return SimpleNamespace(
        ctx=ctx,
        paths=paths,
        values=values,
        call=call,
        write=write,
        permissions=permissions,
    )


def assert_error(result, code):
    status, value = result
    assert status == 2
    assert value["error"]["code"] == code
    assert "result" not in value
    assert "PRIVATE_PAYLOAD" not in json.dumps(value)


def test_calls_pure_planner_once_and_never_resolves_or_decodes_metadata_tree(
    local, monkeypatch
):
    local.permissions({"project:read"})
    original = planner.plan_edt_identity_three_way
    expected = original(*local.values)
    calls = []

    def plan(*values, **kwargs):
        calls.append((values, kwargs))
        return original(*values, **kwargs)

    monkeypatch.setattr(planner, "plan_edt_identity_three_way", plan)
    monkeypatch.setattr(
        LocalRuntime, "resolve", lambda *a, **kw: pytest.fail("Snapshot resolved")
    )
    monkeypatch.setattr(
        cli, "_metadata_tree", lambda *a, **kw: pytest.fail("Metadata tree decoded")
    )
    code, output = local.call()
    assert code == 0
    assert output["result"] == expected
    assert len(calls) == 1
    assert calls[0][0] == tuple(local.values)
    assert asdict(calls[0][1]["limits"]) == LIMITS


@pytest.mark.parametrize("name", LIMITS)
@pytest.mark.parametrize("value", [0, -1, "true", "above"])
def test_invalid_limits_fail_before_first_read(local, monkeypatch, name, value):
    monkeypatch.setattr(
        cli, "_proposal_input", lambda *a, **kw: pytest.fail("Input read")
    )
    argument = LIMITS[name] + 1 if value == "above" else value
    assert_error(
        local.call("--" + name.replace("_", "-"), str(argument)),
        "INVALID_ARGUMENT" if value == "true" else "INVALID_QUERY_OPTIONS",
    )


@pytest.mark.parametrize(
    "permissions",
    [set(), {"source:edit"}, {"analysis:run"}, {"source:edit", "analysis:run"}],
)
def test_read_permission_is_required_before_input_access(
    local, monkeypatch, permissions
):
    local.permissions(permissions)
    monkeypatch.setattr(
        cli, "_proposal_input", lambda *a, **kw: pytest.fail("Denied input read")
    )
    assert_error(local.call(), "PROJECT_FORBIDDEN")


@pytest.mark.parametrize(
    "raw",
    [
        b"\xffPRIVATE_PAYLOAD",
        b'{"PRIVATE_PAYLOAD":1,"PRIVATE_PAYLOAD":2}',
        b'{"PRIVATE_PAYLOAD":NaN}',
        b'{"PRIVATE_PAYLOAD":Infinity}',
        b"{} PRIVATE_PAYLOAD",
        b"[]",
        b"null",
        b'{"PRIVATE_PAYLOAD":',
        b'{"schema":1,"encoding":"base64","files":{}}',
        b'{"result":{}}',
    ],
)
def test_invalid_json_and_wrong_envelopes_do_not_expose_payload(local, raw):
    local.paths[0].write_bytes(raw)
    status, output = local.call()
    assert status == 2
    assert output["error"]["details"] == {}
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)
    assert "result" not in output


def test_input_cap_precedes_json_decode(local, monkeypatch):
    local.paths[0].write_bytes(b" " * (8 * 1024**2 + 1))
    monkeypatch.setattr(
        cli,
        "_edt_identity_inventory_json",
        lambda *a: pytest.fail("Oversized input decoded"),
    )
    assert_error(local.call(), "INVALID_ARGUMENT")


def test_lower_input_byte_limit_is_enforced(local):
    assert_error(local.call("--max-input-bytes", "1"), "INVALID_ARGUMENT")


def test_foreign_project_inventory_stops_before_next_input(local, monkeypatch):
    local.paths[0].write_text(json.dumps(inventory()), encoding="utf-8")
    reads = []
    original = cli._proposal_input

    def read(*args, **kwargs):
        reads.append(args[1])
        return original(*args, **kwargs)

    monkeypatch.setattr(cli, "_proposal_input", read)
    assert_error(local.call(), "EDT_IDENTITY_PLAN_INVALID")
    assert reads == local.paths[:1]


@pytest.mark.parametrize("after", [1, 2, 3])
def test_revocation_after_each_read_stops_before_decode_and_next_read(
    local, monkeypatch, after
):
    original, decode = cli._proposal_input, cli._edt_identity_inventory_json
    reads, decoded = [], []

    def read(*args, **kwargs):
        raw = original(*args, **kwargs)
        reads.append(args[1])
        if len(reads) == after:
            local.permissions(set())
        return raw

    monkeypatch.setattr(cli, "_proposal_input", read)

    def inventory_json(raw):
        decoded.append(raw)
        return decode(raw)

    monkeypatch.setattr(cli, "_edt_identity_inventory_json", inventory_json)
    monkeypatch.setattr(
        planner,
        "plan_edt_identity_three_way",
        lambda *a, **kw: pytest.fail("Planner ran after read revocation"),
    )
    assert_error(local.call(), "PROJECT_FORBIDDEN")
    assert len(reads) == after
    assert len(decoded) == after - 1


@pytest.mark.parametrize("after", [1, 2, 3])
def test_revocation_after_each_decode_precedes_following_operation(
    local, monkeypatch, after
):
    original = cli._edt_identity_inventory_json
    decoded = []

    def decode(raw):
        value = original(raw)
        decoded.append(value)
        if len(decoded) == after:
            local.permissions(set())
        return value

    monkeypatch.setattr(cli, "_edt_identity_inventory_json", decode)
    monkeypatch.setattr(
        planner,
        "plan_edt_identity_three_way",
        lambda *a, **kw: pytest.fail("Planner ran after decode revocation"),
    )
    assert_error(local.call(), "PROJECT_FORBIDDEN")
    assert len(decoded) == after


def test_revocation_during_normalization_precedes_result_serialization(
    local, monkeypatch
):
    original, dumps = planner._normalize, cli.json.dumps

    def normalize(*args):
        value = original(*args)
        local.permissions(set())
        return value

    def serialize(value, **kwargs):
        assert (
            not isinstance(value, dict) or "result" not in value
        ), "Revoked result serialized"
        return dumps(value, **kwargs)

    monkeypatch.setattr(planner, "_normalize", normalize)
    monkeypatch.setattr(cli.json, "dumps", serialize)
    assert_error(local.call(), "PROJECT_FORBIDDEN")


@pytest.mark.parametrize("revoke", [False, True])
def test_planner_errors_are_payload_free_and_reauthorized(local, monkeypatch, revoke):
    def plan(*args, **kwargs):
        if revoke:
            local.permissions(set())
        raise api.CoreError(
            "EDT_IDENTITY_PLAN_INVALID",
            "PRIVATE_PAYLOAD",
            details={"source": "PRIVATE_PAYLOAD"},
        )

    monkeypatch.setattr(planner, "plan_edt_identity_three_way", plan)
    assert_error(
        local.call(), "PROJECT_FORBIDDEN" if revoke else "EDT_IDENTITY_PLAN_INVALID"
    )


@pytest.mark.parametrize("boundary", ["result", "error"])
def test_final_serialization_boundary_rechecks_rights(local, monkeypatch, boundary):
    dumps = cli.json.dumps
    serialized = []
    if boundary == "error":
        local.paths[0].write_bytes(b"invalid PRIVATE_PAYLOAD")

    def serialize(value, **kwargs):
        raw = dumps(value, **kwargs)
        if isinstance(value, dict) and boundary in value and not serialized:
            serialized.append(True)
            local.permissions(set())
        return raw

    monkeypatch.setattr(cli.json, "dumps", serialize)
    assert_error(local.call(), "PROJECT_FORBIDDEN")
    assert serialized == [True]


def test_output_cap_has_no_partial_result(local, monkeypatch):
    monkeypatch.setattr(
        planner,
        "plan_edt_identity_three_way",
        lambda *a, **kw: {"data": "PRIVATE_PAYLOAD" + "x" * (8 * 1024**2)},
    )
    assert_error(local.call(), "OUTPUT_LIMIT_EXCEEDED")


def test_revocation_after_state_context_precedes_actual_file_open(local, monkeypatch):
    original, open_file = LocalRuntime.state_context, Path.open

    def state_context(*args, **kwargs):
        ctx = original(*args, **kwargs)
        local.permissions(set())
        return ctx

    def open_path(path, *args, **kwargs):
        assert path not in local.paths, "Revoked input opened"
        return open_file(path, *args, **kwargs)

    monkeypatch.setattr(LocalRuntime, "state_context", state_context)
    monkeypatch.setattr(Path, "open", open_path)
    assert_error(local.call(), "PROJECT_FORBIDDEN")


def test_mapping_drift_during_planner_capture_is_redacted(local, monkeypatch):
    original = cli._edt_identity_inventory_json

    class Drift(dict):
        def items(self):
            raise RuntimeError("PRIVATE_PAYLOAD")

    def decode(raw):
        value = original(raw)
        value["objects"][0] = Drift(value["objects"][0])
        return value

    monkeypatch.setattr(cli, "_edt_identity_inventory_json", decode)
    assert_error(local.call(), "EDT_IDENTITY_PLAN_INVALID")


@pytest.mark.skipif(os.name != "nt", reason="Windows published snapshot contract")
def test_actual_published_inventory_result_is_accepted_unchanged(
    project, tmp_path, monkeypatch, capsys
):
    ctx, resolver, _, _ = project
    fixture = (
        Path(__file__).resolve().parents[2] / "packaging/fixtures/edt-inventory-v1/base"
    )
    shutil.copytree(fixture, ctx.source_root, dirs_exist_ok=True)
    api.configure_source_layers(
        ctx, (api.SourceLayerSpec("base", 0, "base", ".", "edt"),), expected_revision=1
    )
    publication.publish(project)
    selected = resolver.resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    value = api.edt_metadata_inventory(selected)
    assert "schema" not in value
    expected = planner.plan_edt_identity_three_way(value, value, value)
    assert len(expected["objects"]) == 17
    paths = [tmp_path / (label + ".json") for label in ("base", "current", "upstream")]
    for path in paths:
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    args = arguments()
    args[2], args[4] = str(resolver.registry.path), ctx.project_id
    args[6], args[8], args[10] = map(str, paths)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: ctx.principal)
    monkeypatch.setattr(
        LocalRuntime, "resolve", lambda *a, **kw: pytest.fail("Plan resolved snapshot")
    )
    capsys.readouterr()
    assert cli.main(args) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out)["result"] == expected
