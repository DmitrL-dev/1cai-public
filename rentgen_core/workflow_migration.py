"""Explicit schema3→4 migration with a separate workflow receipt family."""
from dataclasses import asdict
from datetime import datetime, timezone
import json

from .access import backup_binding, canonical, principal_value
from .context import Principal
from .errors import CoreError
from .snapshots import validate_operation_id
from ._schema_upgrade import ReceiptUpgrade, upgrade_receipted_state
from ._workflow_schema import SCHEMA_V4_ADDITIONS


def _boundary(name, **values):
    """Runner failure-injection seam; no production effects."""


def _state_boundary(name, **values):
    """State transaction failure-injection seam; no production effects."""


def upgrade_request(actor, backup, project_id, operation_id):
    receipt = backup_binding(
        backup, project_id=project_id, operation_id=operation_id, schema_version=3
    )
    return {
        "action": "workflow.state_upgraded",
        "actor": principal_value(actor),
        "from_schema": 3,
        "to_schema": 4,
        "backup": asdict(receipt),
    }


def find_upgrade(tx, operation_id):
    tx.require_all({"project:admin"})
    validate_operation_id(operation_id)
    row = tx._connection.execute(
        "SELECT action,action_version,actor_id,actor_authority,recorded_at,request_json,result_json FROM workflow_receipts WHERE project_id=? AND operation_id=?",
        (tx._project_id, operation_id),
    ).fetchone()
    if row is None:
        return None
    if row[0] != "workflow.state_upgraded":
        raise CoreError(
            "OPERATION_CONFLICT", "Operation belongs to another workflow action"
        )
    try:
        action, version, actor_id, authority, recorded, request_json, result_json = row
        if (
            type(version) is not int
            or version != 1
            or datetime.fromisoformat(recorded).tzinfo is None
        ):
            raise ValueError("receipt metadata")
        if any(
            type(raw) is not str or len(raw.encode("utf-8")) > 65536
            for raw in (request_json, result_json)
        ):
            raise ValueError("receipt bound")
        request, result = json.loads(request_json), json.loads(result_json)
        actor = Principal(actor_id, authority)
        expected_request = upgrade_request(
            actor, request["backup"], tx._project_id, operation_id
        )
        expected_result = {
            "project_id": tx._project_id,
            "operation_id": operation_id,
            "action": action,
            "actor": principal_value(actor),
            "recorded_at": recorded,
            "outcome": "committed",
            "source_schema": 3,
            "state_version_confirmed": 4,
            "backup": expected_request["backup"],
            "migration_attribution": "operation_receipt",
        }
        if (
            request != expected_request
            or result != expected_result
            or canonical(expected_request) != request_json
            or canonical(expected_result) != result_json
        ):
            raise ValueError("receipt binding")
    except (TypeError, ValueError, KeyError, CoreError, RecursionError) as exc:
        raise CoreError("STATE_CORRUPT", "Workflow upgrade receipt is invalid") from exc
    return request, result


def migrate_state(state, principal, *, operation_id, backup):
    """Trusted state-only step; the outer runner owns verified backup pins."""
    with state.transaction(principal, write=True) as tx:
        tx.require_all({"project:admin"})
        request = upgrade_request(principal, backup, state.project_id, operation_id)
        version = tx.state_schema_version()
        if version == 4:
            found = find_upgrade(tx, operation_id)
            if found is None:
                return None
            if found[0] != request:
                raise CoreError(
                    "OPERATION_CONFLICT", "Upgrade operation has different inputs"
                )
            return found[1]
        if version != 3:
            raise CoreError(
                "MIGRATION_TARGET_MISMATCH", "Workflow upgrade requires schema 3"
            )
        for statement in SCHEMA_V4_ADDITIONS.split(";"):
            if statement.strip():
                tx._connection.execute(statement)
        _state_boundary("after_ddl", state=state)
        tx._connection.execute("PRAGMA user_version=4")
        _state_boundary("after_version", state=state)
        recorded = datetime.now(timezone.utc).isoformat()
        result = {
            "project_id": state.project_id,
            "operation_id": operation_id,
            "action": request["action"],
            "actor": principal_value(principal),
            "recorded_at": recorded,
            "outcome": "committed",
            "source_schema": 3,
            "state_version_confirmed": 4,
            "backup": request["backup"],
            "migration_attribution": "operation_receipt",
        }
        tx._connection.execute(
            "INSERT INTO workflow_receipts VALUES (?,?,?,?,?,?,?,?,?)",
            (
                state.project_id,
                operation_id,
                request["action"],
                1,
                principal.id,
                principal.authority,
                recorded,
                canonical(request),
                canonical(result),
            ),
        )
        _state_boundary("after_receipt", state=state)
    return result


def _observe(state, principal, operation_id):
    with state.transaction(principal) as tx:
        version = tx.state_schema_version()
        if version not in (3, 4):
            raise CoreError(
                "MIGRATION_TARGET_MISMATCH", "Workflow upgrade requires schema 3 or 4"
            )
        found = find_upgrade(tx, operation_id) if version == 4 else None
        if found is not None and found[1]["actor"] != principal_value(principal):
            raise CoreError("OPERATION_CONFLICT", "Operation belongs to another actor")
        return version, None if found is None else found[1]


def upgrade_project_workflows(
    state,
    principal,
    *,
    backup_directory,
    operation_id,
    timeout_seconds=30,
    max_backup_bytes=256 * 1024 * 1024,
):
    return upgrade_receipted_state(
        state,
        principal,
        step=ReceiptUpgrade(3, 4, _observe, state.migrate_v3_to_v4, _boundary),
        backup_directory=backup_directory,
        operation_id=operation_id,
        timeout_seconds=timeout_seconds,
        max_backup_bytes=max_backup_bytes,
    )
