"""Caller-selected byte trees expose only an authenticated, bounded summary."""

import base64
import json
import os
from pathlib import Path

import pytest

import rentgen_core as api
from rentgen_core import cli
from rentgen_core.local import LocalRuntime
from project_access_test_support import force_legacy_membership
from test_metadata_three_way_materialize import PATH, xml


def arguments(*extra):
    return [
        "metadata-materialize",
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


def test_parser_requires_three_explicit_inputs_without_snapshot():
    parsed = cli._parser().parse_args(arguments())
    assert parsed.base_json == Path("base.json")
    assert parsed.current_json == Path("current.json")
    assert parsed.upstream_json == Path("upstream.json")
    with pytest.raises(api.CoreError):
        cli._parser().parse_args(arguments()[:-2])


@pytest.mark.parametrize(
    "option",
    [
        "--output",
        "--workspace",
        "--apply",
        "--snapshot",
        "--operation-id",
        "--profile-id",
        "--base-json",
    ],
)
def test_parser_refuses_unsafe_or_repeated_options(option):
    cli._parser().parse_args(arguments())
    with pytest.raises(api.CoreError):
        cli._parser().parse_args(arguments(option, "forbidden"))


@pytest.fixture
def local(tmp_path, monkeypatch, capsys):
    if os.name != "nt":
        pytest.skip("Windows registry contract")
    principal = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(
        principal, source_root=source, state_root=tmp_path / "state", display_name="CLI"
    )
    runtime = LocalRuntime(registry.path)
    ctx = runtime.state_context(principal, project.project_id)
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

    write({}, {}, {})
    return ctx, paths, write, call


def test_disjoint_merge_returns_deterministic_summary_without_writes(
    local, monkeypatch
):
    ctx, paths, write, call = local
    trees = (
        {PATH: xml("<Code>CAT</Code>")},
        {PATH: xml("<Code>CAT</Code>", name="private_local")},
        {PATH: xml("<Code>private_upstream</Code>")},
    )
    write(*trees)
    expected = api.materialize_metadata_three_way(*trees)
    expected.pop("candidate")
    before = {
        p: p.read_bytes() for p in ctx.source_root.parent.rglob("*") if p.is_file()
    }
    monkeypatch.setattr(
        LocalRuntime,
        "resolve",
        lambda *a, **k: pytest.fail("Snapshot/source resolution forbidden"),
    )
    code, output = call()
    assert code == 0, output
    assert output["result"] == expected
    assert call()[1]["result"] == expected
    assert "private_local" not in json.dumps(output)
    assert "private_upstream" not in json.dumps(output)
    after = {
        p: p.read_bytes() for p in ctx.source_root.parent.rglob("*") if p.is_file()
    }
    assert before == after


def test_summary_requires_no_source_edit_permission(local):
    ctx, _, _, call = local
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:read", "analysis:run"})
    code, output = call()
    assert code == 0, output
    assert output["result"]["status"] == "ready"


@pytest.mark.parametrize("permission", ["project:read", "analysis:run"])
def test_authorization_precedes_payload_read(local, monkeypatch, permission):
    ctx, _, _, call = local
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(
            tx,
            ctx.principal,
            {"project:read", "analysis:run"} - {permission},
        )
    monkeypatch.setattr(
        cli,
        "_proposal_input",
        lambda *a, **k: pytest.fail("Payload read before authorization"),
    )
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "PROJECT_FORBIDDEN"


@pytest.mark.parametrize(
    "option,value",
    [
        ("--max-files", "0"),
        ("--max-files", "1025"),
        ("--max-file-bytes", "262145"),
        ("--max-total-bytes", "524289"),
    ],
)
def test_limits_checked_before_payload_read(local, monkeypatch, option, value):
    _, _, _, call = local
    monkeypatch.setattr(
        cli,
        "_proposal_input",
        lambda *a, **k: pytest.fail("Payload read before limits"),
    )
    code, output = call(option, value)
    assert code == 2
    assert output["error"]["code"] == "THREE_WAY_LIMIT"


@pytest.mark.parametrize(
    "raw",
    [
        '{"schema":1,"encoding":"base64","files":{"a":"","a":""}}',
        '{"schema":true,"encoding":"base64","files":{}}',
        '{"schema":1,"encoding":"utf-8","files":{"a":"private"}}',
        '{"schema":1,"encoding":"base64","files":{"a":[1,2]}}',
        '{"schema":1,"encoding":"base64","files":{"a":null}}',
        '{"schema":1,"encoding":"base64","files":{"a":"!!!private"}}',
        '{"schema":1,"encoding":"base64","files":{"a":"YR=="}}',
        '{"schema":1,"encoding":"base64","files":{"A":"","a":""}}',
        '{"schema":1,"encoding":"base64","files":{"../private":""}}',
        '{"schema":1,"encoding":"base64","files":{},"retained_path":"private"}',
        '{"private":NaN}',
        '{"private":',
    ],
)
def test_invalid_tree_fails_closed_without_payload(local, raw):
    _, paths, _, call = local
    paths[0].write_text(raw, encoding="utf-8")
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "INVALID_ARGUMENT"
    assert output["error"]["message"] == "Metadata tree JSON is invalid"
    assert "private" not in json.dumps(output)
    assert "result" not in output


def test_oversized_base64_refused_before_decode(local, monkeypatch):
    _, paths, _, call = local
    paths[0].write_text(
        json.dumps({"schema": 1, "encoding": "base64", "files": {"a": "A" * 349532}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        base64, "b64decode", lambda *a, **k: pytest.fail("Oversized base64 decoded")
    )
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "THREE_WAY_LIMIT"


@pytest.mark.parametrize(
    "extra",
    [("--max-files", "1"), ("--max-file-bytes", "1"), ("--max-total-bytes", "2")],
)
def test_lower_limits_enforced(local, extra):
    _, _, write, call = local
    write({"a": b"aa", "b": b"bb"}, {}, {})
    code, output = call(*extra)
    assert code == 2
    assert output["error"]["code"] == "THREE_WAY_LIMIT"


def test_json_input_byte_cap(local):
    _, paths, _, call = local
    paths[0].write_bytes(b" " * (1024 * 1024 + 1))
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "INVALID_ARGUMENT"
    assert output["error"]["message"] == "Proposal input exceeds its byte limit"


def test_conflict_returns_no_candidate_or_payload(local):
    _, _, write, call = local
    write(
        {PATH: xml()},
        {PATH: xml(name="private_current")},
        {PATH: xml(name="private_upstream")},
    )
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "THREE_WAY_CONFLICT"
    assert "private" not in json.dumps(output)
    assert "candidate" not in json.dumps(output)


def test_malformed_xml_returns_no_payload(local):
    _, _, write, call = local
    tree = {PATH: b"<private>"}
    write(tree, tree, tree)
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "THREE_WAY_METADATA_INVALID"
    assert "private" not in json.dumps(output)


def test_engine_error_details_are_not_cli_payload(local, monkeypatch):
    _, _, _, call = local

    def error(*args, **kwargs):
        raise api.CoreError(
            "THREE_WAY_CONFLICT", "private XML", details={"candidate": "private BSL"}
        )

    monkeypatch.setattr(api, "materialize_metadata_three_way", error)
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "THREE_WAY_CONFLICT"
    assert "private" not in json.dumps(output)
    assert "candidate" not in json.dumps(output)


def test_revocation_prevents_next_input_read(local, monkeypatch):
    ctx, paths, _, call = local
    original = cli._metadata_tree

    def revoke(*args, **kwargs):
        tree = original(*args, **kwargs)
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:read"})
        return tree

    paths[1].unlink()
    monkeypatch.setattr(cli, "_metadata_tree", revoke)
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "PROJECT_FORBIDDEN"


@pytest.mark.parametrize("failure", [False, True])
def test_output_reauthorizes_success_and_error(local, monkeypatch, failure):
    ctx, _, _, call = local
    original = api.materialize_metadata_three_way

    def revoke(*args, **kwargs):
        value = original(*args, **kwargs)
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:read"})
        if failure:
            raise api.CoreError(
                "THREE_WAY_CONFLICT", "private", details={"candidate": "private"}
            )
        return value

    monkeypatch.setattr(api, "materialize_metadata_three_way", revoke)
    code, output = call()
    assert code == 2
    assert output["error"]["code"] == "PROJECT_FORBIDDEN"
    assert "private" not in json.dumps(output)
    assert "result" not in output
