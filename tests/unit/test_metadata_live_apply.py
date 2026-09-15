"""Live Designer XML writer contract and recovery tests."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import test_metadata_runs as fixtures
import test_metadata_plans as plan_fixtures
import rentgen_core as api

from rentgen_core import metadata_apply, metadata_live_apply
from rentgen_core import cli
from rentgen_core import stdio_mcp
from test_stdio_native_archive import _Runtime


project, scanner, captured, pytestmark = (
    fixtures.project,
    fixtures.scanner,
    fixtures.captured,
    fixtures.pytestmark,
)


def _request(captured):
    ctx, preview_operation, run, preview = fixtures._finished_run(captured)
    request = {
        "preview_operation_id": preview_operation,
        "operation_id": str(uuid4()),
        "expected_preview_id": preview["preview_id"],
        "expected_head": api.get_project_head(ctx),
    }
    metadata_apply.preflight_apply(ctx, **request)
    return ctx, request, run, preview


def _bytes(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in Path(root).rglob("*")
        if path.is_file()
    }


def test_live_apply_changes_only_candidate_paths_and_undo_restores_source(
    captured,
):
    ctx, request, _, preview = _request(captured)
    before = _bytes(ctx.source_root)

    result = metadata_live_apply.apply_live(ctx, request["operation_id"])

    assert result["status"] == "applied"
    assert result["live_source_written"] is True
    assert result["changed_paths"] == [
        "Catalogs/Products.xml",
        "Catalogs/Products/Forms/ItemForm/Ext/Form.xml",
    ]
    assert _bytes(ctx.source_root)["Catalogs/Products.xml"] == (
        Path(
            plan_fixtures.FIXTURE.parent / "renamed/Catalogs/Products.xml"
        ).read_bytes()
    )
    assert metadata_live_apply.apply_live(ctx, request["operation_id"]) == result

    undo = metadata_live_apply.undo_live(ctx, request["operation_id"])

    assert undo["status"] == "undone"
    assert undo["live_source_written"] is True
    assert _bytes(ctx.source_root) == before
    assert metadata_live_apply.undo_live(ctx, request["operation_id"]) == undo


def test_candidate_delta_accepts_edt_normalization_before_the_same_edit(
    captured, monkeypatch
):
    ctx, request, _, preview = _request(captured)
    body = deepcopy(preview["preview"])
    original = body["inventories"]["original"]
    baseline = deepcopy(original)
    candidate = deepcopy(body["inventories"]["candidate"])
    changed_paths = [
        "Catalogs/Products.xml",
        "Catalogs/Products/Forms/ItemForm/Ext/Form.xml",
    ]
    for row in baseline:
        if row["path"] in changed_paths:
            row["sha256"] = "a" * 64
            row["size"] += 1
    body["inventories"]["baseline"] = baseline
    body["normalization"]["changes"] = [
        {
            "path": path,
            "before": next(row for row in original if row["path"] == path),
            "after": next(row for row in baseline if row["path"] == path),
            "kind": "modified",
        }
        for path in changed_paths
    ]
    body["edit"]["changes"] = [
        {
            "path": path,
            "before": next(row for row in baseline if row["path"] == path),
            "after": next(row for row in candidate if row["path"] == path),
            "kind": "modified",
        }
        for path in changed_paths
    ]
    altered = {**preview, "preview": body}
    monkeypatch.setattr(
        metadata_live_apply.metadata_runs, "get_preview", lambda *_: altered
    )
    monkeypatch.setattr(
        metadata_live_apply.preflight,
        "_evaluate",
        lambda *_: ("unavailable", []),
    )

    _, _, _, _, changed = metadata_live_apply._candidate_delta(
        ctx, request["operation_id"]
    )

    assert changed == changed_paths


def test_live_apply_refuses_stale_source_before_writing(captured):
    ctx, request, _, _ = _request(captured)
    target = ctx.source_root / "Catalogs/Products.xml"
    target.write_bytes(b"foreign")

    with pytest.raises(api.CoreError) as error:
        metadata_live_apply.apply_live(ctx, request["operation_id"])

    assert error.value.code == "METADATA_LIVE_APPLY_STALE"
    assert target.read_bytes() == b"foreign"


def test_live_undo_refuses_foreign_change_without_overwriting_it(captured):
    ctx, request, _, _ = _request(captured)
    metadata_live_apply.apply_live(ctx, request["operation_id"])
    target = ctx.source_root / "Catalogs/Products.xml"
    target.write_bytes(b"foreign after apply")

    with pytest.raises(api.CoreError) as error:
        metadata_live_apply.undo_live(ctx, request["operation_id"])

    assert error.value.code == "METADATA_LIVE_UNDO_CONFLICT"
    assert target.read_bytes() == b"foreign after apply"


def test_interrupted_live_apply_is_unknown_until_explicit_recovery(
    captured, monkeypatch
):
    ctx, request, _, _ = _request(captured)
    before = _bytes(ctx.source_root)
    original_replace = metadata_live_apply.os.replace
    calls = {"count": 0}

    def interrupt(source, target):
        calls["count"] += 1
        if str(target).startswith(str(ctx.source_root)) and calls["count"] == 2:
            raise OSError("simulated interruption")
        return original_replace(source, target)

    monkeypatch.setattr(metadata_live_apply.os, "replace", interrupt)
    with pytest.raises(OSError):
        metadata_live_apply.apply_live(ctx, request["operation_id"])
    monkeypatch.setattr(metadata_live_apply.os, "replace", original_replace)

    status = metadata_live_apply.get_live_status(ctx, request["operation_id"])
    assert status["status"] == "OUTCOME_UNKNOWN"
    recovered = metadata_live_apply.recover_live(
        ctx, request["operation_id"], target="original"
    )
    assert recovered["status"] == "recovered"
    assert (
        metadata_live_apply.get_live_status(ctx, request["operation_id"])["status"]
        == "recovered"
    )
    assert _bytes(ctx.source_root) == before


def test_tampered_live_receipt_requires_recovery(captured):
    ctx, request, _, _ = _request(captured)
    metadata_live_apply.apply_live(ctx, request["operation_id"])
    receipt = (
        metadata_live_apply.journal_path(ctx, request["operation_id"]) / "result.json"
    )
    value = json.loads(receipt.read_text("utf-8"))
    value["status"] = "undone"
    receipt.write_text(json.dumps(value), "utf-8")

    with pytest.raises(api.CoreError) as error:
        metadata_live_apply.get_live_status(ctx, request["operation_id"])

    assert error.value.code == "METADATA_LIVE_RECOVERY_REQUIRED"


def test_recovery_restores_a_missing_changed_file(captured):
    ctx, request, _, _ = _request(captured)
    metadata_live_apply.apply_live(ctx, request["operation_id"])
    target = ctx.source_root / "Catalogs/Products.xml"
    target.unlink()

    recovered = metadata_live_apply.recover_live(
        ctx, request["operation_id"], target="original"
    )

    assert recovered["status"] == "recovered"
    assert target.exists()


def test_repeated_recovery_rechecks_terminal_source(captured):
    ctx, request, _, _ = _request(captured)
    metadata_live_apply.apply_live(ctx, request["operation_id"])
    recovered = metadata_live_apply.recover_live(
        ctx, request["operation_id"], target="original"
    )
    target = ctx.source_root / "Catalogs/Products.xml"
    target.write_bytes(b"foreign after recovery")

    with pytest.raises(api.CoreError) as error:
        metadata_live_apply.recover_live(
            ctx, request["operation_id"], target="original"
        )

    assert error.value.code == "METADATA_LIVE_UNDO_CONFLICT"
    assert recovered["status"] == "recovered"


def test_cli_exposes_live_apply_with_explicit_snapshot_and_operation(
    captured, monkeypatch, capsys
):
    ctx, request, _, _ = _request(captured)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: ctx.principal)
    argv = [
        "metadata-live-apply",
        "--registry",
        str(ctx.source_root.parent / "registry.sqlite3"),
        "--project",
        ctx.project_id,
        "--snapshot",
        ctx.snapshot.snapshot_id,
        "--operation-id",
        request["operation_id"],
    ]
    assert cli.main(argv) == 0
    assert json.loads(capsys.readouterr().out)["result"]["status"] == "applied"


def test_mcp_exposes_explicit_live_operation_contract():
    for name in (
        "rentgen_metadata_live_apply",
        "rentgen_metadata_live_undo",
        "rentgen_metadata_live_status",
    ):
        assert name in stdio_mcp.TOOL_SCHEMAS
        stdio_mcp.validate_arguments(
            name,
            {
                "project_id": "12345678-1234-4234-8234-123456789abc",
                "snapshot_id": "a" * 64,
                "operation_id": "12345678-1234-4234-8234-123456789abc",
            },
        )
    stdio_mcp.validate_arguments(
        "rentgen_metadata_live_recover",
        {
            "project_id": "12345678-1234-4234-8234-123456789abc",
            "snapshot_id": "a" * 64,
            "operation_id": "12345678-1234-4234-8234-123456789abc",
            "target": "original",
        },
    )


def test_mcp_dispatches_live_apply_with_full_mutation_scope(monkeypatch):
    runtime = _Runtime()
    principal = SimpleNamespace(id="tester", authority="local_os")
    calls = []

    def fake_apply(ctx, operation_id):
        calls.append((ctx, operation_id))
        return {
            "schema": 1,
            "status": "applied",
            "live_source_written": True,
            "changed_paths": ["Catalogs/Products.xml"],
        }

    monkeypatch.setattr(metadata_live_apply, "apply_live", fake_apply)
    result = stdio_mcp._execute(
        runtime,
        principal,
        "rentgen_metadata_live_apply",
        {
            "project_id": "11111111-1111-4111-8111-111111111111",
            "snapshot_id": "a" * 64,
            "operation_id": "22222222-2222-4222-8222-222222222222",
        },
        protocol_request_id=9,
        scope=stdio_mcp.McpScope(
            project_id="11111111-1111-4111-8111-111111111111",
            allowed_tools={"rentgen_metadata_live_apply"},
        ),
    )

    assert result.isError is False
    assert result.structuredContent["result"]["metadata_live"]["status"] == "applied"
    assert result.meta["rentgenOutputScope"]["permissions"] == [
        "analysis:run",
        "project:read",
        "source:edit",
    ]
    assert calls[0][1] == "22222222-2222-4222-8222-222222222222"
