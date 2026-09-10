"""Verified schema2 backup followed by an exact-operation schema3 commit."""
from .access import principal_value
from .errors import CoreError
from ._schema_upgrade import ReceiptUpgrade, upgrade_receipted_state


def _boundary(name, **values):
    """Failure-injection seam; production has no side effects."""


def _observe(state, principal, operation_id):
    with state.transaction(principal) as tx:
        version = tx.state_schema_version()
        if version not in (2, 3):
            raise CoreError(
                "MIGRATION_TARGET_MISMATCH", "Access upgrade requires schema 2 or 3"
            )
        found = tx._find_action(operation_id) if version == 3 else None
        if found is not None and (
            found[1]["action"] != "state.upgraded"
            or found[1]["actor"] != principal_value(principal)
        ):
            raise CoreError(
                "OPERATION_CONFLICT", "Operation belongs to another action or actor"
            )
        return version, None if found is None else found[1]


def upgrade_project_access(
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
        step=ReceiptUpgrade(2, 3, _observe, state.migrate_v2_to_v3, _boundary),
        backup_directory=backup_directory,
        operation_id=operation_id,
        timeout_seconds=timeout_seconds,
        max_backup_bytes=max_backup_bytes,
    )
