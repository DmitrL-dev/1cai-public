"""The EDT attribute CLI transports bounded evidence behind project rights."""

import base64
import json
import os
from pathlib import Path

import pytest

import rentgen_core as api
from rentgen_core import CoreError, cli
from rentgen_core.local import LocalRuntime
from project_access_test_support import force_legacy_membership


PERMISSIONS = {"project:read", "source:edit", "analysis:run"}
CATALOG = "Catalogs/Products/Products.mdo"
FIXTURE = (
    Path(__file__).resolve().parents[2] / "packaging/fixtures/edt-inventory-v1/base"
)


def arguments(*extra):
    return [
        "edt-attribute-plan",
        "--registry",
        "registry.sqlite3",
        "--project",
        "p",
        "--base-json",
        "base.json",
        "--current-json",
        "current.json",
        "--upstream-json",
        "upstream.json",
        *extra,
    ]


def test_parser_requires_explicit_trees_and_uses_planner_ceilings():
    parsed = cli._parser().parse_args(arguments())
    assert parsed.command == "edt-attribute-plan"
    for name in ("base", "current", "upstream"):
        assert getattr(parsed, name + "_json") == Path(name + ".json")
    assert (
        parsed.max_files,
        parsed.max_file_bytes,
        parsed.max_total_bytes,
        parsed.max_children,
    ) == (
        256,
        1024 * 1024,
        16 * 1024 * 1024,
        20_000,
    )
    assert not hasattr(parsed, "snapshot")
    assert not hasattr(parsed, "operation_id")


@pytest.mark.parametrize("index", [1, 3, 5, 7, 9])
def test_parser_missing_required_option_returns_json_error(index, capsys):
    argv = arguments()
    del argv[index : index + 2]
    assert cli.main(argv) == 2
    output = capsys.readouterr()
    assert output.err == ""
    value = json.loads(output.out)
    assert value["error"]["code"] == "INVALID_ARGUMENT"
    assert "required" in value["error"]["message"]
    assert "result" not in value


@pytest.mark.parametrize(
    "option,value",
    [
        ("--registry", "registry.sqlite3"),
        ("--project", "p"),
        ("--base-json", "base.json"),
        ("--current-json", "current.json"),
        ("--upstream-json", "upstream.json"),
        ("--max-files", "1"),
        ("--max-file-bytes", "1"),
        ("--max-total-bytes", "1"),
        ("--max-children", "1"),
    ],
)
def test_parser_rejects_repeated_options(option, value):
    argv = arguments()
    if option.startswith("--max-"):
        argv.extend((option, value))
    argv.extend((option, value))
    with pytest.raises(CoreError) as caught:
        cli._parser().parse_args(argv)
    assert caught.value.code == "INVALID_ARGUMENT"
    assert "Repeated option" in caught.value.message


@pytest.mark.parametrize(
    "option",
    [
        "--snapshot",
        "--operation-id",
        "--output",
        "--workspace",
        "--apply",
        "--profile-id",
        "--materialize",
        "--base",
    ],
)
def test_parser_rejects_snapshot_native_write_and_abbreviated_options(option):
    cli._parser().parse_args(arguments())
    with pytest.raises(CoreError) as caught:
        cli._parser().parse_args(arguments(option, "forbidden"))
    assert caught.value.code == "INVALID_ARGUMENT"


def test_parser_help_lists_command_and_arguments(capsys):
    with pytest.raises(SystemExit) as caught:
        cli._parser().parse_args(["--help"])
    assert caught.value.code == 0
    assert "edt-attribute-plan" in capsys.readouterr().out
    with pytest.raises(SystemExit) as caught:
        cli._parser().parse_args(["edt-attribute-plan", "--help"])
    assert caught.value.code == 0
    help_text = capsys.readouterr().out
    assert "--max-children" in help_text
    assert all(
        "--" + label + "-json" in help_text for label in ("base", "current", "upstream")
    )
    assert "--snapshot" not in help_text


@pytest.fixture
def local(tmp_path, monkeypatch, capsys):
    if os.name != "nt":
        pytest.skip("Windows registry contract")
    principal = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(
        principal,
        source_root=source,
        state_root=tmp_path / "state",
        display_name="EDT CLI",
    )
    ctx = LocalRuntime(registry.path).state_context(principal, project.project_id)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: principal)
    paths = [tmp_path / (label + ".json") for label in ("base", "current", "upstream")]

    def write(*trees):
        for path, tree in zip(paths, trees):
            path.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "encoding": "base64",
                        "files": {
                            name: base64.b64encode(raw).decode("ascii")
                            for name, raw in tree.items()
                        },
                    }
                ),
                encoding="utf-8",
            )

    def call(*extra):
        argv = arguments(*extra)
        argv[2], argv[4] = str(registry.path), project.project_id
        argv[6], argv[8], argv[10] = map(str, paths)
        code = cli.main(argv)
        output = capsys.readouterr()
        assert output.err == ""
        return code, json.loads(output.out)

    tree = {CATALOG: (FIXTURE / CATALOG).read_bytes()}
    write(tree, tree, tree)
    return ctx, paths, tree, write, call


def test_execution_matches_library_once_without_source_or_native_operations(
    local, monkeypatch
):
    ctx, _, tree, write, call = local
    base = {
        CATALOG: tree[CATALOG].replace(
            b"</attributes>", b"<comment>old</comment></attributes>"
        )
    }
    current = {CATALOG: base[CATALOG].replace(b"Article", b"SKU")}
    upstream = {CATALOG: base[CATALOG].replace(b">old<", b">PRIVATE_PAYLOAD<")}
    write(base, current, upstream)
    original = api.plan_edt_attribute_three_way
    expected = original(base, current, upstream, max_children=1)
    calls = []

    def record(*trees, **limits):
        calls.append((trees, limits))
        return original(*trees, **limits)

    def forbidden(*args, **kwargs):
        pytest.fail(
            "Evidence CLI must not resolve snapshots, materialize or start native processes"
        )

    monkeypatch.setattr(api, "plan_edt_attribute_three_way", record)
    monkeypatch.setattr(api, "materialize_metadata_three_way", forbidden)
    monkeypatch.setattr(LocalRuntime, "resolve", forbidden)
    monkeypatch.setattr("subprocess.Popen", forbidden)
    before = {
        path: path.read_bytes()
        for path in ctx.source_root.parent.rglob("*")
        if path.is_file()
    }
    code, output = call("--max-children", "1")
    assert code == 0, output
    assert output["result"] == expected
    assert calls == [
        (
            (base, current, upstream),
            {
                "max_files": 256,
                "max_file_bytes": 1024 * 1024,
                "max_total_bytes": 16 * 1024 * 1024,
                "max_children": 1,
            },
        )
    ]
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)
    assert "candidate" not in output["result"]
    assert {
        path: path.read_bytes()
        for path in ctx.source_root.parent.rglob("*")
        if path.is_file()
    } == before


@pytest.mark.parametrize("permission", sorted(PERMISSIONS))
def test_execution_checks_every_permission_before_any_payload_read(
    local, monkeypatch, permission
):
    ctx, _, _, _, call = local
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, PERMISSIONS - {permission})
    monkeypatch.setattr(
        cli,
        "_proposal_input",
        lambda *a, **kw: pytest.fail("Input read before rights check"),
    )
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "PROJECT_FORBIDDEN"


@pytest.mark.parametrize(
    "option,value",
    [
        ("--max-files", "0"),
        ("--max-files", "257"),
        ("--max-file-bytes", "0"),
        ("--max-file-bytes", "1048577"),
        ("--max-total-bytes", "0"),
        ("--max-total-bytes", "16777217"),
        ("--max-children", "0"),
        ("--max-children", "20001"),
    ],
)
def test_execution_checks_limits_before_input_read(local, monkeypatch, option, value):
    _, _, _, _, call = local
    monkeypatch.setattr(
        cli,
        "_proposal_input",
        lambda *a, **kw: pytest.fail("Input read before limit check"),
    )
    code, output = call(option, value)
    assert code == 2
    assert output["error"]["code"] == "THREE_WAY_LIMIT"


@pytest.mark.parametrize(
    "raw",
    [
        b'{"schema":1,"encoding":"base64","files":{"a":"","a":""}}',
        b'{"schema":true,"encoding":"base64","files":{}}',
        b'{"schema":1,"encoding":"utf-8","files":{"a":"PRIVATE_PAYLOAD"}}',
        b'{"schema":1,"encoding":"base64","files":{"a":null}}',
        b'{"schema":1,"encoding":"base64","files":{"a":"!!!PRIVATE_PAYLOAD"}}',
        b'{"schema":1,"encoding":"base64","files":{"a":"YR=="}}',
        b'{"schema":1,"encoding":"base64","files":{"A":"","a":""}}',
        b'{"schema":1,"encoding":"base64","files":{"../PRIVATE_PAYLOAD":""}}',
        b'{"schema":1,"encoding":"base64","files":{},"extra":"PRIVATE_PAYLOAD"}',
        b'{"PRIVATE_PAYLOAD":NaN}',
        b'{"PRIVATE_PAYLOAD":',
        b"\xffPRIVATE_PAYLOAD",
    ],
)
def test_execution_rejects_invalid_envelopes_without_payload(local, raw):
    _, paths, _, _, call = local
    paths[0].write_bytes(raw)
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "INVALID_ARGUMENT"
    assert output["error"]["message"] == "Metadata tree JSON is invalid"
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)
    assert "result" not in output


def test_execution_json_byte_cap_precedes_decode(local, monkeypatch):
    _, paths, _, _, call = local
    paths[0].write_bytes(b" " * (1024 * 1024 + 1))
    monkeypatch.setattr(
        cli, "_metadata_tree", lambda *a, **kw: pytest.fail("Oversized JSON decoded")
    )
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "INVALID_ARGUMENT"
    assert output["error"]["message"] == "Proposal input exceeds its byte limit"


def test_execution_encoded_byte_limit_precedes_base64_decode(local, monkeypatch):
    _, paths, _, _, call = local
    paths[0].write_text(
        json.dumps({"schema": 1, "encoding": "base64", "files": {CATALOG: "AAAAAAAA"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        base64, "b64decode", lambda *a, **kw: pytest.fail("Oversized base64 decoded")
    )
    code, output = call("--max-file-bytes", "1")
    assert code == 2
    assert output["error"]["code"] == "THREE_WAY_LIMIT"


@pytest.mark.parametrize(
    "option", ["--max-file-bytes", "--max-total-bytes", "--max-files"]
)
def test_execution_lower_tree_limits_apply(local, option):
    _, _, tree, write, call = local
    if option == "--max-files":
        tree = {**tree, "Catalogs/Other/Other.mdo": b""}
        write(tree, tree, tree)
    code, output = call(option, "1")
    assert code == 2
    assert output["error"]["code"] == "THREE_WAY_LIMIT"


def test_execution_lower_child_union_limit_reaches_planner(local):
    _, _, tree, write, call = local
    changed = {
        CATALOG: tree[CATALOG].replace(
            b"10000000-0000-4000-8000-000000000020",
            b"20000000-0000-4000-8000-000000000020",
        )
    }
    write(tree, changed, tree)
    code, output = call("--max-children", "1")
    assert code == 2
    assert output["error"]["code"] == "EDT_THREE_WAY_LIMIT"
    assert "result" not in output


@pytest.mark.parametrize("case", ["owner", "xml", "path"])
def test_execution_planner_errors_are_payload_free(local, case):
    _, _, tree, write, call = local
    if case == "owner":
        changed = {
            "Catalogs/PRIVATE_PAYLOAD/PRIVATE_PAYLOAD.mdo": tree[CATALOG]
            .replace(b"Products", b"PRIVATE_PAYLOAD")
            .replace(
                b"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                b"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            )
        }
    elif case == "xml":
        changed = {CATALOG: b"<PRIVATE_PAYLOAD>"}
    else:
        changed = {"PRIVATE_PAYLOAD.mdo": tree[CATALOG]}
    write(tree, changed, tree)
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "EDT_THREE_WAY_INVALID"
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)
    assert "result" not in output


def test_execution_engine_error_message_and_details_are_not_a_payload_surface(
    local, monkeypatch
):
    _, _, _, _, call = local

    def error(*args, **kwargs):
        raise CoreError(
            "EDT_THREE_WAY_INVALID",
            "PRIVATE_PAYLOAD",
            details={"source": "PRIVATE_PAYLOAD"},
        )

    monkeypatch.setattr(api, "plan_edt_attribute_three_way", error)
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "EDT_THREE_WAY_INVALID"
    assert output["error"]["details"] == {}
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)


@pytest.mark.parametrize("after", [1, 2])
def test_execution_revocation_prevents_the_next_input_read(local, monkeypatch, after):
    ctx, paths, _, _, call = local
    original = cli._metadata_tree
    reads = []

    def revoke(*args, **kwargs):
        value = original(*args, **kwargs)
        reads.append(value)
        if len(reads) == after:
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                force_legacy_membership(tx, ctx.principal, {"project:read"})
        return value

    paths[after].unlink()
    monkeypatch.setattr(cli, "_metadata_tree", revoke)
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "PROJECT_FORBIDDEN"
    assert len(reads) == after


@pytest.mark.parametrize("failure", [False, True])
def test_execution_rechecks_rights_after_planner_success_or_error(
    local, monkeypatch, failure
):
    ctx, _, _, _, call = local
    original = api.plan_edt_attribute_three_way

    def revoke(*args, **kwargs):
        value = original(*args, **kwargs)
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:read"})
        if failure:
            raise CoreError("EDT_THREE_WAY_INVALID", "PRIVATE_PAYLOAD")
        return value

    monkeypatch.setattr(api, "plan_edt_attribute_three_way", revoke)
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "PROJECT_FORBIDDEN"
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)
    assert "result" not in output


def test_execution_final_permission_check_follows_result_serialization(
    local, monkeypatch
):
    ctx, _, _, _, call = local
    original = json.dumps
    serialized = []

    def revoke(value, *args, **kwargs):
        encoded = original(value, *args, **kwargs)
        if isinstance(value, dict) and "child_objects" in value.get("result", {}):
            serialized.append(True)
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                force_legacy_membership(tx, ctx.principal, {"project:read"})
        return encoded

    monkeypatch.setattr(cli.json, "dumps", revoke)
    code, output = call()
    assert serialized == [True]
    assert code == 2
    assert output["error"]["code"] == "PROJECT_FORBIDDEN"
    assert "result" not in output


def test_execution_output_limit_is_preserved_without_partial_result(local, monkeypatch):
    _, _, _, _, call = local
    monkeypatch.setattr(
        api,
        "plan_edt_attribute_three_way",
        lambda *a, **kw: {"evidence": "PRIVATE_PAYLOAD" * (2 * 1024 * 1024)},
    )
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "OUTPUT_LIMIT_EXCEEDED"
    assert "PRIVATE_PAYLOAD" not in json.dumps(output)
    assert "result" not in output
