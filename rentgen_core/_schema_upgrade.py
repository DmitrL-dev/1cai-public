"""One retained-backup/receipt protocol for explicit state schema upgrades.

The step is trusted application code; callers cannot choose it through JSON.
Authorization and receipt decoding stay with the specific versioned upgrade.
"""
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import math
import os
from pathlib import Path
from typing import Callable

from .errors import CoreError
from .snapshots import validate_operation_id
from .state_migration import (
    _new_backup,
    _BackupPinStatus,
    _hold_verified_backup,
    _pin_migration_directory,
)


@dataclass(frozen=True)
class ReceiptUpgrade:
    source_schema: int
    target_schema: int
    observe: Callable
    migrate: Callable
    boundary: Callable


def _result(step, state, operation_id, outcome, receipt=None, backup=None):
    return {
        "project_id": state.project_id,
        "operation_id": operation_id,
        "state_version_confirmed": step.target_schema,
        "outcome": outcome,
        "receipt": receipt,
        "backup": None if backup is None else asdict(backup),
        "migration_attribution": "operation_receipt" if receipt else "not_proven",
    }


def _verified_committed(
    step, state, principal, operation_id, attempt, receipt, maximum, timeout
):
    # Receipt proves schema commit. A subsequent artifact failure cannot undo it.
    try:
        status = _BackupPinStatus()
        with _hold_verified_backup(
            attempt,
            state,
            operation_id,
            maximum,
            timeout,
            status,
            schema_version=step.source_schema,
        ) as (backup, check):
            if asdict(backup) != receipt["backup"]:
                raise CoreError(
                    "MIGRATION_OPERATION_CONFLICT",
                    "Retained backup differs from the committed binding",
                )
            try:
                version, confirmed = step.observe(state, principal, operation_id)
                if version != step.target_schema or confirmed != receipt:
                    raise CoreError(
                        "STATE_CORRUPT", "Previously observed action receipt changed"
                    )
            except (Exception, KeyboardInterrupt) as exc:
                if isinstance(exc, CoreError) and exc.code == "PROJECT_FORBIDDEN":
                    raise
                raise CoreError(
                    "MIGRATION_OUTCOME_UNKNOWN",
                    "Schema commit was observed, but final state reconciliation is unavailable",
                    details={
                        "operation_id": operation_id,
                        "migration_committed": True,
                        "state_version_confirmed": step.target_schema,
                    },
                ) from exc
            check()
    except (Exception, KeyboardInterrupt) as exc:
        if isinstance(exc, CoreError) and exc.code in {
            "PROJECT_FORBIDDEN",
            "MIGRATION_OUTCOME_UNKNOWN",
        }:
            raise
        raise CoreError(
            "MIGRATION_COMMITTED_BACKUP_INVALID",
            "Schema upgrade committed, but its complete backup cannot be verified",
            details={
                "operation_id": operation_id,
                "migration_committed": True,
                "state_version_confirmed": step.target_schema,
            },
        ) from exc
    return _result(step, state, operation_id, "reconciled", receipt, backup)


def upgrade_receipted_state(
    state,
    principal,
    *,
    step,
    backup_directory,
    operation_id,
    timeout_seconds=30,
    max_backup_bytes=256 * 1024 * 1024,
):
    if type(step) is not ReceiptUpgrade or (
        step.source_schema,
        step.target_schema,
    ) not in {(2, 3), (3, 4)}:
        raise CoreError("MIGRATION_TARGET_MISMATCH", "Unsupported receipt upgrade step")
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
    version, committed = step.observe(
        state, principal, operation_id
    )  # Before backup IO.
    directory = Path(backup_directory).absolute()
    attempt = directory / operation_id
    if version == step.target_schema:
        return (
            _result(step, state, operation_id, "already_current")
            if committed is None
            else _verified_committed(
                step,
                state,
                principal,
                operation_id,
                attempt,
                committed,
                max_backup_bytes,
                timeout_seconds,
            )
        )
    attempted = False
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
                    schema_version=step.source_schema,
                )
            backup, check = pins.enter_context(
                _hold_verified_backup(
                    attempt,
                    state,
                    operation_id,
                    max_backup_bytes,
                    timeout_seconds,
                    status,
                    schema_version=step.source_schema,
                )
            )
            step.boundary("after_complete_backup", state=state, attempt=attempt)
            step.boundary("before_migration", state=state, attempt=attempt)
            check()
            attempted = True
            receipt = step.migrate(
                principal, operation_id=operation_id, backup=asdict(backup)
            )
            step.boundary("after_commit", state=state, attempt=attempt)
            check()
            observed, confirmed = step.observe(state, principal, operation_id)
            if receipt is not None and (
                observed != step.target_schema or confirmed != receipt
            ):
                raise CoreError(
                    "MIGRATION_OUTCOME_UNKNOWN",
                    "Exact schema upgrade receipt was not confirmed",
                )
            result = (
                _result(step, state, operation_id, "already_current")
                if receipt is None
                else _result(step, state, operation_id, "committed", receipt, backup)
            )
        return result
    except (Exception, KeyboardInterrupt) as exc:
        if not attempted:
            if isinstance(exc, KeyboardInterrupt):
                raise CoreError(
                    "MIGRATION_INTERRUPTED",
                    "Backup/upgrade interrupted before schema commit",
                    details={"operation_id": operation_id},
                ) from exc
            raise
        if isinstance(exc, CoreError) and exc.code in {
            "PROJECT_FORBIDDEN",
            "OPERATION_CONFLICT",
        }:
            raise
        try:
            observed, committed = step.observe(state, principal, operation_id)
        except Exception as read_error:
            raise CoreError(
                "MIGRATION_OUTCOME_UNKNOWN",
                "Cannot reconcile the schema upgrade operation",
                details={"operation_id": operation_id},
            ) from read_error
        if committed is not None:
            if status.cleanup_failed:
                raise CoreError(
                    "MIGRATION_COMMITTED_BACKUP_INVALID",
                    "Schema upgrade committed, but backup pin cleanup was not confirmed",
                    details={
                        "operation_id": operation_id,
                        "migration_committed": True,
                        "state_version_confirmed": step.target_schema,
                    },
                ) from exc
            return _verified_committed(
                step,
                state,
                principal,
                operation_id,
                attempt,
                committed,
                max_backup_bytes,
                timeout_seconds,
            )
        if observed == step.target_schema:
            if status.cleanup_failed:
                raise CoreError(
                    "MIGRATION_BACKUP_CLEANUP_FAILED",
                    "Backup pin cleanup could not be confirmed",
                ) from exc
            return _result(step, state, operation_id, "already_current")
        if isinstance(exc, KeyboardInterrupt):
            raise CoreError(
                "MIGRATION_INTERRUPTED",
                "Schema upgrade has no confirmed commit",
                details={"operation_id": operation_id},
            ) from exc
        raise
