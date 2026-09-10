"""TEST USE ONLY: explicit fixture access, excluded from wheel/sdist packaging.

Normal fixtures use audited operations. force_legacy_membership is restricted to
deliberately invalid/legacy state in authorization and migration failure probes;
it is never an application API, bootstrap adapter or substitute for admin grants.
"""
from uuid import uuid4


def grant_membership(tx, principal, permissions):
    return tx.set_membership(
        principal,
        permissions,
        operation_id=str(uuid4()),
        expected_revision=tx.membership_revision(),
    )


def revoke_membership(tx, principal):
    return tx.revoke_membership(
        principal, operation_id=str(uuid4()), expected_revision=tx.membership_revision()
    )


def force_legacy_membership(tx, principal, permissions):
    """Inject a legacy/invalid permission state for an explicit negative test."""
    tx._require_admin_write()
    identity = (tx._project_id, principal.id, principal.authority)
    tx._connection.execute("INSERT OR IGNORE INTO memberships VALUES (?,?,?)", identity)
    tx._connection.execute(
        "DELETE FROM membership_permissions WHERE project_id=? AND principal_id=? AND authority=?",
        identity,
    )
    tx._connection.executemany(
        "INSERT INTO membership_permissions VALUES (?,?,?,?)",
        [(*identity, p) for p in sorted(permissions)],
    )


def create_legacy_v2_state(path, project_id, owner):
    """Reserve a NEW genuine schema2 fixture; never downgrade existing state."""
    from rentgen_core import ProjectState, _sqlite
    from rentgen_core.authorization import OWNER_PERMISSIONS
    from rentgen_core.state import _SCHEMA_V1, _SCHEMA_V2_ADDITIONS, _initialize_v2

    state = ProjectState(path, project_id)
    with _sqlite.create_database(state.path, _SCHEMA_V1 + _SCHEMA_V2_ADDITIONS) as db:
        db.execute("INSERT INTO project VALUES (1,?)", (project_id,))
        identity = (project_id, owner.id, owner.authority)
        db.execute("INSERT INTO memberships VALUES (?,?,?)", identity)
        db.executemany(
            "INSERT INTO membership_permissions VALUES (?,?,?,?)",
            [(*identity, p) for p in OWNER_PERMISSIONS],
        )
        _initialize_v2(db, project_id)
    return state
