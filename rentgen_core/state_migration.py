"""Verified backups before explicit schema upgrades, without commit attribution.

Operation IDs identify a retained backup/runner attempt. They are deliberately
not claimed as atomic receipts of the existing schema migration transaction.
"""
from contextlib import closing, contextmanager, ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import time

from .errors import CoreError
from .manifests import canonical_bytes
from .snapshots import validate_operation_id
from ._windows_source_tree import flush_owned, pinned_retained


@dataclass(frozen=True)
class StateBackupReceipt:
    operation_id: str
    project_id: str
    source_path: str
    path: str
    schema_version: int
    sha256: str
    size_bytes: int
    created_at: str
    actor_id: str
    actor_authority: str


@dataclass(frozen=True)
class StateMigrationResult:
    operation_id: str
    project_id: str
    state_version_confirmed: int
    outcome: str
    backup: StateBackupReceipt | None
    migration_attribution: str = "not_proven"


def _boundary(name, **values):
    """Failure-injection seam; production performs no side effects here."""


def _version(state, principal):
    with state.transaction(principal) as tx:
        return tx.state_schema_version()


def _sidecars(path):
    if any(
        os.path.lexists(path.with_name(path.name + suffix))
        for suffix in ("-wal", "-shm", "-journal")
    ):
        raise CoreError("MIGRATION_BACKUP_CORRUPT", "Final backup has SQLite sidecars")


def _verify_backup(
    path, state, maximum, timeout_seconds, receipt=None, *, schema_version=1
):
    _sidecars(path)
    with pinned_retained(path, maximum) as raw:
        digest = hashlib.sha256(raw).hexdigest()
        if receipt is not None and (
            receipt.sha256 != digest or receipt.size_bytes != len(raw)
        ):
            raise CoreError(
                "MIGRATION_BACKUP_CORRUPT",
                "Backup bytes do not match the complete receipt",
            )
        deadline = time.monotonic() + timeout_seconds
        with closing(
            sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=0)
        ) as db:
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            if (
                db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]
                or db.execute("PRAGMA foreign_key_check").fetchall()
            ):
                raise CoreError(
                    "MIGRATION_BACKUP_CORRUPT",
                    "Backup failed SQLite consistency checks",
                )
            if db.execute("PRAGMA user_version").fetchone() != (
                schema_version,
            ) or db.execute(
                "SELECT project_id FROM project WHERE singleton=1"
            ).fetchone() != (
                state.project_id,
            ):
                raise CoreError(
                    "MIGRATION_BACKUP_CORRUPT",
                    "Backup schema/project identity mismatch",
                )
            tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if not {"project", "memberships", "membership_permissions"} <= tables:
                raise CoreError(
                    "MIGRATION_BACKUP_CORRUPT",
                    "Backup is missing the schema-1 state tables",
                )
            if schema_version in (2, 3):
                _verify_v2_schema(db, tables)
            if schema_version == 3:
                _verify_v3_schema(db)
        _sidecars(path)
        return digest, len(raw)


def _receipt_path(attempt):
    return attempt / "backup-receipt.json"


@dataclass
class _BackupPinStatus:
    cleanup_failed: bool = False


def _close_backup_pins(ops, handles, status):
    primary = sys.exc_info()[0] is not None
    failure = None
    for handle in reversed(handles):
        try:
            ops.close(handle)
        except BaseException as exc:
            status.cleanup_failed = True
            failure = failure or exc
    if failure is not None and not primary:
        raise CoreError(
            "MIGRATION_BACKUP_CLEANUP_FAILED",
            "Backup pin cleanup could not be confirmed",
        ) from failure


@contextmanager
def _pin_migration_directory(path, status):
    """Same strong directory boundary, with explicit close outcome for the runner."""
    from ._windows_source_tree import WindowsHandleOps, _require_local_path

    ops, handles = WindowsHandleOps(), []
    _require_local_path(ops, path)
    try:
        for ancestor in (*reversed(path.parents), path):
            handle = ops.open(ancestor, directory=True)
            handles.append(handle)
            if not ops.stamp(handle).directory or ops.final_path(handle) != ancestor:
                raise CoreError("MIGRATION_BACKUP_CORRUPT", "Invalid backup ancestor")
        yield path
    finally:
        _close_backup_pins(ops, handles, status)


@contextmanager
def _hold_verified_backup(
    attempt, state, operation_id, maximum, timeout, status, *, schema_version=2
):
    """Keep verified backup/receipt bytes stable through the caller UOW.

    Only handles/stamps survive the yield, not the complete backup byte buffer.
    The caller observes cleanup_failed even when a primary error is preserved,
    so reconciliation cannot turn uncertain resource cleanup into success.
    """
    from ._windows_source_tree import (
        WindowsHandleOps,
        _retained_stamp,
        _require_local_path,
    )

    if type(schema_version) is not int or schema_version not in (1, 2, 3):
        raise CoreError(
            "MIGRATION_BACKUP_INVALID", "Unsupported retained backup schema"
        )
    ops, handles, stamps = WindowsHandleOps(), [], []
    _require_local_path(ops, attempt)
    expected = {f"state-v{schema_version}.sqlite3", "backup-receipt.json"}

    def check():
        if {entry.name for entry in attempt.iterdir()} != expected:
            raise CoreError(
                "MIGRATION_BACKUP_CORRUPT", "Unexpected files in the backup attempt"
            )
        for path, handle, before in stamps:
            after = (
                ops.stamp(handle) if before.directory else _retained_stamp(ops, handle)
            )
            if ops.final_path(handle) != path or (
                after.identity != before.identity
                if before.directory
                else after != before
            ):
                raise CoreError(
                    "MIGRATION_BACKUP_CORRUPT", "Retained backup identity changed"
                )

    try:
        for path in (*reversed(attempt.parents), attempt):
            handle = ops.open(path, directory=True)
            handles.append(handle)
            stamp = ops.stamp(handle)
            if not stamp.directory or ops.final_path(handle) != path:
                raise CoreError(
                    "MIGRATION_BACKUP_CORRUPT", "Invalid backup directory identity"
                )
            stamps.append((path, handle, stamp))
        if not os.path.lexists(_receipt_path(attempt)):
            raise CoreError(
                "MIGRATION_BACKUP_INCOMPLETE",
                "Existing attempt has no complete backup receipt; it was not overwritten",
            )
        for name in sorted(expected):
            path = attempt / name
            handle = ops.open(path, directory=False)
            handles.append(handle)
            stamp = _retained_stamp(ops, handle)
            if stamp.directory or ops.final_path(handle) != path:
                raise CoreError(
                    "MIGRATION_BACKUP_CORRUPT", "Invalid backup file identity"
                )
            stamps.append((path, handle, stamp))
        receipt = _read_receipt(
            attempt,
            state,
            operation_id,
            maximum,
            timeout,
            schema_version=schema_version,
        )
        check()
        yield receipt, check
        check()
    finally:
        _close_backup_pins(ops, handles, status)


def _verify_v2_schema(db, tables):
    """Verify actual state layout, not merely user_version and a healthy DB file."""
    from .state import _SCHEMA_V1, _SCHEMA_V2_ADDITIONS

    with closing(sqlite3.connect(":memory:")) as reference:
        reference.executescript(_SCHEMA_V1 + _SCHEMA_V2_ADDITIONS)
        required = {
            row[0]
            for row in reference.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not required <= tables:
            raise CoreError(
                "MIGRATION_BACKUP_CORRUPT", "Backup is missing schema-2 state tables"
            )
        for table in sorted(required):
            # Table identifiers come solely from the trusted constant schema.
            for pragma in ("table_info", "foreign_key_list"):
                sql = f'PRAGMA {pragma}("{table}")'
                if db.execute(sql).fetchall() != reference.execute(sql).fetchall():
                    raise CoreError(
                        "MIGRATION_BACKUP_CORRUPT",
                        "Backup schema-2 columns or relationships differ",
                    )
    if db.execute("SELECT COUNT(*) FROM project_head").fetchone() != (1,) or db.execute(
        "SELECT COUNT(*) FROM source_configuration"
    ).fetchone() != (1,):
        raise CoreError(
            "MIGRATION_BACKUP_CORRUPT",
            "Backup lacks the project head/configuration singleton",
        )
    if db.execute(
        "SELECT COUNT(*) FROM publication_receipts r LEFT JOIN snapshot_events e USING(project_id,operation_id) LEFT JOIN snapshot_outbox o USING(project_id,operation_id) WHERE e.operation_id IS NULL OR o.operation_id IS NULL"
    ).fetchone() != (0,):
        raise CoreError(
            "MIGRATION_BACKUP_CORRUPT", "Backup publication evidence is incomplete"
        )


def _verify_v3_schema(db):
    """Match delivered schema-3 constraints as well as columns and foreign keys.

    Additional application tables are preserved, but required tables cannot
    silently lose CHECK/UNIQUE constraints while retaining a healthy SQLite file.
    Schema versions are exact delivered DDL contracts, not user-editable layouts.
    """
    from .state import _SCHEMA_V1, _SCHEMA_V2_ADDITIONS, _SCHEMA_V3_ADDITIONS

    with closing(sqlite3.connect(":memory:")) as reference:
        reference.executescript(
            _SCHEMA_V1 + _SCHEMA_V2_ADDITIONS + _SCHEMA_V3_ADDITIONS
        )
        required = dict(
            reference.execute("SELECT name,sql FROM sqlite_master WHERE type='table'")
        )
    actual = dict(db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"))
    for table, definition in required.items():
        if table not in actual or " ".join(actual[table].split()) != " ".join(
            definition.split()
        ):
            raise CoreError(
                "MIGRATION_BACKUP_CORRUPT", "Backup schema-3 table definition differs"
            )


def _read_receipt(
    attempt, state, operation_id, maximum, timeout_seconds, *, schema_version=1
):
    if not os.path.lexists(_receipt_path(attempt)):
        raise CoreError(
            "MIGRATION_BACKUP_INCOMPLETE",
            "Existing attempt has no complete backup receipt; it was not overwritten",
        )
    try:
        with pinned_retained(_receipt_path(attempt), 65536) as raw:
            document = json.loads(raw)
            if canonical_bytes(document) != raw:
                raise ValueError("noncanonical receipt")
            receipt = StateBackupReceipt(**document)
        if (
            receipt.operation_id != operation_id
            or receipt.project_id != state.project_id
            or receipt.source_path != str(state.path)
            or receipt.path != str(attempt / f"state-v{schema_version}.sqlite3")
            or type(receipt.schema_version) is not int
            or receipt.schema_version != schema_version
        ):
            raise CoreError(
                "MIGRATION_OPERATION_CONFLICT",
                "Backup receipt does not match this state/operation",
            )
        if (
            not isinstance(receipt.sha256, str)
            or len(receipt.sha256) != 64
            or any(c not in "0123456789abcdef" for c in receipt.sha256)
            or type(receipt.size_bytes) is not int
            or not 0 < receipt.size_bytes <= maximum
            or not isinstance(receipt.actor_id, str)
            or not receipt.actor_id
            or receipt.actor_authority
            not in ("local_os", "verified_token", "local_service")
            or datetime.fromisoformat(receipt.created_at).tzinfo is None
        ):
            raise ValueError("invalid receipt fields")
        if {item.name for item in attempt.iterdir()} != {
            f"state-v{schema_version}.sqlite3",
            "backup-receipt.json",
        }:
            raise CoreError(
                "MIGRATION_BACKUP_CORRUPT", "Unexpected files in the backup attempt"
            )
        _verify_backup(
            Path(receipt.path),
            state,
            maximum,
            timeout_seconds,
            receipt,
            schema_version=schema_version,
        )
        return receipt
    except (OSError, ValueError, TypeError, RecursionError, sqlite3.Error) as exc:
        raise CoreError(
            "MIGRATION_BACKUP_INCOMPLETE",
            "Existing backup attempt is incomplete or invalid; it was not overwritten",
        ) from exc


def _new_backup(
    attempt,
    state,
    principal,
    operation_id,
    maximum,
    timeout_seconds,
    *,
    schema_version=1,
):
    path = attempt / f"state-v{schema_version}.sqlite3"
    with state.transaction(principal) as tx:
        if tx.state_schema_version() != schema_version:
            raise CoreError("MIGRATION_STATE_CHANGED", "Schema changed before backup")
        with path.open("xb"):
            pass
        _sidecars(path)
        with closing(
            sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=0)
        ) as destination:
            backup = {1: tx.backup_v1, 2: tx.backup_v2, 3: tx.backup_v3}[schema_version]
            backup(
                destination, timeout_seconds=timeout_seconds, max_backup_bytes=maximum
            )
            destination.execute("PRAGMA journal_mode=DELETE")
    _boundary("after_backup_copy", state=state, attempt=attempt)
    flush_owned(path)
    digest, size = _verify_backup(
        path, state, maximum, timeout_seconds, schema_version=schema_version
    )
    receipt = StateBackupReceipt(
        operation_id,
        state.project_id,
        str(state.path),
        str(path),
        schema_version,
        digest,
        size,
        datetime.now(timezone.utc).isoformat(),
        principal.id,
        principal.authority,
    )
    _boundary("before_backup_receipt", state=state, attempt=attempt)
    with _receipt_path(attempt).open("xb") as output:
        output.write(canonical_bytes(asdict(receipt)))
    flush_owned(_receipt_path(attempt))
    _boundary("after_backup_receipt", state=state, attempt=attempt)
    return _read_receipt(
        attempt,
        state,
        operation_id,
        maximum,
        timeout_seconds,
        schema_version=schema_version,
    )


def _upgrade(state, principal, receipt, *, existed, attempt, check):
    _boundary("before_migration", state=state, attempt=attempt)
    check()
    returned = False
    try:
        state.migrate_v1_to_v2(principal)
        returned = True
        _boundary("after_migration", state=state, attempt=attempt)
        check()
        confirmed = _version(state, principal)
        if confirmed != 2:
            raise CoreError(
                "MIGRATION_OUTCOME_UNKNOWN", "Expected schema 2 was not confirmed"
            )
    except (Exception, KeyboardInterrupt) as exc:
        # Existing migration checks admin before changing schema. Preserve this
        # known refusal rather than disguising it as a failed reconciliation.
        if (
            not returned
            and isinstance(exc, CoreError)
            and exc.code == "PROJECT_FORBIDDEN"
        ):
            raise
        try:
            observed = _version(state, principal)
        except Exception as read_error:
            raise CoreError(
                "MIGRATION_OUTCOME_UNKNOWN",
                "Cannot confirm state version after migration attempt",
                details={"operation_id": receipt.operation_id},
            ) from read_error
        if observed != 2:
            if isinstance(exc, KeyboardInterrupt):
                raise CoreError(
                    "MIGRATION_INTERRUPTED",
                    "Upgrade interrupted; schema 2 was not confirmed",
                    details={"operation_id": receipt.operation_id},
                ) from exc
            raise
        return StateMigrationResult(
            receipt.operation_id, state.project_id, 2, "reconciled", receipt
        )
    return StateMigrationResult(
        receipt.operation_id,
        state.project_id,
        confirmed,
        "reconciled" if existed else "version_confirmed",
        receipt,
    )


def migrate_project_state(
    state,
    principal,
    *,
    backup_directory,
    operation_id,
    timeout_seconds=30,
    max_backup_bytes=256 * 1024 * 1024,
):
    """Back up schema 1, then reauthorize its existing explicit migration.

    A schema-2 observation confirms current version, not which operation upgraded
    it. Existing incomplete attempts are retained and never overwritten/GC'd.
    Windows pins protect retained backup paths; live source DB uses its existing
    authorized SQLite read transaction, including committed WAL contents.
    """
    validate_operation_id(operation_id)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 300
        or type(max_backup_bytes) is not int
        or not 1 <= max_backup_bytes <= 1024**3
    ):
        raise CoreError("MIGRATION_BACKUP_INVALID", "Invalid migration backup limits")
    current = _version(state, principal)  # No backup filesystem IO before admin.
    if current not in (1, 2):
        raise CoreError(
            "MIGRATION_TARGET_MISMATCH", "This runner upgrades schema 1 to 2 only"
        )
    directory = Path(backup_directory).absolute()
    attempt = directory / operation_id
    # Already-current operations do not create directories or a new backup.
    if current == 2 and not os.path.lexists(attempt):
        return StateMigrationResult(
            operation_id, state.project_id, 2, "already_current", None
        )
    result = None
    status = _BackupPinStatus()
    try:
        with ExitStack() as pins:
            pins.enter_context(_pin_migration_directory(directory.parent, status))
            directory.mkdir(exist_ok=True)
            pins.enter_context(_pin_migration_directory(directory, status))
            existed = os.path.lexists(attempt)
            if not existed:
                attempt.mkdir()
            pins.enter_context(_pin_migration_directory(attempt, status))
            if not existed:
                _new_backup(
                    attempt,
                    state,
                    principal,
                    operation_id,
                    max_backup_bytes,
                    timeout_seconds,
                )
            receipt, check = pins.enter_context(
                _hold_verified_backup(
                    attempt,
                    state,
                    operation_id,
                    max_backup_bytes,
                    timeout_seconds,
                    status,
                    schema_version=1,
                )
            )
            result = _upgrade(
                state, principal, receipt, existed=existed, attempt=attempt, check=check
            )
        return result
    except (Exception, KeyboardInterrupt) as exc:
        if result is not None:
            try:
                if _version(state, principal) != 2:
                    raise CoreError(
                        "MIGRATION_OUTCOME_UNKNOWN", "Schema 2 no longer confirmed"
                    )
            except Exception as error:
                raise CoreError(
                    "MIGRATION_OUTCOME_UNKNOWN",
                    "Cannot confirm version after retained handle closure failed",
                    details={"operation_id": operation_id},
                ) from error
            raise CoreError(
                "MIGRATION_BACKUP_CLEANUP_FAILED"
                if status.cleanup_failed
                else "MIGRATION_BACKUP_CORRUPT",
                "Schema 2 is confirmed, but complete backup verification/cleanup failed",
                details={
                    "operation_id": operation_id,
                    "state_version_confirmed": 2,
                    "migration_attribution": "not_proven",
                },
            ) from exc
        if isinstance(exc, KeyboardInterrupt):
            raise CoreError(
                "MIGRATION_INTERRUPTED",
                "Runner interrupted; reconcile state and any complete backup receipt",
                details={"operation_id": operation_id},
            ) from exc
        raise
