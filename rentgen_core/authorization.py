"""Project permissions come from current membership, never request claims."""

from contextlib import contextmanager
from dataclasses import asdict, replace
from pathlib import Path
from datetime import datetime, timezone
import json
import math
import sqlite3
import time

from .errors import CoreError
from .context import Principal, SnapshotRef
from .access import (
    canonical,
    decode_action,
    membership_request,
    permission_values,
    principal_value,
)
from .snapshots import (
    ProjectHead,
    PublishResult,
    SnapshotCatalogEntry,
    SnapshotLayer,
    validate_operation_id,
)
from .source_configuration import (
    SourceConfiguration,
    SourceLayerSpec,
    _revision,
    validate_layer_roots,
)

OWNER_PERMISSIONS = frozenset(
    {
        "project:read",
        "project:admin",
        "analysis:run",
        "source:edit",
        "artifacts:export",
        "approvals:decide",
        "operations:execute",
        "policies:decide",
    }
)


class StateTransaction:
    """Trusted core use-case transaction, valid only inside ProjectState.transaction."""

    def __init__(self, connection, project_id, principal, write, state_root=None):
        self._connection = connection
        self._project_id = project_id
        self._principal = principal
        self._write = write
        self._closed = False
        self._state_root = state_root

    def require_all(self, permissions):
        if self._closed:
            raise CoreError("TRANSACTION_CLOSED", "Unit of work has ended")
        identity = (self._project_id, self._principal.id, self._principal.authority)
        member = self._connection.execute(
            "SELECT 1 FROM memberships WHERE project_id=? AND principal_id=? AND authority=?",
            identity,
        ).fetchone()
        actual = {
            row[0]
            for row in self._connection.execute(
                "SELECT permission FROM membership_permissions "
                "WHERE project_id=? AND principal_id=? AND authority=?",
                identity,
            )
        }
        if not member or not set(permissions).issubset(actual):
            raise CoreError("PROJECT_FORBIDDEN", "Project permissions are insufficient")

    def set_membership(
        self, principal, permissions, *, operation_id=None, expected_revision=None
    ):
        return self._change_membership(
            principal, permissions, "membership.set", operation_id, expected_revision
        )

    def _require_access_schema(self):
        self.require_all({"project:admin"})
        if self.state_schema_version() not in (3, 4):
            raise CoreError(
                "MEMBERSHIP_SCHEMA_REQUIRED",
                "Audited membership changes require schema 3 or 4",
            )

    def membership_revision(self):
        self._require_access_schema()
        return self._connection.execute(
            "SELECT COALESCE(MAX(sequence),0) FROM project_action_receipts WHERE project_id=?",
            (self._project_id,),
        ).fetchone()[0]

    def _member_permissions(self, target):
        identity = (self._project_id, target.id, target.authority)
        if not self._connection.execute(
            "SELECT 1 FROM memberships WHERE project_id=? AND principal_id=? AND authority=?",
            identity,
        ).fetchone():
            return None
        values = [
            row[0]
            for row in self._connection.execute(
                "SELECT permission FROM membership_permissions WHERE project_id=? AND principal_id=? AND authority=? ORDER BY permission",
                identity,
            )
        ]
        try:
            return permission_values(values)
        except CoreError as exc:
            raise CoreError(
                "STATE_CORRUPT", "Stored membership permissions are invalid"
            ) from exc

    def list_memberships(self, *, limit=100, after=None):
        self.require_all({"project:admin"})
        if type(limit) is not int or not 1 <= limit <= 200:
            raise CoreError(
                "MEMBERSHIP_INVALID", "Membership page limit must be 1..200"
            )
        if after is not None:
            principal_value(after)
        query = "SELECT principal_id,authority FROM memberships WHERE project_id=?"
        values = [self._project_id]
        if after is not None:
            query += " AND (authority,principal_id)>(?,?)"
            values.extend((after.authority, after.id))
        rows = self._connection.execute(
            query + " ORDER BY authority,principal_id LIMIT ?", (*values, limit + 1)
        ).fetchall()
        items = []
        for name, authority in rows[:limit]:
            try:
                principal = Principal(name, authority)
                item = principal_value(principal)
            except CoreError as exc:
                raise CoreError(
                    "STATE_CORRUPT", "Stored membership identity is invalid"
                ) from exc
            items.append(
                {"principal": item, "permissions": self._member_permissions(principal)}
            )
        version = self.state_schema_version()
        return {
            "project_id": self._project_id,
            "state_schema_version": version,
            "revision": self.membership_revision() if version in (3, 4) else None,
            "memberships": items,
            "next_after": items[-1]["principal"] if len(rows) > limit else None,
        }

    def _find_action(self, operation_id):
        self._require_access_schema()
        validate_operation_id(operation_id)
        row = self._connection.execute(
            "SELECT sequence,operation_id,action,action_version,actor_id,actor_authority,recorded_at,request_json,result_json FROM project_action_receipts WHERE project_id=? AND operation_id=?",
            (self._project_id, operation_id),
        ).fetchone()
        return None if row is None else decode_action(row, self._project_id)

    def get_membership_receipt(self, operation_id):
        found = self._find_action(operation_id)
        if found is None:
            raise CoreError(
                "MEMBERSHIP_RECEIPT_NOT_FOUND", "No committed membership receipt exists"
            )
        if not found[1]["action"].startswith("membership."):
            raise CoreError("OPERATION_CONFLICT", "Operation belongs to another action")
        return found[1]

    def _record_action(self, operation_id, request, result):
        self._require_admin_write()
        self._require_access_schema()
        actor = principal_value(self._principal)
        recorded = datetime.now(timezone.utc).isoformat()
        sequence = self.membership_revision() + 1
        if sequence >= 2**63:
            raise CoreError(
                "MEMBERSHIP_CONFLICT", "Administrative revision cannot advance"
            )
        result = dict(
            result,
            project_id=self._project_id,
            operation_id=operation_id,
            action=request["action"],
            actor=actor,
            revision=sequence,
            recorded_at=recorded,
        )
        self._connection.execute(
            "INSERT INTO project_action_receipts VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                sequence,
                self._project_id,
                operation_id,
                request["action"],
                1,
                self._principal.id,
                self._principal.authority,
                recorded,
                canonical(request),
                canonical(result),
            ),
        )
        return result

    def _protect_administrators(self, target, before, after):
        effective = {"project:read", "project:admin"}
        loses_admin = effective <= set(before or ()) and not effective <= set(
            after or ()
        )
        if target == self._principal and loses_admin:
            raise CoreError(
                "MEMBERSHIP_SELF_LOCKOUT",
                "An administrator cannot remove its own access",
            )
        if not loses_admin:
            return
        admins = self._connection.execute(
            "SELECT authority,principal_id FROM membership_permissions WHERE project_id=? AND permission IN ('project:read','project:admin') GROUP BY authority,principal_id HAVING COUNT(*)=2",
            (self._project_id,),
        ).fetchall()
        if len(admins) <= 1:
            raise CoreError(
                "MEMBERSHIP_LAST_ADMIN",
                "At least one effective administrator must remain",
            )
        if (
            target.authority == "local_os"
            and sum(a == "local_os" for a, _ in admins) <= 1
        ):
            raise CoreError(
                "MEMBERSHIP_LAST_LOCAL_ADMIN",
                "At least one existing local administrator must remain",
            )

    def _change_membership(
        self, target, permissions, action, operation_id, expected_revision
    ):
        self._require_admin_write()
        self._require_access_schema()
        request = membership_request(
            self._principal,
            target,
            permissions,
            action,
            operation_id,
            expected_revision,
        )
        found = self._find_action(operation_id)
        if found is not None:
            if found[0] != request:
                raise CoreError(
                    "OPERATION_CONFLICT",
                    "Operation is bound to different administrative inputs",
                )
            return found[1]
        if self.membership_revision() != expected_revision:
            raise CoreError("MEMBERSHIP_CONFLICT", "Project access changed")
        before, after = self._member_permissions(target), request["permissions"]
        self._protect_administrators(target, before, after)
        identity = (self._project_id, target.id, target.authority)
        with self._atomic_operation():
            if after is None:
                self._connection.execute(
                    "DELETE FROM memberships WHERE project_id=? AND principal_id=? AND authority=?",
                    identity,
                )
            else:
                self._connection.execute(
                    "INSERT OR IGNORE INTO memberships VALUES (?,?,?)", identity
                )
                self._connection.execute(
                    "DELETE FROM membership_permissions WHERE project_id=? AND principal_id=? AND authority=?",
                    identity,
                )
                self._connection.executemany(
                    "INSERT INTO membership_permissions VALUES (?,?,?,?)",
                    [(*identity, p) for p in after],
                )
            return self._record_action(
                operation_id,
                request,
                {
                    "target": request["target"],
                    "before": before,
                    "after": after,
                    "changed": before != after,
                    "outcome": "committed",
                },
            )

    def state_schema_version(self) -> int:
        """Administrative state inspection, including a pre-snapshot schema 1."""
        self.require_all({"project:admin"})
        return self._connection.execute("PRAGMA user_version").fetchone()[0]

    def backup_v1(
        self,
        target,
        *,
        timeout_seconds=30,
        max_backup_bytes=256 * 1024 * 1024,
        pages=64,
    ):
        return self._backup_schema(
            target,
            schema_version=1,
            timeout_seconds=timeout_seconds,
            max_backup_bytes=max_backup_bytes,
            pages=pages,
        )

    def backup_v2(
        self,
        target,
        *,
        timeout_seconds=30,
        max_backup_bytes=256 * 1024 * 1024,
        pages=64,
    ):
        return self._backup_schema(
            target,
            schema_version=2,
            timeout_seconds=timeout_seconds,
            max_backup_bytes=max_backup_bytes,
            pages=pages,
        )

    def backup_v3(
        self,
        target,
        *,
        timeout_seconds=30,
        max_backup_bytes=256 * 1024 * 1024,
        pages=64,
    ):
        return self._backup_schema(
            target,
            schema_version=3,
            timeout_seconds=timeout_seconds,
            max_backup_bytes=max_backup_bytes,
            pages=pages,
        )

    def _backup_schema(
        self,
        target,
        *,
        schema_version,
        timeout_seconds=30,
        max_backup_bytes=256 * 1024 * 1024,
        pages=64,
    ):
        """Copy this authorized version-checked READ snapshot into an owned target.

        Narrow exception to short read UOWs: a consistent WAL-safe backup keeps
        this read transaction alive. No source connection leaves this method.
        The caller owns target creation/closure, validation and durable receipt.
        Deadline checks are cooperative between bounded SQLite backup steps.
        """
        version = self.state_schema_version()  # Always repeat the admin check.
        if (
            self._write
            or target is self._connection
            or not isinstance(target, sqlite3.Connection)
        ):
            raise CoreError(
                "MIGRATION_BACKUP_INVALID",
                "Backup requires a read UOW and a separate SQLite target",
            )
        if version != schema_version:
            raise CoreError("MIGRATION_STATE_CHANGED", "Backup source schema changed")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 300
            or type(max_backup_bytes) is not int
            or not 1 <= max_backup_bytes <= 1024**3
            or type(pages) is not int
            or not 1 <= pages <= 256
        ):
            raise CoreError("MIGRATION_BACKUP_INVALID", "Invalid backup limits")
        page_size = self._connection.execute("PRAGMA page_size").fetchone()[0]
        page_count = self._connection.execute("PRAGMA page_count").fetchone()[0]
        if page_count * page_size > max_backup_bytes:
            raise CoreError(
                "MIGRATION_BACKUP_LIMIT", "State exceeds the backup byte limit"
            )
        deadline = time.monotonic() + timeout_seconds

        def progress(status, remaining, total):
            if time.monotonic() >= deadline:
                raise CoreError(
                    "MIGRATION_BACKUP_TIMEOUT", "SQLite backup deadline exceeded"
                )
            if total * page_size > max_backup_bytes:
                raise CoreError(
                    "MIGRATION_BACKUP_LIMIT", "State exceeds the backup byte limit"
                )

        self._connection.backup(
            target, pages=pages, progress=progress, sleep=min(0.01, timeout_seconds)
        )
        return {"page_size": page_size, "page_count": page_count}

    def _require_snapshot_schema(self):
        self.require_all({"project:read"})
        if self._connection.execute("PRAGMA user_version").fetchone()[0] not in (
            2,
            3,
            4,
        ):
            raise CoreError(
                "PROJECT_STATE_MISMATCH", "Snapshot state requires schema 2, 3 or 4"
            )

    def get_source_configuration(self) -> SourceConfiguration:
        self._require_snapshot_schema()
        revision = self._connection.execute(
            "SELECT revision FROM source_configuration WHERE project_id=?",
            (self._project_id,),
        ).fetchone()[0]
        layers = self._connection.execute(
            "SELECT layer_id,ordinal,kind,root_relative_path,source_format "
            "FROM source_layers WHERE project_id=? ORDER BY ordinal",
            (self._project_id,),
        ).fetchall()
        return SourceConfiguration(
            revision, tuple(SourceLayerSpec(*row) for row in layers)
        )

    def get_project_head(self) -> ProjectHead:
        self._require_snapshot_schema()
        row = self._connection.execute(
            "SELECT h.revision,h.snapshot_id,c.revision FROM project_head h "
            "JOIN source_configuration c USING(project_id) WHERE h.project_id=?",
            (self._project_id,),
        ).fetchone()
        snapshot = (
            None if row[1] is None else SnapshotRef(self._project_id, row[1], row[1])
        )
        return ProjectHead(self._project_id, row[0], snapshot, row[2])

    def configure_source_layers(
        self,
        layers: tuple[SourceLayerSpec, ...],
        *,
        expected_revision: int,
        source_root: Path,
    ) -> SourceConfiguration:
        self._require_admin_write()
        self._require_snapshot_schema()
        _revision(expected_revision)
        current = self.get_source_configuration()
        if current.revision != expected_revision:
            raise CoreError(
                "SOURCE_CONFIGURATION_CONFLICT", "Source configuration changed"
            )
        result = SourceConfiguration(expected_revision + 1, layers)
        validate_layer_roots(layers, source_root, self._state_root)
        with self._atomic_operation():
            updated = self._connection.execute(
                "UPDATE source_configuration SET revision=revision+1 "
                "WHERE project_id=? AND revision=?",
                (self._project_id, expected_revision),
            )
            if updated.rowcount != 1:
                raise CoreError(
                    "SOURCE_CONFIGURATION_CONFLICT", "Source configuration changed"
                )
            self._connection.execute(
                "DELETE FROM source_layers WHERE project_id=?", (self._project_id,)
            )
            self._connection.executemany(
                "INSERT INTO source_layers VALUES (?,?,?,?,?,?)",
                [
                    (
                        self._project_id,
                        layer.layer_id,
                        layer.ordinal,
                        layer.kind,
                        layer.root_relative_path,
                        layer.source_format,
                    )
                    for layer in layers
                ],
            )
        return result

    def get_snapshot(self, snapshot_id: str) -> SnapshotCatalogEntry:
        self._require_snapshot_schema()
        ref = SnapshotRef(self._project_id, snapshot_id, snapshot_id)
        row = self._connection.execute(
            "SELECT manifest_hash,source_digest,graph_hash,generation_relpath,manifest_version,published_at "
            "FROM snapshots WHERE project_id=? AND snapshot_id=?",
            (self._project_id, snapshot_id),
        ).fetchone()
        if row is None:
            raise CoreError(
                "SNAPSHOT_NOT_FOUND", "Snapshot is not published in this project"
            )
        if row[0] != ref.manifest_hash:
            raise CoreError("SNAPSHOT_CORRUPT", "Catalog manifest binding is invalid")
        return SnapshotCatalogEntry(ref, *row[1:])

    def get_snapshot_layers(self, snapshot_id: str) -> tuple[SnapshotLayer, ...]:
        self._require_snapshot_schema()
        self.get_snapshot(snapshot_id)
        rows = self._connection.execute(
            "SELECT layer_id,ordinal,kind,configuration_uuid,identity_status,source_format "
            "FROM snapshot_layers WHERE project_id=? AND snapshot_id=? ORDER BY ordinal",
            (self._project_id, snapshot_id),
        ).fetchall()
        return tuple(SnapshotLayer(*row) for row in rows)

    def _find_publication(self, operation_id):
        self._require_snapshot_schema()
        validate_operation_id(operation_id)
        row = self._connection.execute(
            "SELECT snapshot_id,expected_snapshot_id,expected_head_revision,source_revision,committed_head_revision "
            "FROM publication_receipts WHERE project_id=? AND operation_id=?",
            (self._project_id, operation_id),
        ).fetchone()
        if row is None:
            return None
        snapshot = SnapshotRef(self._project_id, row[0], row[0])
        previous = (
            None if row[1] is None else SnapshotRef(self._project_id, row[1], row[1])
        )
        expected = ProjectHead(self._project_id, row[2], previous, row[3])
        result = PublishResult(
            operation_id,
            snapshot,
            ProjectHead(self._project_id, row[4], snapshot, row[3]),
            "committed",
        )
        return result, expected

    def get_publication(self, operation_id: str) -> PublishResult:
        self._require_snapshot_schema()
        found = self._find_publication(operation_id)
        if found is None:
            raise CoreError(
                "PUBLICATION_NOT_FOUND",
                "No committed receipt exists for this operation",
            )
        return found[0]

    def commit_publication(
        self,
        *,
        expected_head: ProjectHead,
        catalog: SnapshotCatalogEntry,
        layers: tuple[SnapshotLayer, ...],
        operation_id: str,
    ) -> PublishResult:
        """State-only seam for trusted orchestration AFTER validating/renaming files.

        This method performs no capture, graph build, filesystem verification or
        source/graph capability construction. Every mutation shares this unit of
        work. A savepoint prevents partial publication if a caller catches errors.
        The returned result is durable only after the outer unit of work commits.
        """
        self.require_all({"analysis:run"})
        if not self._write:
            raise CoreError("READ_ONLY_TRANSACTION", "A write unit of work is required")
        self._require_snapshot_schema()
        validate_operation_id(operation_id)
        if not isinstance(expected_head, ProjectHead) or not isinstance(
            catalog, SnapshotCatalogEntry
        ):
            raise CoreError("HEAD_CONFLICT", "Typed publication inputs are required")
        if (
            expected_head.project_id != self._project_id
            or catalog.snapshot.project_id != self._project_id
        ):
            raise CoreError(
                "CONTEXT_PROJECT_MISMATCH", "Publication belongs to another project"
            )
        if (
            not isinstance(layers, tuple)
            or not layers
            or any(
                not isinstance(layer, SnapshotLayer)
                or layer.ordinal != ordinal
                or layer.kind != ("base" if ordinal == 0 else "extension")
                for ordinal, layer in enumerate(layers)
            )
            or len({layer.layer_id for layer in layers}) != len(layers)
        ):
            raise CoreError("SOURCE_LAYER_INVALID", "Invalid snapshot layers")
        found = self._find_publication(operation_id)
        if found is not None:
            if found[1] != expected_head or found[0].snapshot != catalog.snapshot:
                raise CoreError(
                    "OPERATION_CONFLICT",
                    "Operation is already bound to different inputs",
                )
            old = self.get_snapshot(catalog.snapshot.snapshot_id)
            if (
                replace(catalog, published_at=old.published_at) != old
                or self.get_snapshot_layers(catalog.snapshot.snapshot_id) != layers
            ):
                raise CoreError(
                    "OPERATION_CONFLICT", "Operation content binding does not match"
                )
            return found[0]
        current = self.get_project_head()
        if current.source_revision != expected_head.source_revision:
            raise CoreError(
                "SOURCE_CONFIGURATION_CONFLICT", "Source configuration changed"
            )
        if current != expected_head or current.revision == 2**63 - 1:
            raise CoreError("HEAD_CONFLICT", "Project head changed or cannot advance")
        configured = self.get_source_configuration().layers
        if tuple(
            (v.layer_id, v.ordinal, v.kind, v.source_format) for v in layers
        ) != tuple(
            (v.layer_id, v.ordinal, v.kind, v.source_format) for v in configured
        ):
            raise CoreError(
                "SOURCE_CONFIGURATION_CONFLICT",
                "Snapshot layers do not match configuration",
            )
        with self._atomic_operation():
            self._insert_catalog(catalog, layers)
            updated = self._connection.execute(
                "UPDATE project_head SET snapshot_id=?,revision=revision+1 "
                "WHERE project_id=? AND revision=? AND snapshot_id IS ?",
                (
                    catalog.snapshot.snapshot_id,
                    self._project_id,
                    expected_head.revision,
                    None
                    if expected_head.snapshot is None
                    else expected_head.snapshot.snapshot_id,
                ),
            )
            if updated.rowcount != 1:
                raise CoreError("HEAD_CONFLICT", "Project head changed")
            result = PublishResult(
                operation_id, catalog.snapshot, self.get_project_head(), "committed"
            )
            self._connection.execute(
                "INSERT INTO publication_receipts VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    self._project_id,
                    operation_id,
                    catalog.snapshot.snapshot_id,
                    None
                    if expected_head.snapshot is None
                    else expected_head.snapshot.snapshot_id,
                    expected_head.revision,
                    expected_head.source_revision,
                    result.head.revision,
                    self._principal.id,
                    self._principal.authority,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._connection.execute(
                "INSERT INTO snapshot_events VALUES (?,?,'snapshot.published',?)",
                (
                    self._project_id,
                    operation_id,
                    json.dumps(
                        asdict(result),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ),
                ),
            )
            self._connection.execute(
                "INSERT INTO snapshot_outbox VALUES (?,?,'source_observer','pending')",
                (self._project_id, operation_id),
            )
        return result

    @contextmanager
    def _atomic_operation(self):
        self.require_all({"project:read"})
        if not self._write:
            raise CoreError("READ_ONLY_TRANSACTION", "A write unit of work is required")
        self._connection.execute("SAVEPOINT core_operation")
        try:
            yield
        except BaseException:
            self._connection.execute("ROLLBACK TO core_operation")
            self._connection.execute("RELEASE core_operation")
            raise
        self._connection.execute("RELEASE core_operation")

    def _insert_catalog(self, catalog, layers):
        self._require_snapshot_schema()
        self.require_all({"analysis:run"})
        if not self._write:
            raise CoreError("READ_ONLY_TRANSACTION", "A write unit of work is required")
        ref = catalog.snapshot
        exists = self._connection.execute(
            "SELECT 1 FROM snapshots WHERE project_id=? AND snapshot_id=?",
            (self._project_id, ref.snapshot_id),
        ).fetchone()
        if exists:
            old = self.get_snapshot(ref.snapshot_id)
            if (
                replace(catalog, published_at=old.published_at) != old
                or self.get_snapshot_layers(ref.snapshot_id) != layers
            ):
                raise CoreError(
                    "SNAPSHOT_CORRUPT", "Existing catalog content does not match"
                )
            return
        self._connection.execute(
            "INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?)",
            (
                self._project_id,
                ref.snapshot_id,
                ref.manifest_hash,
                catalog.source_digest,
                catalog.graph_hash,
                catalog.generation_relpath,
                catalog.manifest_version,
                catalog.published_at,
            ),
        )
        self._connection.executemany(
            "INSERT INTO snapshot_layers VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    self._project_id,
                    ref.snapshot_id,
                    layer.layer_id,
                    layer.ordinal,
                    layer.kind,
                    layer.configuration_uuid,
                    layer.identity_status,
                    layer.source_format,
                )
                for layer in layers
            ],
        )

    def revoke_membership(
        self, principal, *, operation_id=None, expected_revision=None
    ):
        return self._change_membership(
            principal, None, "membership.revoke", operation_id, expected_revision
        )

    def _require_admin_write(self):
        self.require_all({"project:admin"})
        if not self._write:
            raise CoreError("READ_ONLY_TRANSACTION", "A write unit of work is required")
