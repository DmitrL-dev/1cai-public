import json
import sys

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


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows capture and native archive contract"
)
def test_native_archive_cli_archives_metadata_run_before_any_new_evidence(
    captured, monkeypatch, capsys
):
    ctx, operation, run, preview = metadata_fixtures._finished_run(captured)
    monkeypatch.setattr(cli, "current_local_principal", lambda: ctx.principal)
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


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows capture and native archive contract"
)
def test_native_archive_cli_redacts_snapshot_error_after_access_revoke(
    captured, monkeypatch, capsys
):
    ctx, operation, run, _ = metadata_fixtures._finished_run(captured)
    monkeypatch.setattr(cli, "current_local_principal", lambda: ctx.principal)

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


@pytest.mark.skipif(
    sys.platform not in {"linux", "darwin"},
    reason="Actual unsupported OS native archive refusal",
)
def test_native_archive_cli_refuses_unsupported_os_before_identity_runtime_or_archive_io(
    tmp_path, monkeypatch, capsys
):
    def forbidden(*args, **kwargs):
        pytest.fail("Unsupported native archive accessed identity, runtime, or archive")

    monkeypatch.setattr(cli, "current_local_principal", forbidden)
    monkeypatch.setattr(cli, "_runtime", forbidden)
    monkeypatch.setattr("rentgen_core.native_resources.archive_native_run", forbidden)
    missing = tmp_path / "not-created"
    argv = [
        "native-archive",
        "--registry",
        str(missing / "registry.sqlite3"),
        "--identity-profile",
        str(missing / "identity.json"),
        "--project",
        "11111111-1111-4111-8111-111111111111",
        "--snapshot",
        "b" * 64,
        "--operation-id",
        "22222222-2222-4222-8222-222222222222",
        "--namespace",
        "metadata-runs",
        "--profile-id",
        "a" * 64,
    ]
    assert cli.main(argv) == 2
    output = capsys.readouterr()
    error = json.loads(output.out)["error"]
    assert output.err == ""
    assert error["code"] == "CAPABILITY_UNAVAILABLE"
    assert error["details"]["operation"] == "native-archive"
    assert error["details"]["capability"] == "native.execution"
    assert error["details"]["platform"] == sys.platform
    assert not missing.exists()
