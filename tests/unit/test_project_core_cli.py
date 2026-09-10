"""CLI operation semantics with real core and explicitly injected graph adapters."""
from project_access_test_support import force_legacy_membership
from dataclasses import asdict
import base64
import importlib
import json
from uuid import UUID, uuid4

import pytest
import rentgen_core as api
import test_project_core_publication as fixtures

project = fixtures.project
scanner = fixtures.scanner
pytestmark = fixtures.pytestmark


def test_source_list_passes_search_options_and_preserves_default_listing(
    command, project
):
    (project[2].parents[3] / "A.xml").write_bytes(b"<data/>")
    receipt = fixtures.publish(project)
    default, _ = command("source-list", "--snapshot", receipt.snapshot.snapshot_id)
    assert len(default["result"]["entries"]) == 2
    found, _ = command(
        "source-list",
        "--snapshot",
        receipt.snapshot.snapshot_id,
        "--query",
        "ОБЩИЙМОДУЛЬ",
        "--kind",
        "module",
        "--layer",
        "base",
    )
    assert [item["ref"]["relative_path"] for item in found["result"]["entries"]] == [
        "CommonModules/ОбщийМодуль/Ext/Module.bsl"
    ]


@pytest.fixture
def command(project, monkeypatch, capsys):
    cli = importlib.import_module("rentgen_core.cli")
    from rentgen_core.local import LocalRuntime

    ctx, resolver, _, builder = project
    runtime = LocalRuntime(
        resolver.registry.path, resolver.graph_reader_factory, builder
    )
    monkeypatch.setattr(cli, "current_windows_principal", lambda: ctx.principal)
    monkeypatch.setattr(cli, "_runtime", lambda args: runtime)

    def call(name, *args, success=True):
        code = cli.main(
            [
                name,
                "--registry",
                str(resolver.registry.path),
                "--project",
                ctx.project_id,
                *map(str, args),
            ]
        )
        output = capsys.readouterr()
        assert code == (0 if success else 2), (output.out, output.err)
        return json.loads(output.out), output.err

    return call


def test_capture_reads_head_once_and_never_retries_conflict(
    command, project, monkeypatch
):
    import rentgen_core.cli as cli
    from rentgen_core.authorization import StateTransaction

    calls = []
    heads = []
    original_head = StateTransaction.get_project_head

    def read_head(tx):
        heads.append(True)
        return original_head(tx)

    def conflict(ctx, **kwargs):
        calls.append(kwargs)
        raise api.CoreError("HEAD_CONFLICT", "concurrent publication")

    monkeypatch.setattr(cli, "capture_and_publish", conflict, raising=False)
    monkeypatch.setattr(StateTransaction, "get_project_head", read_head)
    value, stderr = command("capture", success=False)
    assert value["error"]["code"] == "HEAD_CONFLICT"
    assert len(calls) == 1 and calls[0]["expected_head"].revision == 0
    assert len(heads) == 1
    recovery = json.loads(stderr)["recovery"]
    assert str(UUID(recovery["operation_id"])) == recovery["operation_id"]
    assert recovery["expected_head"] == asdict(calls[0]["expected_head"])


def test_real_capture_binary_output_graph_and_replay_after_later_head(
    command, project, tmp_path
):
    original = project[2].read_bytes()
    first, stderr = command("capture")
    recovery = json.loads(stderr.splitlines()[0])["recovery"]
    first_snapshot = first["result"]["snapshot"]["snapshot_id"]
    expected = tmp_path / "head.json"
    expected.write_text(json.dumps(recovery["expected_head"]), encoding="utf-8")
    project[2].write_bytes(original.replace(b"1", b"2"))
    second, _ = command("capture")
    assert first_snapshot != second["result"]["snapshot"]["snapshot_id"]
    replay, _ = command(
        "capture",
        "--operation-id",
        recovery["operation_id"],
        "--expected-head-json",
        expected,
    )
    assert replay["result"] == first["result"]
    path = "CommonModules/ОбщийМодуль/Ext/Module.bsl"
    encoded, _ = command(
        "source-read",
        "--snapshot",
        first_snapshot,
        "--layer",
        "base",
        "--path",
        path,
        "--base64",
    )
    assert base64.b64decode(encoded["result"]["data"]) == original
    assert encoded["result"]["encoding"] == "base64"
    ref_file = tmp_path / "ref.json"
    ref_file.write_text(json.dumps(encoded["result"]["ref"]), encoding="utf-8")
    destination = tmp_path / "raw.bsl"
    command("source-read", "--source-ref-json", ref_file, "--output", destination)
    assert destination.read_bytes() == original
    failure, _ = command(
        "source-read",
        "--source-ref-json",
        ref_file,
        "--output",
        destination,
        success=False,
    )
    assert failure["error"]["code"] == "LOCAL_IO_ERROR"
    graph, _ = command("graph-resolve", "--source-ref-json", ref_file)
    assert graph["result"]["snapshot_id"] == first_snapshot
    assert graph["result"]["capabilities"]["quality"] == "unavailable"
    impact, _ = command("impact", "--source-ref-json", ref_file, "--depth", "1")
    assert impact["result"]["snapshot_id"] == first_snapshot


@pytest.mark.parametrize(
    "args", [("--operation-id", str(uuid4())), ("--expected-head-json", "absent.json")]
)
def test_capture_replay_requires_both_original_fields(command, args):
    value, _ = command("capture", *args, success=False)
    assert value["error"]["code"] == "INVALID_ARGUMENT"


def test_denial_precedes_payload_source_and_output_io(
    command, project, tmp_path, monkeypatch
):
    import rentgen_core.cli as cli

    ctx = project[0]
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:admin"})
    monkeypatch.setattr(
        cli, "_json_file", lambda *args: pytest.fail("unauthorized payload IO")
    )
    output = tmp_path / "must-not-exist"
    for name, args in (
        ("layers-set", ("--expected-revision", "1", "--layers-json", "outside.json")),
        (
            "capture",
            ("--operation-id", str(uuid4()), "--expected-head-json", "outside.json"),
        ),
        ("source-read", ("--source-ref-json", "outside.json", "--output", output)),
    ):
        value, _ = command(name, *args, success=False)
        assert value["error"]["code"] == "PROJECT_FORBIDDEN"
    assert not output.exists()


def test_bounded_json_rejects_actor_duplicate_keys_and_large_payload(command, tmp_path):
    payload = tmp_path / "layers.json"
    for text in (
        '[{"actor":"forged"}]',
        '[{"layer_id":"base","layer_id":"other"}]',
        " " * (1024 * 1024 + 1),
    ):
        payload.write_text(text, encoding="utf-8")
        value, _ = command(
            "layers-set",
            "--expected-revision",
            "1",
            "--layers-json",
            payload,
            success=False,
        )
        assert value["error"]["code"] == "INVALID_ARGUMENT"


def test_cancellation_does_not_assert_rollback(command, monkeypatch):
    import rentgen_core.cli as cli

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "capture_and_publish", interrupted)
    value, stderr = command("capture", success=False)
    assert value["error"]["code"] == "OPERATION_INTERRUPTED"
    assert "committed" not in value["error"]["details"]
    assert json.loads(stderr)["recovery"]["operation_id"]


def test_unknown_publication_retains_unknown_semantics(command, monkeypatch):
    import rentgen_core.cli as cli

    def unknown(*args, **kwargs):
        raise api.CoreError(
            "PUBLICATION_OUTCOME_UNKNOWN",
            "Receipt could not be read",
            details={"operation_id": kwargs["operation_id"]},
        )

    monkeypatch.setattr(cli, "capture_and_publish", unknown)
    value, stderr = command("capture", success=False)
    assert value["error"]["code"] == "PUBLICATION_OUTCOME_UNKNOWN"
    assert (
        value["error"]["details"]["operation_id"]
        == json.loads(stderr)["recovery"]["operation_id"]
    )
    assert "committed" not in value["error"]["details"]


def test_source_ref_project_mismatch_precedes_retained_io(
    command, project, tmp_path, monkeypatch
):
    import rentgen_core.resolver as resolver

    monkeypatch.setattr(
        resolver,
        "verify_generation",
        lambda *args: pytest.fail("unexpected retained read"),
    )
    foreign = api.SourceRef(
        api.SnapshotRef(str(uuid4()), "a" * 64, "a" * 64),
        "base",
        "Module.bsl",
        "b" * 64,
    )
    payload = tmp_path / "foreign.json"
    payload.write_text(json.dumps(asdict(foreign)), encoding="utf-8")
    value, _ = command(
        "source-read", "--source-ref-json", payload, "--base64", success=False
    )
    assert value["error"]["code"] == "SOURCE_REF_MISMATCH"
