"""Resolve explicit project scope before any project source IO."""

from dataclasses import dataclass
from uuid import uuid4

from .context import (
    Explicit,
    Principal,
    ProjectContext,
    SnapshotRef,
    UseConfiguredDefault,
    validate_project_id,
)
from .errors import CoreError
from .registry import ProjectRegistry
from .state import ProjectState
from .graph import GraphReaderFactory
from .sources import SnapshotSources, SnapshotGraph, verify_generation


@dataclass(frozen=True)
class ContextResolver:
    registry: ProjectRegistry
    configured_default: str | None = None
    graph_reader_factory: GraphReaderFactory | None = None

    def __post_init__(self):
        if self.configured_default is not None:
            validate_project_id(self.configured_default)

    def resolve_context(
        self,
        principal: Principal,
        selection: Explicit | UseConfiguredDefault,
        snapshot_id: str | None = None,
        *,
        request_id: str | None = None
    ) -> ProjectContext:
        """Use only adapter-authenticated principal and explicit selection DTOs.

        Absence is represented by UseConfiguredDefault; blank/unknown selectors
        must never be retried through default. No global current project exists.
        """
        if isinstance(selection, Explicit):
            project_id = selection.project_id
        elif (
            isinstance(selection, UseConfiguredDefault)
            and self.configured_default is not None
        ):
            project_id = self.configured_default
        else:
            raise CoreError(
                "PROJECT_REQUIRED", "An explicit or configured project is required"
            )
        project = self.registry.get(project_id)
        state = ProjectState(project.state_root / "state.sqlite3", project_id)
        with state.transaction(principal) as tx:
            if snapshot_id is not None:
                SnapshotRef(project_id, snapshot_id, snapshot_id)
                catalog = tx.get_snapshot(snapshot_id)
            else:
                head = tx.get_project_head()
                catalog = (
                    None
                    if head.snapshot is None
                    else tx.get_snapshot(head.snapshot.snapshot_id)
                )
        snapshot, sources, graph = None, None, None
        if catalog is not None:
            path = project.state_root / catalog.generation_relpath
            verify_generation(path, catalog)
            if self.graph_reader_factory is None:
                raise CoreError(
                    "GRAPH_ADAPTER_UNAVAILABLE",
                    "A graph reader adapter must be explicitly installed",
                )
            snapshot = catalog.snapshot
            sources = SnapshotSources(snapshot, state, principal, path)
            graph = SnapshotGraph(snapshot, sources, self.graph_reader_factory)
        return ProjectContext(
            project_id,
            principal,
            request_id or str(uuid4()),
            state,
            project.source_root,
            snapshot,
            sources,
            graph,
        )


def require_permission(ctx: ProjectContext, permission: str) -> None:
    """Standalone check; mutations must check inside the same write unit of work."""
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({permission})


def require_snapshot(ctx: ProjectContext) -> SnapshotRef:
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    if ctx.snapshot is None:
        raise CoreError("SNAPSHOT_REQUIRED", "A published project snapshot is required")
    return ctx.snapshot
