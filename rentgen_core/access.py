"""Strict administrative action values; actor is supplied by trusted composition."""

from dataclasses import asdict
from datetime import datetime
import json

from .context import Principal
from .errors import CoreError
from .snapshots import validate_operation_id


def principal_value(value):
    if not isinstance(value, Principal):
        raise CoreError("MEMBERSHIP_INVALID", "A typed target principal is required")
    try:
        valid = len(value.id.encode("utf-8")) <= 4096 and not any(
            ord(c) < 32 or ord(c) == 127 for c in value.id
        )
    except UnicodeError:
        valid = False
    if not valid:
        raise CoreError("MEMBERSHIP_INVALID", "Principal ID is invalid or too long")
    return asdict(value)


def permission_values(values, *, require_read=False):
    from .authorization import OWNER_PERMISSIONS

    if (
        not isinstance(values, (list, tuple, set, frozenset))
        or any(not isinstance(p, str) for p in values)
        or len(values) != len(set(values))
        or not set(values) <= OWNER_PERMISSIONS
        or (require_read and "project:read" not in values)
    ):
        raise CoreError(
            "MEMBERSHIP_INVALID",
            "Expected distinct known project permissions including project:read for set",
        )
    return sorted(values)


def revision_value(value):
    if type(value) is not int or not 0 <= value < 2**63 - 1:
        raise CoreError("MEMBERSHIP_INVALID", "Expected a bounded access revision")
    return value


def membership_request(
    actor, target, permissions, action, operation_id, expected_revision
):
    if operation_id is None or expected_revision is None:
        raise CoreError(
            "MEMBERSHIP_OPERATION_REQUIRED",
            "Original operation ID and expected revision are required",
        )
    validate_operation_id(operation_id)
    if action not in {"membership.set", "membership.revoke"}:
        raise CoreError("MEMBERSHIP_INVALID", "Unknown membership action")
    return {
        "action": action,
        "actor": principal_value(actor),
        "target": principal_value(target),
        "permissions": permission_values(permissions, require_read=True)
        if action == "membership.set"
        else None,
        "expected_revision": revision_value(expected_revision),
    }


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _boundary(name, **values):
    """Failure-injection seam; no production side effects."""


def change_membership(
    state, actor, *, target, permissions=None, action, operation_id, expected_revision
):
    """Commit one audited change or reconcile its original exact operation.

    Request metadata remains unchanged across retries. A returned receipt describes
    that historical operation, not necessarily the target's current access.
    """
    request = membership_request(
        actor, target, permissions, action, operation_id, expected_revision
    )
    _boundary("before_state_transaction", state=state, operation_id=operation_id)
    try:
        with state.transaction(actor, write=True) as tx:
            result = tx._change_membership(
                target, permissions, action, operation_id, expected_revision
            )
            _boundary("before_commit", state=state, operation_id=operation_id)
        _boundary("after_commit", state=state, operation_id=operation_id)
        return result
    except (Exception, KeyboardInterrupt) as exc:
        if isinstance(exc, CoreError) and exc.code in {
            "PROJECT_FORBIDDEN",
            "MEMBERSHIP_SCHEMA_REQUIRED",
            "MEMBERSHIP_CONFLICT",
            "MEMBERSHIP_SELF_LOCKOUT",
            "MEMBERSHIP_LAST_ADMIN",
            "MEMBERSHIP_LAST_LOCAL_ADMIN",
            "MEMBERSHIP_INVALID",
            "OPERATION_CONFLICT",
            "STATE_CORRUPT",
        }:
            raise
        try:
            with state.transaction(actor) as tx:
                found = tx._find_action(operation_id)
        except Exception as read_error:
            raise CoreError(
                "MEMBERSHIP_OUTCOME_UNKNOWN",
                "Cannot reconcile the original membership operation",
                details={"operation_id": operation_id},
            ) from read_error
        if found is not None:
            if found[0] != request:
                raise CoreError(
                    "OPERATION_CONFLICT",
                    "Operation is bound to different administrative inputs",
                ) from exc
            return found[1]
        if isinstance(exc, KeyboardInterrupt):
            raise CoreError(
                "OPERATION_INTERRUPTED",
                "No membership commit receipt was confirmed; retain the original operation and revision",
                details={"operation_id": operation_id},
            ) from exc
        raise


def backup_binding(backup, *, project_id, operation_id, schema_version):
    from .state_migration import StateBackupReceipt
    from .context import validate_project_id

    try:
        validate_operation_id(operation_id)
        validate_project_id(project_id)
        receipt = StateBackupReceipt(**backup)
        if (
            receipt.project_id != project_id
            or receipt.operation_id != operation_id
            or type(receipt.schema_version) is not int
            or receipt.schema_version != schema_version
            or type(receipt.size_bytes) is not int
            or not 0 < receipt.size_bytes <= 1024**3
            or not isinstance(receipt.sha256, str)
            or len(receipt.sha256) != 64
            or any(c not in "0123456789abcdef" for c in receipt.sha256)
            or datetime.fromisoformat(receipt.created_at).tzinfo is None
            or any(
                not isinstance(p, str) or not p or len(p) > 8192
                for p in (receipt.path, receipt.source_path)
            )
        ):
            raise ValueError("backup binding")
        principal_value(Principal(receipt.actor_id, receipt.actor_authority))
    except (TypeError, ValueError, CoreError) as exc:
        raise CoreError(
            "MIGRATION_BACKUP_CORRUPT", "Invalid verified backup binding"
        ) from exc
    return receipt


def upgrade_request(actor, backup, *, project_id, operation_id):
    receipt = backup_binding(
        backup, project_id=project_id, operation_id=operation_id, schema_version=2
    )
    return {
        "action": "state.upgraded",
        "actor": principal_value(actor),
        "from_schema": 2,
        "to_schema": 3,
        "backup": asdict(receipt),
    }


def decode_action(row, project_id):
    """Validate stored metadata before it can be used as success evidence."""
    try:
        (
            sequence,
            operation,
            action,
            version,
            actor_id,
            authority,
            recorded,
            request_raw,
            result_raw,
        ) = row
        validate_operation_id(operation)
        if version != 1 or type(sequence) is not int or not 1 <= sequence < 2**63:
            raise ValueError("version/sequence")
        if any(
            not isinstance(raw, str) or len(raw.encode("utf-8")) > 65536
            for raw in (request_raw, result_raw)
        ):
            raise ValueError("oversized receipt")
        request, result = json.loads(request_raw), json.loads(result_raw)
        if canonical(request) != request_raw or canonical(result) != result_raw:
            raise ValueError("noncanonical receipt")
        if action not in {"membership.set", "membership.revoke", "state.upgraded"}:
            raise ValueError("action")
        actor = principal_value(Principal(actor_id, authority))
        if datetime.fromisoformat(recorded).tzinfo is None:
            raise ValueError("timestamp")
        if action.startswith("membership."):
            if set(request) != {
                "action",
                "actor",
                "target",
                "permissions",
                "expected_revision",
            }:
                raise ValueError("request fields")
            target = Principal(**request["target"])
            expected = membership_request(
                Principal(**actor),
                target,
                request["permissions"],
                action,
                operation,
                request["expected_revision"],
            )
            if request != expected or request["expected_revision"] + 1 != sequence:
                raise ValueError("request binding")
            fields = {
                "project_id",
                "operation_id",
                "action",
                "actor",
                "target",
                "before",
                "after",
                "changed",
                "revision",
                "recorded_at",
                "outcome",
            }
            if set(result) != fields:
                raise ValueError("result fields")
            before = result["before"]
            if before is not None and permission_values(before) != before:
                raise ValueError("previous permissions")
            if (
                result["after"] != request["permissions"]
                or type(result["changed"]) is not bool
                or result["changed"] != (before != result["after"])
            ):
                raise ValueError("change binding")
            if (
                result["target"] != request["target"]
                or result["outcome"] != "committed"
            ):
                raise ValueError("target/outcome")
        else:
            expected = upgrade_request(
                Principal(**actor),
                request["backup"],
                project_id=project_id,
                operation_id=operation,
            )
            if request != expected or sequence != 1:
                raise ValueError("upgrade request binding")
            if set(result) != {
                "project_id",
                "operation_id",
                "action",
                "actor",
                "revision",
                "recorded_at",
                "outcome",
                "source_schema",
                "state_version_confirmed",
                "backup",
                "migration_attribution",
            }:
                raise ValueError("upgrade result fields")
            if (
                result["source_schema"] != 2
                or type(result["source_schema"]) is not int
                or result["state_version_confirmed"] != 3
                or type(result["state_version_confirmed"]) is not int
                or result["backup"] != request["backup"]
                or result["outcome"] != "committed"
                or result["migration_attribution"] != "operation_receipt"
            ):
                raise ValueError("upgrade result binding")
        if type(result.get("revision")) is not int or any(
            result.get(k) != v
            for k, v in {
                "project_id": project_id,
                "operation_id": operation,
                "action": action,
                "actor": actor,
                "revision": sequence,
                "recorded_at": recorded,
            }.items()
        ):
            raise ValueError("row/result binding")
        return request, result
    except (
        CoreError,
        ValueError,
        TypeError,
        KeyError,
        RecursionError,
        UnicodeError,
    ) as exc:
        raise CoreError("STATE_CORRUPT", "Administrative receipt is invalid") from exc
