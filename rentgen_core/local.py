"""Explicit local composition; administrative state reads never open sources."""
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .context import Explicit, ProjectContext
from .registry import ProjectRegistry
from .resolver import ContextResolver
from .state import ProjectState


@dataclass(frozen=True)
class LocalRuntime:
    registry_path: Path
    graph_reader_factory: object = None
    graph_builder: object = None
    diagnostic_provider: object = None

    @property
    def registry(self):
        return ProjectRegistry(self.registry_path)

    def state_context(self, principal, project_id, *, permissions=()):
        """Authenticate before administrative payload/root IO; no snapshot lookup."""
        project = self.registry.get(project_id)
        state = ProjectState(project.state_root / "state.sqlite3", project_id)
        with state.transaction(principal) as tx:
            tx.require_all(set(permissions))
        return ProjectContext(
            project_id, principal, str(uuid4()), state, project.source_root
        )

    def head(self, principal, project_id):
        ctx = self.state_context(principal, project_id)
        with ctx.state.transaction(principal) as tx:
            return tx.get_project_head()

    def resolve(self, principal, project_id, snapshot_id=None):
        return ContextResolver(
            self.registry, graph_reader_factory=self.graph_reader_factory
        ).resolve_context(principal, Explicit(project_id), snapshot_id)
