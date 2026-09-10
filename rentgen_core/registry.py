"""Trusted local registry. Display names are labels, never project selectors."""

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from . import _sqlite
from .context import Principal, validate_project_id
from .errors import CoreError
from .state import ProjectState

_SCHEMA = """
PRAGMA user_version=1;
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY NOT NULL,
    source_root TEXT UNIQUE NOT NULL,
    state_root TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class ProjectRegistration:
    project_id: str
    source_root: Path
    state_root: Path
    display_name: str


@dataclass(frozen=True)
class ProjectSummary:
    """Authorized discovery result; administrative locators are not exposed."""

    project_id: str
    display_name: str


@dataclass(frozen=True)
class ProjectRegistry:
    """Open an explicitly configured registry; construction performs no IO."""

    path: Path

    def __post_init__(self):
        object.__setattr__(self, "path", Path(self.path).absolute())

    @classmethod
    def create(cls, path: Path) -> "ProjectRegistry":
        registry = cls(path)
        with _sqlite.create_database(registry.path, _SCHEMA):
            pass
        return registry

    def register(
        self,
        owner: Principal,
        *,
        source_root: Path,
        state_root: Path,
        display_name: str,
    ) -> ProjectRegistration:
        """Trusted local bootstrap only: source must exist, state root must be new.

        Registry commit follows successful state bootstrap. A crash can leave an
        unregistered state directory, but never a committed half-built project.
        Attach/move/migration and aliases are intentionally absent.
        """
        source = Path(os.path.normcase(str(Path(source_root).resolve(strict=True))))
        if not source.is_dir():
            raise CoreError("INVALID_SOURCE_ROOT", "Source root must be a directory")
        state = Path(os.path.normcase(str(Path(state_root).resolve())))
        project_id = str(uuid4())
        created = False
        try:
            with _sqlite.transaction(self.path, write=True) as connection:
                self._check_schema(connection)
                for row in connection.execute(
                    "SELECT source_root, state_root FROM projects"
                ):
                    for registered in map(Path, row):
                        if any(
                            root.is_relative_to(registered)
                            or registered.is_relative_to(root)
                            for root in (source, state)
                        ):
                            raise CoreError(
                                "PROJECT_REGISTRATION_CONFLICT",
                                "Project roots must not overlap another project",
                            )
                try:
                    connection.execute(
                        "INSERT INTO projects VALUES (?, ?, ?, ?)",
                        (project_id, str(source), str(state), display_name),
                    )
                except sqlite3.IntegrityError as exc:
                    raise CoreError(
                        "PROJECT_REGISTRATION_CONFLICT",
                        "Source or state root is already registered",
                    ) from exc
                state.mkdir()
                created = True
                ProjectState.create(state / "state.sqlite3", project_id, owner)
        except BaseException:
            if created:
                # Only files created under this call's exclusively reserved directory.
                for name in ("state.sqlite3", "state.sqlite3-wal", "state.sqlite3-shm"):
                    (state / name).unlink(missing_ok=True)
                state.rmdir()
            raise
        return ProjectRegistration(project_id, source, state, display_name)

    def get(self, project_id: str) -> ProjectRegistration:
        validate_project_id(project_id)
        with _sqlite.transaction(self.path) as connection:
            self._check_schema(connection)
            row = connection.execute(
                "SELECT project_id, source_root, state_root, display_name "
                "FROM projects WHERE project_id=?",
                (project_id,),
            ).fetchone()
        if row is None:
            raise CoreError("PROJECT_NOT_FOUND", "Selected project is not registered")
        return ProjectRegistration(row[0], Path(row[1]), Path(row[2]), row[3])

    def list_for(self, principal: Principal) -> tuple[ProjectSummary, ...]:
        """Check each current membership; corruption is never hidden as denial.

        This is a discovery result, not a capability or cached permission grant.
        A later command must authorize again against the selected project's state.
        """
        with _sqlite.transaction(self.path) as connection:
            self._check_schema(connection)
            projects = connection.execute(
                "SELECT project_id,state_root,display_name FROM projects ORDER BY project_id"
            ).fetchall()
        result = []
        for project_id, state_root, display_name in projects:
            state = ProjectState(Path(state_root) / "state.sqlite3", project_id)
            try:
                with state.transaction(principal):
                    result.append(ProjectSummary(project_id, display_name))
            except CoreError as exc:
                if exc.code != "PROJECT_FORBIDDEN":
                    raise
        return tuple(result)

    @staticmethod
    def _check_schema(connection):
        if connection.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise CoreError("REGISTRY_SCHEMA_MISMATCH", "Unsupported registry schema")
