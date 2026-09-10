"""One local SQLite file per project. No source access or ambient connection."""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from . import _sqlite
from .authorization import OWNER_PERMISSIONS, StateTransaction
from .context import Principal, validate_project_id
from .errors import CoreError
from ._workflow_schema import SCHEMA_V4_ADDITIONS

_SCHEMA_V1 = """
PRAGMA user_version=1;
CREATE TABLE project (
    singleton INTEGER PRIMARY KEY CHECK (singleton=1),
    project_id TEXT NOT NULL UNIQUE
);
CREATE TABLE memberships (
    project_id TEXT NOT NULL REFERENCES project(project_id),
    principal_id TEXT NOT NULL,
    authority TEXT NOT NULL,
    PRIMARY KEY (project_id, principal_id, authority)
);
CREATE TABLE membership_permissions (
    project_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,
    authority TEXT NOT NULL,
    permission TEXT NOT NULL CHECK (length(permission)>0),
    PRIMARY KEY (project_id, principal_id, authority, permission),
    FOREIGN KEY (project_id, principal_id, authority)
        REFERENCES memberships(project_id, principal_id, authority) ON DELETE CASCADE
);
"""

_SCHEMA_V2_ADDITIONS = """
CREATE TABLE source_configuration (
  project_id TEXT PRIMARY KEY REFERENCES project(project_id),
  revision INTEGER NOT NULL CHECK(revision >= 1)
);
CREATE TABLE source_layers (
  project_id TEXT NOT NULL REFERENCES source_configuration(project_id),
  layer_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
  kind TEXT NOT NULL CHECK(kind IN ('base','extension')),
  root_relative_path TEXT NOT NULL,
  source_format TEXT NOT NULL CHECK(source_format IN ('designer_xml','edt','unknown')),
  PRIMARY KEY(project_id,layer_id), UNIQUE(project_id,ordinal),
  UNIQUE(project_id,root_relative_path)
);
CREATE TABLE snapshots (
  project_id TEXT NOT NULL REFERENCES project(project_id),
  snapshot_id TEXT NOT NULL CHECK(length(snapshot_id)=64),
  manifest_hash TEXT NOT NULL CHECK(manifest_hash=snapshot_id),
  source_digest TEXT NOT NULL CHECK(length(source_digest)=64),
  graph_hash TEXT NOT NULL CHECK(length(graph_hash)=64),
  generation_relpath TEXT NOT NULL,
  manifest_version INTEGER NOT NULL CHECK(manifest_version=1),
  published_at TEXT NOT NULL,
  PRIMARY KEY(project_id,snapshot_id), UNIQUE(project_id,generation_relpath)
);
CREATE TABLE project_head (
  project_id TEXT PRIMARY KEY REFERENCES project(project_id),
  snapshot_id TEXT,
  revision INTEGER NOT NULL CHECK(revision >= 0),
  FOREIGN KEY(project_id,snapshot_id) REFERENCES snapshots(project_id,snapshot_id)
);
CREATE TABLE snapshot_layers (
  project_id TEXT NOT NULL, snapshot_id TEXT NOT NULL, layer_id TEXT NOT NULL,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
  kind TEXT NOT NULL CHECK(kind IN ('base','extension')),
  configuration_uuid TEXT,
  identity_status TEXT NOT NULL CHECK(identity_status IN ('unresolved','verified')),
  source_format TEXT NOT NULL,
  PRIMARY KEY(project_id,snapshot_id,layer_id),
  UNIQUE(project_id,snapshot_id,ordinal),
  FOREIGN KEY(project_id,snapshot_id) REFERENCES snapshots(project_id,snapshot_id)
);
CREATE TABLE publication_receipts (
  project_id TEXT NOT NULL, operation_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  expected_snapshot_id TEXT, expected_head_revision INTEGER NOT NULL,
  source_revision INTEGER NOT NULL, committed_head_revision INTEGER NOT NULL,
  actor_id TEXT NOT NULL, actor_authority TEXT NOT NULL, committed_at TEXT NOT NULL,
  PRIMARY KEY(project_id,operation_id), UNIQUE(project_id,committed_head_revision),
  FOREIGN KEY(project_id,snapshot_id) REFERENCES snapshots(project_id,snapshot_id)
);
CREATE TABLE snapshot_events (
  project_id TEXT NOT NULL, operation_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind='snapshot.published'),
  payload_json TEXT NOT NULL,
  PRIMARY KEY(project_id,operation_id),
  FOREIGN KEY(project_id,operation_id)
    REFERENCES publication_receipts(project_id,operation_id)
);
CREATE TABLE snapshot_outbox (
  project_id TEXT NOT NULL, operation_id TEXT NOT NULL,
  consumer TEXT NOT NULL CHECK(consumer='source_observer'),
  status TEXT NOT NULL CHECK(status IN ('pending','delivered')),
  PRIMARY KEY(project_id,operation_id,consumer),
  FOREIGN KEY(project_id,operation_id)
    REFERENCES snapshot_events(project_id,operation_id)
);
"""

_SCHEMA_V3_ADDITIONS = """
CREATE TABLE project_action_receipts (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES project(project_id),
  operation_id TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('membership.set','membership.revoke','state.upgraded')),
  action_version INTEGER NOT NULL CHECK(action_version=1),
  actor_id TEXT NOT NULL,
  actor_authority TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  request_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  UNIQUE(project_id,operation_id)
);
"""

_SCHEMA = _SCHEMA_V1 + _SCHEMA_V2_ADDITIONS + _SCHEMA_V3_ADDITIONS + SCHEMA_V4_ADDITIONS


def _initialize_v2(connection, project_id):
    connection.execute("INSERT INTO source_configuration VALUES (?, 1)", (project_id,))
    connection.execute(
        "INSERT INTO source_layers VALUES (?, 'base', 0, 'base', '.', 'unknown')",
        (project_id,),
    )
    connection.execute("INSERT INTO project_head VALUES (?, NULL, 0)", (project_id,))
    connection.execute("PRAGMA user_version=2")


def _access_upgrade_boundary(name, **values):
    """Failure-injection seam; no production side effects."""


@dataclass(frozen=True)
class ProjectState:
    """Trusted handle; instantiate from registry, never from untrusted path input."""

    path: Path
    project_id: str

    def __post_init__(self):
        validate_project_id(self.project_id)
        object.__setattr__(self, "path", Path(self.path).absolute())

    @classmethod
    def create(cls, path: Path, project_id: str, owner: Principal) -> "ProjectState":
        """Bootstrap a new explicit file; no attach, overwrite or migration."""
        state = cls(path, project_id)
        with _sqlite.create_database(state.path, _SCHEMA) as connection:
            connection.execute("INSERT INTO project VALUES (1, ?)", (project_id,))
            identity = (project_id, owner.id, owner.authority)
            connection.execute("INSERT INTO memberships VALUES (?, ?, ?)", identity)
            connection.executemany(
                "INSERT INTO membership_permissions VALUES (?, ?, ?, ?)",
                [(*identity, p) for p in sorted(OWNER_PERMISSIONS)],
            )
            _initialize_v2(connection, project_id)
            connection.execute("PRAGMA user_version=4")
        return state

    def migrate_v1_to_v2(self, principal: Principal) -> None:
        """Explicit trusted upgrade; caller handles backup before invoking this method."""
        with _sqlite.transaction(self.path, write=True) as connection:
            version = self._check_identity(connection)
            tx = StateTransaction(connection, self.project_id, principal, True)
            try:
                tx.require_all({"project:admin"})
                if version == 2:
                    return
                if version != 1:
                    raise CoreError(
                        "MIGRATION_TARGET_MISMATCH",
                        "This upgrade targets schema 2 only",
                    )
                for statement in _SCHEMA_V2_ADDITIONS.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                _initialize_v2(connection, self.project_id)
            finally:
                tx._closed = True

    def _check_identity(self, connection):
        row = connection.execute(
            "SELECT project_id FROM project WHERE singleton=1"
        ).fetchone()
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if row != (self.project_id,) or version not in (1, 2, 3, 4):
            raise CoreError(
                "PROJECT_STATE_MISMATCH", "State identity or schema does not match"
            )
        return version

    def migrate_v2_to_v3(self, principal, *, operation_id, backup):
        """Trusted state-only upgrade after the runner verifies/flushes backup bytes.

        Returns the exact action receipt after commit, or None if another
        operation/fresh bootstrap already supplied schema3. No filesystem IO.
        """
        from .access import upgrade_request

        with self.transaction(principal, write=True) as tx:
            tx.require_all({"project:admin"})
            request = upgrade_request(
                principal, backup, project_id=self.project_id, operation_id=operation_id
            )
            version = tx.state_schema_version()
            if version == 3:
                found = tx._find_action(operation_id)
                if found is None:
                    return None
                if found[0] != request:
                    raise CoreError(
                        "OPERATION_CONFLICT", "Upgrade operation has different inputs"
                    )
                return found[1]
            if version != 2:
                raise CoreError(
                    "MIGRATION_TARGET_MISMATCH", "Access upgrade requires schema 2"
                )
            for statement in _SCHEMA_V3_ADDITIONS.split(";"):
                if statement.strip():
                    tx._connection.execute(statement)
            _access_upgrade_boundary("after_ddl", state=self)
            tx._connection.execute("PRAGMA user_version=3")
            _access_upgrade_boundary("after_version", state=self)
            receipt = tx._record_action(
                operation_id,
                request,
                {
                    "outcome": "committed",
                    "source_schema": 2,
                    "state_version_confirmed": 3,
                    "backup": backup,
                    "migration_attribution": "operation_receipt",
                },
            )
            _access_upgrade_boundary("after_receipt", state=self)
        return receipt

    def migrate_v3_to_v4(self, principal, *, operation_id, backup):
        """Trusted state-only step after the workflow runner verifies its backup."""
        from .workflow_migration import migrate_state

        return migrate_state(self, principal, operation_id=operation_id, backup=backup)

    @contextmanager
    def transaction(self, principal: Principal, *, write: bool = False):
        """Check current membership, commit on success, roll back/close on all exits.

        Write locks serialize permission checking and membership changes. Keep
        use cases short; never do parsing or external effects inside this scope.
        """
        with _sqlite.transaction(self.path, write=write) as connection:
            self._check_identity(connection)
            tx = StateTransaction(
                connection, self.project_id, principal, write, self.path.parent
            )
            try:
                tx.require_all({"project:read"})
                yield tx
            finally:
                tx._closed = True
