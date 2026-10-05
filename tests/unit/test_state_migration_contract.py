"""Portable SQLite and reconciliation contracts for the schema-1 runner.

Real temporary SQLite databases exercise membership, WAL backup and migration.
These tests do not model Windows path confinement, native handle ownership,
process-kill boundaries or CLI process-SID authentication.
"""

from contextlib import closing
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from uuid import uuid4

import pytest

from rentgen_core import Principal
from rentgen_core.errors import CoreError
from rentgen_core.state import ProjectState, _SCHEMA_V1
from rentgen_core import state_migration as migration


@pytest.fixture
def state_v1(tmp_path):
    project_id = str(uuid4())
    state = ProjectState(tmp_path / "state.sqlite3", project_id)
    admin = Principal("owner", "local_os")
    reader = Principal("reader", "local_os")
    with closing(sqlite3.connect(state.path)) as db:
        db.executescript(_SCHEMA_V1)
        db.execute("INSERT INTO project VALUES (1, ?)", (project_id,))
        for actor, permissions in (
            (admin, ("project:read", "project:admin")),
            (reader, ("project:read",)),
        ):
            identity = (project_id, actor.id, actor.authority)
            db.execute("INSERT INTO memberships VALUES (?, ?, ?)", identity)
            db.executemany(
                "INSERT INTO membership_permissions VALUES (?, ?, ?, ?)",
                [(*identity, permission) for permission in permissions],
            )
        db.execute("CREATE TABLE owned_payload (id INTEGER PRIMARY KEY, value BLOB)")
        db.execute("INSERT INTO owned_payload VALUES (1, ?)", (b"original",))
        db.commit()
    return SimpleNamespace(state=state, admin=admin, reader=reader)


def _rows(path, table):
    with closing(sqlite3.connect(path)) as db:
        return db.execute(f'SELECT * FROM "{table}" ORDER BY 1,2').fetchall()


def _version(run):
    with run.state.transaction(run.admin) as tx:
        return tx.state_schema_version()


def _backup(run, target):
    with closing(sqlite3.connect(target)) as destination:
        with run.state.transaction(run.admin) as tx:
            tx.backup_v1(destination, pages=1)
        destination.execute("PRAGMA journal_mode=DELETE")


def _receipt(run, path):
    raw = path.read_bytes()
    return migration.StateBackupReceipt(
        str(uuid4()), run.state.project_id, str(run.state.path), str(path), 1,
        hashlib.sha256(raw).hexdigest(), len(raw),
        datetime.now(timezone.utc).isoformat(), run.admin.id, run.admin.authority,
    )


def test_backup_includes_committed_wal_without_changing_source(state_v1, tmp_path):
    run = state_v1
    destination = tmp_path / "backup.sqlite3"
    with closing(sqlite3.connect(run.state.path)) as writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        writer.execute("INSERT INTO owned_payload VALUES (2, ?)", (b"committed in WAL",))
        writer.commit()
        assert Path(str(run.state.path) + "-wal").stat().st_size > 0
        _backup(run, destination)
        assert _rows(destination, "owned_payload") == [
            (1, b"original"), (2, b"committed in WAL")
        ]
        assert _rows(destination, "memberships") == _rows(run.state.path, "memberships")
        assert _rows(destination, "membership_permissions") == _rows(run.state.path, "membership_permissions")
        assert _version(run) == 1
        with closing(sqlite3.connect(destination)) as db:
            assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert db.execute("PRAGMA foreign_key_check").fetchall() == []
            assert db.execute("PRAGMA user_version").fetchone() == (1,)


@pytest.mark.parametrize("actor", ["reader", "unknown"])
def test_runner_refuses_nonadmin_before_backup_filesystem_io(state_v1, tmp_path, monkeypatch, actor):
    run = state_v1
    principal = run.reader if actor == "reader" else Principal("unknown", "local_os")
    destination = tmp_path / "absent-backups"

    def unexpected(*args, **kwargs):
        pytest.fail("Backup directory ownership was attempted before admin authorization")

    monkeypatch.setattr(migration, "_pin_migration_directory", unexpected)
    with pytest.raises(CoreError) as error:
        migration.migrate_project_state(
            run.state, principal, backup_directory=destination, operation_id=str(uuid4())
        )
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert not destination.exists()
    assert _version(run) == 1


@pytest.mark.parametrize("write,maximum,expected", [
    (True, 1024**2, "MIGRATION_BACKUP_INVALID"),
    (False, 1, "MIGRATION_BACKUP_LIMIT"),
])
def test_backup_refuses_write_uow_and_oversize_before_copy(state_v1, tmp_path, write, maximum, expected):
    run = state_v1
    with closing(sqlite3.connect(tmp_path / "empty.sqlite3")) as destination:
        with run.state.transaction(run.admin, write=write) as tx:
            with pytest.raises(CoreError) as error:
                tx.backup_v1(destination, max_backup_bytes=maximum)
        assert error.value.code == expected
        assert destination.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    assert _version(run) == 1


def test_migration_preserves_membership_payload_and_retained_backup(state_v1, tmp_path):
    run = state_v1
    backup = tmp_path / "backup.sqlite3"
    _backup(run, backup)
    before = backup.read_bytes()
    membership = _rows(run.state.path, "membership_permissions")
    run.state.migrate_v1_to_v2(run.admin)
    assert _version(run) == 2
    assert _rows(run.state.path, "membership_permissions") == membership
    assert _rows(run.state.path, "owned_payload") == [(1, b"original")]
    with run.state.transaction(run.admin) as tx:
        assert tx.get_source_configuration().revision == 1
    assert backup.read_bytes() == before
    assert _rows(backup, "owned_payload") == [(1, b"original")]


def test_already_current_runner_creates_no_backup_and_claims_no_attribution(state_v1, tmp_path, monkeypatch):
    run = state_v1
    run.state.migrate_v1_to_v2(run.admin)
    destination = tmp_path / "absent-backups"
    monkeypatch.setattr(migration, "_pin_migration_directory", lambda *a: pytest.fail("Unexpected backup IO"))
    result = migration.migrate_project_state(
        run.state, run.admin, backup_directory=destination, operation_id=str(uuid4())
    )
    assert result.outcome == "already_current"
    assert result.state_version_confirmed == 2
    assert result.migration_attribution == "not_proven"
    assert result.backup is None
    assert not destination.exists()


@pytest.mark.parametrize("version", [3, 4])
def test_runner_refuses_newer_schema_before_backup_io(state_v1, tmp_path, monkeypatch, version):
    run = state_v1
    with closing(sqlite3.connect(run.state.path)) as db:
        db.execute(f"PRAGMA user_version={version}")
    destination = tmp_path / "absent-backups"
    monkeypatch.setattr(migration, "_pin_migration_directory", lambda *a: pytest.fail("Unexpected backup IO"))
    with pytest.raises(CoreError) as error:
        migration.migrate_project_state(
            run.state, run.admin, backup_directory=destination, operation_id=str(uuid4())
        )
    assert error.value.code == "MIGRATION_TARGET_MISMATCH"
    assert not destination.exists()
    assert _version(run) == version


@pytest.mark.parametrize("failure", [OSError("lost acknowledgment"), KeyboardInterrupt()])
def test_upgrade_reconciles_committed_schema_after_lost_response(state_v1, tmp_path, monkeypatch, failure):
    run = state_v1
    backup = tmp_path / "backup.sqlite3"
    _backup(run, backup)
    receipt = _receipt(run, backup)

    def boundary(name, **values):
        if name == "after_migration":
            raise failure

    monkeypatch.setattr(migration, "_boundary", boundary)
    result = migration._upgrade(
        run.state, run.admin, receipt, existed=False, attempt=tmp_path, check=lambda: None
    )
    assert _version(run) == 2
    assert result.outcome == "reconciled"
    assert result.migration_attribution == "not_proven"
    assert result.backup == receipt
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == receipt.sha256


def test_revocation_before_migration_preserves_known_refusal(state_v1, tmp_path, monkeypatch):
    run = state_v1
    backup = tmp_path / "backup.sqlite3"
    _backup(run, backup)
    receipt = _receipt(run, backup)

    def boundary(name, **values):
        if name == "before_migration":
            with closing(sqlite3.connect(run.state.path)) as db:
                db.execute("DELETE FROM membership_permissions WHERE principal_id=? AND permission='project:admin'", (run.admin.id,))
                db.commit()

    monkeypatch.setattr(migration, "_boundary", boundary)
    with pytest.raises(CoreError) as error:
        migration._upgrade(
            run.state, run.admin, receipt, existed=False, attempt=tmp_path, check=lambda: None
        )
    assert error.value.code == "PROJECT_FORBIDDEN"
    with closing(sqlite3.connect(run.state.path)) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (1,)
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == receipt.sha256


@pytest.mark.parametrize("primary", [False, True])
def test_cleanup_failure_is_recorded_without_masking_primary(primary):
    status = migration._BackupPinStatus()
    closed = []

    def close(handle):
        closed.append(handle)
        if handle == 2:
            raise OSError("injected close failure")

    ops = SimpleNamespace(close=close)
    original = OSError("original failure")
    with pytest.raises(OSError if primary else CoreError) as error:
        try:
            if primary:
                raise original
        finally:
            migration._close_backup_pins(ops, [1, 2, 3], status)
    assert closed == [3, 2, 1]
    assert status.cleanup_failed
    if primary:
        assert error.value is original
    else:
        assert error.value.code == "MIGRATION_BACKUP_CLEANUP_FAILED"
