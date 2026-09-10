"""Explicit immutable inputs; trusted adapters authenticate before constructing Principal.

These Python values are not a security boundary against code in this process or
the same OS account. Request JSON must never be deserialized into a Principal.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from .errors import CoreError

if TYPE_CHECKING:
    from .state import ProjectState
    from .sources import SnapshotSources, SnapshotGraph


def validate_project_id(value: str) -> str:
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise CoreError("INVALID_PROJECT_ID", "Expected a canonical project UUID")
    return value


@dataclass(frozen=True)
class Principal:
    id: str
    authority: Literal["local_os", "verified_token", "local_service"]

    def __post_init__(self):
        if (
            not isinstance(self.id, str)
            or not self.id.strip()
            or self.authority not in ("local_os", "verified_token", "local_service")
        ):
            raise CoreError(
                "INVALID_PRINCIPAL",
                "Verified identity and known authority are required",
            )


@dataclass(frozen=True)
class Explicit:
    project_id: str

    def __post_init__(self):
        validate_project_id(self.project_id)


@dataclass(frozen=True)
class UseConfiguredDefault:
    """Only an absent adapter selector may be translated to this value."""


@dataclass(frozen=True)
class SnapshotRef:
    """Pinned manifest identity, not proof of capture, publication or availability."""

    project_id: str
    snapshot_id: str
    manifest_hash: str

    def __post_init__(self):
        validate_project_id(self.project_id)
        if (
            not isinstance(self.snapshot_id, str)
            or len(self.snapshot_id) != 64
            or any(c not in "0123456789abcdef" for c in self.snapshot_id)
        ):
            raise CoreError("INVALID_SNAPSHOT_ID", "Expected a SHA-256 snapshot ID")
        if self.manifest_hash != self.snapshot_id:
            raise CoreError(
                "INVALID_SNAPSHOT_ID", "Manifest hash must match snapshot ID"
            )


@dataclass(frozen=True)
class ProjectContext:
    """Resolver-produced request scope; handles and values do not cache permissions.

    source_root is administrative-only: a registered locator for configuring
    layers, never snapshot evidence. Source/graph capabilities retain one exact
    snapshot and reauthorize their operations against current membership.
    """

    project_id: str
    principal: Principal
    request_id: str
    state: "ProjectState"
    source_root: Path
    snapshot: SnapshotRef | None = None
    sources: "SnapshotSources | None" = None
    graph: "SnapshotGraph | None" = None

    def __post_init__(self):
        validate_project_id(self.project_id)
        if self.state.project_id != self.project_id or (
            self.snapshot is not None and self.snapshot.project_id != self.project_id
        ):
            raise CoreError(
                "CONTEXT_PROJECT_MISMATCH",
                "Context handles belong to different projects",
            )
        for capability in (self.sources, self.graph):
            if capability is not None and (
                self.snapshot is None or capability.snapshot != self.snapshot
            ):
                raise CoreError(
                    "CONTEXT_PROJECT_MISMATCH",
                    "Capability snapshot does not match context",
                )
