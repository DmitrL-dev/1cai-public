import json

import pytest
import test_metadata_runs as metadata_fixtures
from project_access_test_support import force_legacy_membership
from rentgen_core import cli
from rentgen_core.errors import CoreError

captured = metadata_fixtures.captured
project = metadata_fixtures.project
scanner = metadata_fixtures.scanner


def test_native_archive_parser_requires_explicit_namespace_and_binding():
    parser = cli._parser()
    base = [
        "native-archive",
        "--registry",
        "registry.sqlite3",
        "--project",
        "project",
        "--snapshot",
        "snapshot",
        "--operation-id",
        "operation",
        "--namespace",
        "metadata-runs",
        "--profile-id",
        "a" * 64,
    ]
    parsed = parser.parse_args(base)
    assert parsed.namespace == "metadata-runs"
    assert parsed.snapshot == "snapshot"
    assert parsed.operation_id == "operation"
    assert parsed.profile_id == "a" * 64
    with pytest.raises(CoreError):
        parser.parse_args(base + ["--namespace", "test-runs"])


def test_native_archive_cli_archives_metadata_run_before_any_new_evidence(
    captured, monkeypatch, capsys
):
    ctx, operation, run, preview = metadata_fixtures._finished_run(captured)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: ctx.principal)
    argv = [
        "native-archive",
        "--registry",
        str(ctx.source_root.parent / "registry.sqlite3"),
        "--project",
        ctx.project_id,
        "--snapshot",
        ctx.snapshot.snapshot_id,
        "--operation-id",
        operation,
        "--namespace",
        "metadata-runs",
        "--profile-id",
        "a" * 64,
    ]
    assert cli.main(argv) == 0
    value = json.loads(capsys.readouterr().out)
    assert value["result"]["status"] == "archived"
    assert metadata_fixtures.runs.get_preview(ctx, operation) == preview
    with pytest.raises(CoreError, match="Archived"):
        metadata_fixtures.runs.attach_business_evidence(
            ctx, operation, metadata_fixtures._evidence(preview)
        )


def test_native_archive_cli_redacts_snapshot_error_after_access_revoke(
    captured, monkeypatch, capsys
):
    ctx, operation, run, _ = metadata_fixtures._finished_run(captured)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: ctx.principal)

    def revoked_resolve(self, principal, project_id, snapshot_id=None):
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:read"})
        raise CoreError("SNAPSHOT_CORRUPT", "Retained source digest mismatch")

    monkeypatch.setattr(cli.LocalRuntime, "resolve", revoked_resolve)
    argv = [
        "native-archive",
        "--registry",
        str(ctx.source_root.parent / "registry.sqlite3"),
        "--project",
        ctx.project_id,
        "--snapshot",
        ctx.snapshot.snapshot_id,
        "--operation-id",
        operation,
        "--namespace",
        "metadata-runs",
        "--profile-id",
        "a" * 64,
    ]
    assert cli.main(argv) == 2
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["code"] == "PROJECT_FORBIDDEN"
    assert "SNAPSHOT_CORRUPT" not in json.dumps(error)
    assert not (ctx.state.path.parent / "native-archive").exists()
    assert run.exists()
