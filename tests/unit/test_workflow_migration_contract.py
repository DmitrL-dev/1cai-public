"""Schema3→4 workflow upgrade contracts on real temporary SQLite state.

The state-level tests run on every OS. The verified-backup runner uses Windows
retained directory pins and is exercised separately under Windows CI.
"""
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from rentgen_core import Principal
from rentgen_core.errors import CoreError
from rentgen_core.state import ProjectState, _SCHEMA_V1
from rentgen_core.state_migration import StateBackupReceipt
from rentgen_core import workflow_migration as workflow

V4_TABLES = {
    "workflow_receipts",
    "workflow_proposals",
    "workflow_draft_heads",
    "workflow_draft_revisions",
}


def _backup(state, actor, operation_id, schema_version, tmp_path):
    raw = b"verified backup bytes " + operation_id.encode()
    path = tmp_path / (operation_id + ".sqlite3")
    path.write_bytes(raw)
    return asdict(
        StateBackupReceipt(
            operation_id, state.project_id, str(state.path), str(path), schema_version,
            hashlib.sha256(raw).hexdigest(), len(raw),
            datetime.now(timezone.utc).isoformat(), actor.id, actor.authority,
        )
    )


@pytest.fixture
def state_v3(tmp_path):
    project_id = str(uuid4())
    state = ProjectState(tmp_path / "state.sqlite3", project_id)
    admin, reader = Principal("owner", "local_os"), Principal("reader", "local_os")
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
        db.execute("INSERT INTO owned_payload VALUES (1, ?)", (b"retained payload",))
        db.commit()
    state.migrate_v1_to_v2(admin)
    access = str(uuid4())
    state.migrate_v2_to_v3(
        admin, operation_id=access, backup=_backup(state, admin, access, 2, tmp_path)
    )
    return state, admin, reader


def _version(path):
    with closing(sqlite3.connect(path)) as db:
        return db.execute("PRAGMA user_version").fetchone()[0]


def _dump(path):
    with closing(sqlite3.connect(path)) as db:
        tables = [
            name
            for (name,) in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        return {
            name: db.execute(f'SELECT * FROM "{name}" ORDER BY 1, 2').fetchall()
            for name in tables
        }


def test_upgrade_keeps_every_existing_row_and_records_one_exact_receipt(state_v3, tmp_path):
    state, admin, _ = state_v3
    before = _dump(state.path)
    operation = str(uuid4())
    backup = _backup(state, admin, operation, 3, tmp_path)
    receipt = state.migrate_v3_to_v4(admin, operation_id=operation, backup=backup)
    after = _dump(state.path)
    assert _version(state.path) == 4
    assert set(after) - set(before) == V4_TABLES
    assert {name: after[name] for name in before} == before
    assert receipt["outcome"] == "committed" and receipt["backup"] == backup
    assert receipt["source_schema"] == 3 and receipt["state_version_confirmed"] == 4
    with state.transaction(admin) as tx:
        request, result = workflow.find_upgrade(tx, operation)
    assert result == receipt and request["backup"] == backup
    assert after["workflow_receipts"] == [
        row for row in after["workflow_receipts"] if row[1] == operation
    ]


@pytest.mark.parametrize("boundary", ["after_ddl", "after_version", "after_receipt"])
def test_failure_inside_the_unit_of_work_rolls_back_to_schema3(
    state_v3, tmp_path, monkeypatch, boundary
):
    state, admin, _ = state_v3
    before = _dump(state.path)
    operation = str(uuid4())
    backup = _backup(state, admin, operation, 3, tmp_path)

    def fail(name, **values):
        if name == boundary:
            raise OSError("injected failure at " + name)

    monkeypatch.setattr(workflow, "_state_boundary", fail)
    with pytest.raises(OSError):
        state.migrate_v3_to_v4(admin, operation_id=operation, backup=backup)
    assert _version(state.path) == 3
    assert _dump(state.path) == before
    monkeypatch.setattr(workflow, "_state_boundary", lambda *a, **k: None)
    assert state.migrate_v3_to_v4(admin, operation_id=operation, backup=backup)[
        "outcome"
    ] == "committed"


def test_replay_conflict_and_foreign_operation_attribution(state_v3, tmp_path):
    state, admin, _ = state_v3
    operation = str(uuid4())
    backup = _backup(state, admin, operation, 3, tmp_path)
    receipt = state.migrate_v3_to_v4(admin, operation_id=operation, backup=backup)
    assert state.migrate_v3_to_v4(admin, operation_id=operation, backup=backup) == receipt
    changed = dict(backup, sha256="0" * 64)
    with pytest.raises(CoreError) as error:
        state.migrate_v3_to_v4(admin, operation_id=operation, backup=changed)
    assert error.value.code == "OPERATION_CONFLICT"
    other = str(uuid4())
    # Schema4 reached by another operation is never claimed as this one's success.
    assert (
        state.migrate_v3_to_v4(
            admin, operation_id=other, backup=_backup(state, admin, other, 3, tmp_path)
        )
        is None
    )


def test_nonadmin_wrong_schema_and_foreign_backup_are_refused_without_change(
    state_v3, tmp_path
):
    state, admin, reader = state_v3
    operation = str(uuid4())
    backup = _backup(state, admin, operation, 3, tmp_path)
    before = _dump(state.path)
    with pytest.raises(CoreError) as error:
        state.migrate_v3_to_v4(reader, operation_id=operation, backup=backup)
    assert error.value.code == "PROJECT_FORBIDDEN"
    for bad in (
        dict(backup, schema_version=2),
        dict(backup, project_id=str(uuid4())),
        dict(backup, operation_id=str(uuid4())),
        dict(backup, size_bytes=True),
    ):
        with pytest.raises(CoreError):
            state.migrate_v3_to_v4(admin, operation_id=operation, backup=bad)
    assert _dump(state.path) == before
    with closing(sqlite3.connect(state.path)) as db:
        db.execute("PRAGMA user_version=2")
    with pytest.raises(CoreError) as error:
        state.migrate_v3_to_v4(admin, operation_id=operation, backup=backup)
    assert error.value.code == "MIGRATION_TARGET_MISMATCH"


@pytest.mark.parametrize(
    "tamper",
    [
        "UPDATE workflow_receipts SET result_json=replace(result_json, '\"committed\"', '\"forged\"')",
        "UPDATE workflow_receipts SET request_json=replace(request_json, '\"from_schema\":3', '\"from_schema\":2')",
        "UPDATE workflow_receipts SET recorded_at='2026-10-16T00:00:00'",
    ],
)
def test_tampered_upgrade_receipt_is_state_corrupt(state_v3, tmp_path, tamper):
    # A wrong action_version is already refused by the schema CHECK constraint.
    state, admin, _ = state_v3
    operation = str(uuid4())
    backup = _backup(state, admin, operation, 3, tmp_path)
    state.migrate_v3_to_v4(admin, operation_id=operation, backup=backup)
    with closing(sqlite3.connect(state.path)) as db:
        db.execute(tamper)
        db.commit()
    with pytest.raises(CoreError) as error:
        state.migrate_v3_to_v4(admin, operation_id=operation, backup=backup)
    assert error.value.code == "STATE_CORRUPT"


def test_operation_of_another_workflow_action_is_a_conflict(state_v3, tmp_path):
    state, admin, _ = state_v3
    operation = str(uuid4())
    state.migrate_v3_to_v4(
        admin, operation_id=operation, backup=_backup(state, admin, operation, 3, tmp_path)
    )
    other = str(uuid4())
    with closing(sqlite3.connect(state.path)) as db:
        row = db.execute("SELECT * FROM workflow_receipts").fetchone()
        db.execute(
            "INSERT INTO workflow_receipts VALUES (?,?,?,?,?,?,?,?,?)",
            (row[0], other, "draft.saved", *row[3:]),
        )
        db.commit()
    with state.transaction(admin) as tx:
        with pytest.raises(CoreError) as error:
            workflow.find_upgrade(tx, other)
    assert error.value.code == "OPERATION_CONFLICT"


@pytest.mark.skipif(os.name != "nt", reason="Verified backup runner uses Windows pins")
def test_runner_backup_opens_and_lost_acknowledgement_reconciles(
    state_v3, tmp_path, monkeypatch
):
    state, admin, reader = state_v3
    before = _dump(state.path)
    with pytest.raises(CoreError) as error:
        workflow.upgrade_project_workflows(
            state, reader, backup_directory=tmp_path / "refused", operation_id=str(uuid4())
        )
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert not (tmp_path / "refused").exists()
    operation = str(uuid4())

    def lost(name, **values):
        if name == "after_commit":
            raise OSError("lost acknowledgement after commit")

    monkeypatch.setattr(workflow, "_boundary", lost)
    result = workflow.upgrade_project_workflows(
        state, admin, backup_directory=tmp_path / "backups", operation_id=operation
    )
    assert _version(state.path) == 4
    assert result["outcome"] in {"committed", "reconciled"}
    assert result["migration_attribution"] == "operation_receipt"
    assert result["receipt"]["backup"] == result["backup"]
    backup = Path(result["backup"]["path"])
    raw = backup.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == result["backup"]["sha256"]
    with closing(sqlite3.connect(f"file:{backup}?mode=ro&immutable=1", uri=True)) as db:
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert db.execute("PRAGMA user_version").fetchone() == (3,)
    after = _dump(state.path)
    assert {name: after[name] for name in before} == before
    monkeypatch.setattr(workflow, "_boundary", lambda *a, **k: None)
    again = workflow.upgrade_project_workflows(
        state, admin, backup_directory=tmp_path / "backups", operation_id=operation
    )
    assert again["backup"] == result["backup"]
    assert again["receipt"] == result["receipt"]
