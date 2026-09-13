"""Owner-report CLI binds durable receipts to the authenticated project."""

import json
import os
import sqlite3

import pytest

import rentgen_core as api
from rentgen_core.owner_report import build_owner_report

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows owner-report lock")


@pytest.fixture
def project_fixture(tmp_path):
    owner = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    registered = registry.register(
        owner, source_root=source, state_root=tmp_path / "state", display_name="A"
    )
    snapshot = "b" * 64
    with sqlite3.connect(registered.state_root / "state.sqlite3") as connection:
        connection.execute(
            "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                registered.project_id,
                snapshot,
                snapshot,
                "a" * 64,
                "a" * 64,
                "generations/" + snapshot,
                1,
                "2026-09-13T00:00:00+00:00",
            ),
        )
    resolver = api.ContextResolver(registry)
    ctx = resolver.resolve_context(owner, api.Explicit(registered.project_id))
    return ctx, resolver


@pytest.fixture
def command(project_fixture, monkeypatch, capsys):
    import rentgen_core.cli as cli
    from rentgen_core.local import LocalRuntime

    ctx, resolver = project_fixture
    runtime = LocalRuntime(resolver.registry.path)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: ctx.principal)
    monkeypatch.setattr(cli, "_runtime", lambda args: runtime)

    def invoke(name, *args, success=True):
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
        output = capsys.readouterr().out
        assert code == (0 if success else 2), output
        return json.loads(output)

    return ctx, invoke


def test_owner_report_cli_save_get_and_list(command, tmp_path):
    ctx, invoke = command
    snapshot = "b" * 64
    store = ctx.state.path.parent / "owner-reports"
    report = build_owner_report(ctx.project_id, snapshot)
    payload = tmp_path / "report.json"
    payload.write_text(json.dumps(report), encoding="utf-8")

    saved = invoke(
        "owner-report-save",
        "--store",
        store,
        "--snapshot",
        snapshot,
        "--report-json",
        payload,
    )
    receipt = saved["result"]
    assert receipt["status"] == "stored"
    loaded = invoke(
        "owner-report-get",
        "--store",
        store,
        "--snapshot",
        snapshot,
        "--report-id",
        receipt["report_id"],
    )
    assert loaded["result"] == receipt
    listed = invoke(
        "owner-report-list",
        "--store",
        store,
        "--snapshot",
        snapshot,
    )
    assert listed["result"] == [
        {
            key: receipt[key]
            for key in (
                "schema",
                "report_id",
                "project_id",
                "snapshot_id",
                "status",
                "created_at",
                "receipt_id",
            )
        }
    ]


def test_owner_report_cli_rejects_report_snapshot_mismatch(command, tmp_path):
    ctx, invoke = command
    store = ctx.state.path.parent / "owner-reports"
    report = build_owner_report(ctx.project_id, "a" * 64)
    payload = tmp_path / "report.json"
    payload.write_text(json.dumps(report), encoding="utf-8")
    result = invoke(
        "owner-report-save",
        "--store",
        store,
        "--snapshot",
        "b" * 64,
        "--report-json",
        payload,
        success=False,
    )
    assert result["error"]["code"] == "OWNER_REPORT_STORE_CONTEXT"


def test_owner_report_cli_rejects_store_outside_project_state(command, tmp_path):
    ctx, invoke = command
    report = build_owner_report(ctx.project_id, "b" * 64)
    payload = tmp_path / "report.json"
    payload.write_text(json.dumps(report), encoding="utf-8")
    result = invoke(
        "owner-report-save",
        "--store",
        ctx.state.path.parent.parent / "outside",
        "--snapshot",
        "b" * 64,
        "--report-json",
        payload,
        success=False,
    )
    assert result["error"]["code"] == "OWNER_REPORT_STORE_INVALID"


def test_owner_report_cli_rejects_internal_generation_as_store(command, tmp_path):
    ctx, invoke = command
    report = build_owner_report(ctx.project_id, "b" * 64)
    payload = tmp_path / "report.json"
    payload.write_text(json.dumps(report), encoding="utf-8")
    result = invoke(
        "owner-report-save",
        "--store",
        ctx.state.path.parent / "generations" / "b",
        "--snapshot",
        "b" * 64,
        "--report-json",
        payload,
        success=False,
    )
    assert result["error"]["code"] == "OWNER_REPORT_STORE_INVALID"


def test_owner_report_cli_rejects_unpublished_snapshot(command, tmp_path):
    ctx, invoke = command
    snapshot = "c" * 64
    report = build_owner_report(ctx.project_id, snapshot)
    payload = tmp_path / "report.json"
    payload.write_text(json.dumps(report), encoding="utf-8")
    result = invoke(
        "owner-report-save",
        "--store",
        ctx.state.path.parent / "owner-reports",
        "--snapshot",
        snapshot,
        "--report-json",
        payload,
        success=False,
    )
    assert result["error"]["code"] == "SNAPSHOT_NOT_FOUND"
