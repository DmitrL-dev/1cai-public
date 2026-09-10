"""Immutable snapshot state values; catalog records do not grant file capabilities."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from .context import ProjectContext, SnapshotRef, validate_project_id
from .errors import CoreError
from .source_configuration import SourceLayerSpec


def _snapshot_invalid(message):
    return CoreError("SNAPSHOT_CORRUPT", message)


def _validate_hash(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise _snapshot_invalid("Expected a lowercase SHA-256 digest")


def validate_operation_id(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise CoreError("OPERATION_CONFLICT", "Expected a canonical operation UUID")
    return value


@dataclass(frozen=True)
class ProjectHead:
    project_id: str
    revision: int
    snapshot: SnapshotRef | None
    source_revision: int

    def __post_init__(self):
        validate_project_id(self.project_id)
        for value, minimum in ((self.revision, 0), (self.source_revision, 1)):
            if type(value) is not int or not minimum <= value < 2**63:
                raise CoreError("HEAD_CONFLICT", "Invalid project head revision")
        if self.snapshot is not None and (
            not isinstance(self.snapshot, SnapshotRef)
            or self.snapshot.project_id != self.project_id
        ):
            raise CoreError(
                "CONTEXT_PROJECT_MISMATCH", "Head belongs to another project"
            )


@dataclass(frozen=True)
class SnapshotCatalogEntry:
    """Trusted publication metadata; constructing this value verifies no files."""

    snapshot: SnapshotRef
    source_digest: str
    graph_hash: str
    generation_relpath: str
    manifest_version: int
    published_at: str

    def __post_init__(self):
        if not isinstance(self.snapshot, SnapshotRef):
            raise _snapshot_invalid("Snapshot reference required")
        _validate_hash(self.source_digest)
        _validate_hash(self.graph_hash)
        generation_valid = (
            self.generation_relpath == "generations/" + self.snapshot.snapshot_id
        )
        if isinstance(
            self.generation_relpath, str
        ) and self.generation_relpath.startswith("generations/"):
            locator = self.generation_relpath.removeprefix("generations/")
            try:
                generation_valid = generation_valid or str(UUID(locator)) == locator
            except ValueError:
                pass
        if not generation_valid:
            raise _snapshot_invalid("Invalid generation locator")
        if type(self.manifest_version) is not int or self.manifest_version != 1:
            raise CoreError("SNAPSHOT_SCHEMA_MISMATCH", "Unsupported manifest version")
        try:
            valid = (
                isinstance(self.published_at, str)
                and datetime.fromisoformat(self.published_at).tzinfo is not None
            )
        except ValueError:
            valid = False
        if not valid:
            raise _snapshot_invalid("Publication timestamp requires a timezone")


@dataclass(frozen=True)
class SnapshotLayer:
    layer_id: str
    ordinal: int
    kind: Literal["base", "extension"]
    configuration_uuid: None
    identity_status: Literal["unresolved"]
    source_format: Literal["designer_xml", "edt", "unknown"]

    def __post_init__(self):
        SourceLayerSpec(self.layer_id, self.ordinal, self.kind, ".", self.source_format)
        if self.configuration_uuid is not None or self.identity_status != "unresolved":
            raise _snapshot_invalid(
                "Verified metadata identity is not supported by this state slice"
            )


@dataclass(frozen=True)
class PublishResult:
    operation_id: str
    snapshot: SnapshotRef
    head: ProjectHead
    publication: Literal["committed"]

    def __post_init__(self):
        validate_operation_id(self.operation_id)
        if (
            self.publication != "committed"
            or not isinstance(self.snapshot, SnapshotRef)
            or not isinstance(self.head, ProjectHead)
            or self.head.snapshot != self.snapshot
        ):
            raise _snapshot_invalid("Invalid publication receipt")


def get_project_head(ctx: ProjectContext) -> ProjectHead:
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    with ctx.state.transaction(ctx.principal) as tx:
        return tx.get_project_head()


def get_publication(ctx: ProjectContext, operation_id: str) -> PublishResult:
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    with ctx.state.transaction(ctx.principal) as tx:
        return tx.get_publication(operation_id)
