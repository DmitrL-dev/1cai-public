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
    monkeypatch.setattr(cli, "current_local_principal", lambda: ctx.principal)
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


def _start_cli_draft(command, project, tmp_path, original):
    ctx, resolver, module, _ = project
    with ctx.state.transaction(ctx.principal) as tx:
        assert tx.state_schema_version() == 4
    module.write_bytes(original)
    published = fixtures.publish(project)
    snapshot_id = published.snapshot.snapshot_id
    selected = resolver.resolve_context(
        ctx.principal, api.Explicit(ctx.project_id), snapshot_id
    )
    ref = selected.sources.resolve("base", "CommonModules/ОбщийМодуль/Ext/Module.bsl")
    ref_file = tmp_path / "draft-source-ref.json"
    ref_file.write_text(json.dumps(asdict(ref)), encoding="utf-8")
    draft_id = str(uuid4())
    first, _ = command(
        "draft-start",
        "--snapshot", snapshot_id,
        "--source-ref-json", ref_file,
        "--draft-id", draft_id,
        "--title", "Проверка значения",
        "--operation-id", str(uuid4()),
    )
    return snapshot_id, draft_id, ref_file, original, first["result"]


@pytest.fixture
def cli_draft(command, project, tmp_path):
    original = b"\xef\xbb\xbf" + project[2].read_bytes()
    return _start_cli_draft(command, project, tmp_path, original)


def test_draft_start_edit_preserves_utf8_without_bom_and_lf(
    command, project, tmp_path
):
    original = project[2].read_bytes().replace(b"\r\n", b"\n")
    snapshot_id, draft_id, ref_file, _, first = _start_cli_draft(
        command, project, tmp_path, original
    )
    assert first["revision"] == 1
    edits_file = tmp_path / "edits.json"
    edits_file.write_text(
        json.dumps([{"old_text": "Возврат 1;\n", "new_text": "Возврат 2;\n"}]),
        encoding="utf-8",
    )
    second, _ = command(
        "draft-edit",
        "--snapshot", snapshot_id,
        "--draft-id", draft_id,
        "--expected-revision", "1",
        "--edits-json", edits_file,
        "--operation-id", str(uuid4()),
    )
    assert second["result"]["revision"] == 2
    for revision, expected in (
        (1, original),
        (2, original.replace(b"1;\n", b"2;\n")),
    ):
        stored, _ = command(
            "draft-get", "--draft-id", draft_id, "--revision", revision
        )
        proposal = stored["result"]["proposal"]
        assert base64.b64decode(proposal["replacement"]["base64"]) == expected
        assert proposal["policy"]["bom"] is False
        assert proposal["policy"]["newline"] == "lf"
        assert proposal["source_ref"] == first["source_ref"]
    retained, _ = command(
        "source-read", "--source-ref-json", ref_file, "--base64"
    )
    assert base64.b64decode(retained["result"]["data"]) == original
    assert project[2].read_bytes() == original


def test_draft_start_edit_preserves_bytes_and_replays_after_later_revision(
    command, project, cli_draft, tmp_path
):
    snapshot_id, draft_id, ref_file, original, first = cli_draft
    assert first["revision"] == 1
    assert first["outcome"] == "committed"
    assert first["source_ref"] == json.loads(ref_file.read_text(encoding="utf-8"))
    edits_file = tmp_path / "edits.json"
    edits = [{"old_text": "Возврат 1;\r\n", "new_text": "Возврат 2;\r\n"}]
    edits_file.write_text(json.dumps(edits), encoding="utf-8")
    operation_id = str(uuid4())
    edit_args = (
        "--snapshot", snapshot_id,
        "--draft-id", draft_id,
        "--expected-revision", "1",
        "--edits-json", edits_file,
        "--operation-id", operation_id,
    )
    second, _ = command("draft-edit", *edit_args)
    assert second["result"]["revision"] == 2
    assert second["result"]["source_ref"] == first["source_ref"]
    later_edits = tmp_path / "later-edits.json"
    later_edits.write_text(
        json.dumps([{"old_text": "Возврат 2;", "new_text": "Возврат 3;"}]),
        encoding="utf-8",
    )
    third, _ = command(
        "draft-edit",
        "--snapshot", snapshot_id,
        "--draft-id", draft_id,
        "--expected-revision", "2",
        "--edits-json", later_edits,
        "--operation-id", str(uuid4()),
    )
    assert third["result"]["revision"] == 3
    replay, _ = command("draft-edit", *edit_args)
    assert replay["result"] == second["result"]
    replay_start, _ = command(
        "draft-start",
        "--snapshot", snapshot_id,
        "--source-ref-json", ref_file,
        "--draft-id", draft_id,
        "--title", first["title"],
        "--operation-id", first["operation_id"],
    )
    assert replay_start["result"] == first
    receipt, _ = command("draft-receipt", "--operation-id", operation_id)
    assert receipt["result"] == second["result"]
    history, _ = command("draft-history", "--draft-id", draft_id)
    assert history["result"]["items"] == [third["result"], second["result"], first]
    for revision, expected in (
        (1, original),
        (2, original.replace(b"1;\r\n", b"2;\r\n")),
        (3, original.replace(b"1;\r\n", b"3;\r\n")),
    ):
        stored, _ = command(
            "draft-get", "--draft-id", draft_id, "--revision", revision
        )
        proposal = stored["result"]["proposal"]
        assert base64.b64decode(proposal["replacement"]["base64"]) == expected
        assert proposal["source_ref"] == first["source_ref"]
        assert proposal["policy"]["bom"] is True
        assert proposal["policy"]["newline"] == "crlf"
    retained, _ = command(
        "source-read", "--source-ref-json", ref_file, "--base64"
    )
    assert base64.b64decode(retained["result"]["data"]) == original
    assert project[2].read_bytes() == original


def test_draft_edit_stale_revision_and_changed_operation_inputs_do_not_save(
    command, project, cli_draft, tmp_path
):
    snapshot_id, draft_id, ref_file, original, first = cli_draft
    edits_file = tmp_path / "edits.json"
    edits_file.write_text(
        json.dumps([{"old_text": "Возврат 1;", "new_text": "Возврат 2;"}]),
        encoding="utf-8",
    )
    operation_id = str(uuid4())
    common = (
        "--snapshot", snapshot_id,
        "--draft-id", draft_id,
        "--expected-revision", "1",
        "--edits-json", edits_file,
    )
    second, _ = command("draft-edit", *common, "--operation-id", operation_id)
    stale_operation = str(uuid4())
    stale, _ = command(
        "draft-edit", *common, "--operation-id", stale_operation, success=False
    )
    assert stale["error"]["code"] == "DRAFT_CONFLICT"
    assert stale["error"]["details"]["current_revision"] == 2
    missing, _ = command("draft-receipt", "--operation-id", stale_operation)
    assert missing["result"] is None
    edits_file.write_text(
        json.dumps([{"old_text": "Возврат 1;", "new_text": "Возврат 9;"}]),
        encoding="utf-8",
    )
    conflict, _ = command(
        "draft-edit", *common, "--operation-id", operation_id, success=False
    )
    assert conflict["error"]["code"] == "OPERATION_CONFLICT"
    start_conflict, _ = command(
        "draft-start",
        "--snapshot", snapshot_id,
        "--source-ref-json", ref_file,
        "--draft-id", draft_id,
        "--title", "Изменённое название",
        "--operation-id", first["operation_id"],
        success=False,
    )
    assert start_conflict["error"]["code"] == "OPERATION_CONFLICT"
    history, _ = command("draft-history", "--draft-id", draft_id)
    assert history["result"]["items"] == [second["result"], first]
    assert project[2].read_bytes() == original


def test_draft_commands_reject_mismatched_selected_snapshot(
    command, project, cli_draft, tmp_path, monkeypatch
):
    from rentgen_core.local import LocalRuntime

    snapshot_id, draft_id, ref_file, original, first = cli_draft
    current = original.replace(b"1;\r\n", b"4;\r\n")
    project[2].write_bytes(current)
    later = fixtures.publish(project).snapshot.snapshot_id
    assert later != snapshot_id
    edits_file = tmp_path / "edits.json"
    edits_file.write_text(
        json.dumps([{"old_text": "Возврат 1;", "new_text": "Возврат 2;"}]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        LocalRuntime, "resolve",
        lambda *args, **kwargs: pytest.fail("mismatched snapshot IO"),
    )
    for name, args in (
        (
            "draft-start",
            (
                "--draft-id", str(uuid4()),
                "--source-ref-json", ref_file,
                "--title", "Другая версия",
            ),
        ),
        (
            "draft-edit",
            (
                "--draft-id", draft_id,
                "--expected-revision", "1",
                "--edits-json", edits_file,
            ),
        ),
    ):
        value, _ = command(
            name, "--snapshot", later, "--operation-id", str(uuid4()),
            *args, success=False,
        )
        assert value["error"]["code"] == "SOURCE_REF_MISMATCH"
    history, _ = command("draft-history", "--draft-id", draft_id)
    assert history["result"]["items"] == [first]
    listing, _ = command("draft-list")
    assert listing["result"]["items"] == [first]
    assert project[2].read_bytes() == current


def test_draft_edit_rejects_unbounded_or_invalid_json_and_invalid_edits(
    command, project, cli_draft, tmp_path
):
    snapshot_id, draft_id, _, original, first = cli_draft
    payload = tmp_path / "invalid-edits.json"
    valid = b'[{"old_text":"1","new_text":"2"}]'
    for raw, code in (
        (b"[", "INVALID_ARGUMENT"),
        (b"\xff", "INVALID_ARGUMENT"),
        (b"\xef\xbb\xbf" + valid, "INVALID_ARGUMENT"),
        (b'[{"old_text":"1","new_text":"2","new_text":"3"}]', "INVALID_ARGUMENT"),
        (b'[{"old_text":"1","new_text":NaN}]', "INVALID_ARGUMENT"),
        (b" " * (1024 * 1024 + 1), "INVALID_ARGUMENT"),
        (b'{"old_text":"1","new_text":"2"}', "DRAFT_EDIT_INVALID"),
        (b"[]", "DRAFT_EDIT_INVALID"),
        (b'[{"old_text":"1","new_text":"2","actor":"forged"}]', "DRAFT_EDIT_INVALID"),
        (json.dumps([{"old_text": "1", "new_text": "2"}] * 17).encode(), "DRAFT_EDIT_INVALID"),
        (json.dumps([{"old_text": "1", "new_text": "я" * 4097}]).encode(), "DRAFT_EDIT_INVALID"),
        (b'[{"old_text":"absent","new_text":"2"}]', "DRAFT_EDIT_MISMATCH"),
    ):
        payload.write_bytes(raw)
        value, _ = command(
            "draft-edit",
            "--snapshot", snapshot_id,
            "--draft-id", draft_id,
            "--expected-revision", "1",
            "--edits-json", payload,
            "--operation-id", str(uuid4()),
            success=False,
        )
        assert value["error"]["code"] == code
    history, _ = command("draft-history", "--draft-id", draft_id)
    assert history["result"]["items"] == [first]
    assert project[2].read_bytes() == original


def test_draft_start_rejects_malformed_source_ref_json_without_saving(
    command, cli_draft, tmp_path
):
    snapshot_id, _, ref_file, _, first = cli_draft
    valid = ref_file.read_bytes()
    payload = tmp_path / "invalid-source-ref.json"
    for raw in (
        b"{",
        b"\xff",
        b"\xef\xbb\xbf" + valid,
        valid[:-1] + b',"layer_id":"base"}',
        b" " * (1024 * 1024 + 1),
        b"[]",
    ):
        payload.write_bytes(raw)
        value, _ = command(
            "draft-start",
            "--snapshot", snapshot_id,
            "--source-ref-json", payload,
            "--draft-id", str(uuid4()),
            "--title", "Неверный JSON",
            "--operation-id", str(uuid4()),
            success=False,
        )
        assert value["error"]["code"] == "INVALID_ARGUMENT"
    listing, _ = command("draft-list")
    assert listing["result"]["items"] == [first]


def test_draft_write_denial_precedes_selected_input_and_snapshot_io(
    command, project, tmp_path, monkeypatch
):
    import rentgen_core.cli as cli
    from rentgen_core.local import LocalRuntime

    ctx = project[0]
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:read", "project:admin"})
    monkeypatch.setattr(
        cli, "_json_file", lambda *args: pytest.fail("unauthorized payload IO")
    )
    monkeypatch.setattr(
        LocalRuntime, "resolve",
        lambda *args, **kwargs: pytest.fail("unauthorized snapshot IO"),
    )
    for name, args in (
        (
            "draft-start",
            ("--source-ref-json", tmp_path / "absent-ref.json", "--title", "Denied"),
        ),
        (
            "draft-edit",
            ("--edits-json", tmp_path / "absent-edits.json", "--expected-revision", "1"),
        ),
    ):
        value, _ = command(
            name,
            "--snapshot", "a" * 64,
            "--draft-id", str(uuid4()),
            "--operation-id", str(uuid4()),
            *args,
            success=False,
        )
        assert value["error"]["code"] == "PROJECT_FORBIDDEN"


@pytest.mark.parametrize("name", ["draft-start", "draft-edit"])
def test_draft_write_rechecks_edit_permission_before_emitting_committed_receipt(
    command, project, cli_draft, tmp_path, monkeypatch, name
):
    from rentgen_core import draft_editing

    snapshot_id, draft_id, ref_file, original, _ = cli_draft
    edits_file = tmp_path / "edits.json"
    edits_file.write_text(
        json.dumps([{"old_text": "Возврат 1;", "new_text": "Возврат 2;"}]),
        encoding="utf-8",
    )
    ctx = project[0]
    action_name = "start_draft" if name == "draft-start" else "edit_draft"
    action = getattr(draft_editing, action_name)
    committed = []

    def revoke_after_commit(*args, **kwargs):
        result = action(*args, **kwargs)
        committed.append(result)
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(
                tx, ctx.principal, {"project:read", "project:admin"}
            )
        return result

    monkeypatch.setattr(draft_editing, action_name, revoke_after_commit)
    args = (
        ("--source-ref-json", ref_file, "--title", "Сохранённый черновик")
        if name == "draft-start"
        else ("--edits-json", edits_file, "--expected-revision", "1")
    )
    operation_id = str(uuid4())
    value, _ = command(
        name,
        "--snapshot", snapshot_id,
        "--draft-id", str(uuid4()) if name == "draft-start" else draft_id,
        "--operation-id", operation_id,
        *args,
        success=False,
    )
    assert value["error"]["code"] == "PROJECT_FORBIDDEN"
    assert "result" not in value
    assert len(committed) == 1
    # Read permission still permits reconciliation; denial does not imply rollback.
    receipt, _ = command("draft-receipt", "--operation-id", operation_id)
    assert receipt["result"] == committed[0]
    assert project[2].read_bytes() == original
