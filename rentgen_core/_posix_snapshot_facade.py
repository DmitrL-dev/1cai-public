"""Request-owned POSIX read facades; a fresh verified session per operation."""

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import os
from threading import get_ident
from typing import Callable

from ._posix_snapshot_session import PosixSnapshotLimits, open_posix_snapshot_session
from ._verified_graph import VerifiedGraphLimits
from .context import Principal, SnapshotRef
from .errors import CoreError
from .manifests import parse_manifest
from .source_paths import validate_source_path
from .sources import SnapshotCapabilities, SnapshotReadLimits, _source_page
from .state import ProjectState


def _owner():
    return os.getpid(), get_ident()


@dataclass(frozen=True)
class PosixSnapshotSources:
    snapshot: SnapshotRef
    _state: ProjectState
    _principal: Principal
    _factory: object
    _limits: PosixSnapshotLimits
    _graph_limits: VerifiedGraphLimits
    _authorize_read: Callable[[], None]
    _owner: tuple = field(default_factory=_owner, init=False, repr=False, compare=False)
    _busy: bool = field(default=False, init=False, repr=False, compare=False)

    def __post_init__(self):
        if (type(self.snapshot) is not SnapshotRef or type(self._state) is not ProjectState
                or type(self._principal) is not Principal
                or self.snapshot.project_id != self._state.project_id
                or type(self._limits) is not PosixSnapshotLimits
                or type(self._graph_limits) is not VerifiedGraphLimits
                or not callable(self._authorize_read)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed trusted POSIX facade inputs required")
        if not callable(getattr(self._factory, "open_verified", None)):
            raise CoreError("GRAPH_ADAPTER_UNAVAILABLE", "A verified-byte graph reader is required")

    def _run(self, operation):
        if self._owner != _owner() or self._busy:
            raise CoreError("SNAPSHOT_READ_SESSION_INVALID", "POSIX facade is not active on its owner")
        object.__setattr__(self, "_busy", True)
        result = None
        try:
            with open_posix_snapshot_session(
                state=self._state, principal=self._principal, snapshot=self.snapshot,
                graph_reader_factory=self._factory, limits=self._limits,
                graph_limits=self._graph_limits, authorize_read=self._authorize_read,
            ) as session:
                result = operation(session)
            return result  # Disclosure follows successful exit and reauthorization.
        except BaseException:
            result = None
            raise
        finally:
            object.__setattr__(self, "_busy", False)

    def _verify(self):
        self._run(lambda session: None)

    def read_session(self, *, limits, purpose=None):
        """A fresh verified POSIX session for reviewed read-only consumers only.

        Metadata navigation reads bytes through entries/read_source/checkpoint,
        all bounded by this facade's POSIX limits and reauthorized per read.
        Every other legacy consumer keeps a controlled zero-IO refusal.
        """
        if purpose != "metadata-navigation" or type(limits) is not SnapshotReadLimits:
            raise CoreError(
                "CAPABILITY_UNAVAILABLE",
                "The legacy Windows retained session is unavailable for POSIX snapshots",
            )
        return self._owned_session()

    @contextmanager
    def _owned_session(self):
        if self._owner != _owner() or self._busy:
            raise CoreError("SNAPSHOT_READ_SESSION_INVALID", "POSIX facade is not active on its owner")
        object.__setattr__(self, "_busy", True)
        try:
            with open_posix_snapshot_session(
                state=self._state, principal=self._principal, snapshot=self.snapshot,
                graph_reader_factory=self._factory, limits=self._limits,
                graph_limits=self._graph_limits, authorize_read=self._authorize_read,
            ) as session:
                yield session
        finally:
            object.__setattr__(self, "_busy", False)

    def resolve(self, layer_id, relative_path):
        def operation(session):
            validate_source_path(relative_path)
            for entry in session.entries():
                if (entry.ref.layer_id, entry.ref.relative_path) == (layer_id, relative_path):
                    return entry.ref
            raise CoreError("SOURCE_NOT_FOUND", "Source is absent from this snapshot")
        return self._run(operation)

    def read_source(self, ref):
        return self._run(lambda session: session.read_source(ref))

    def list_entries(self, *, limit=100, cursor=None, query="", kind="all", layer=None):
        return self._run(lambda session: _source_page(
            parse_manifest(session.manifest_bytes()), self.snapshot,
            limit=limit, cursor=cursor, query=query, kind=kind, layer=layer,
        ))


@dataclass(frozen=True)
class PosixSnapshotGraph:
    snapshot: SnapshotRef
    _sources: PosixSnapshotSources
    capabilities: SnapshotCapabilities = SnapshotCapabilities()

    def __post_init__(self):
        if type(self._sources) is not PosixSnapshotSources or self.snapshot != self._sources.snapshot:
            raise CoreError("SOURCE_REF_MISMATCH", "Graph and sources must use one pinned snapshot")

    def _query(self, ref, depth=None):
        def operation(session):
            if depth is not None and (type(depth) is not int or not 1 <= depth <= 5):
                raise CoreError("INVALID_QUERY_OPTIONS", "Impact depth must be 1..5")
            return dict(
                project_id=self.snapshot.project_id,
                snapshot_id=self.snapshot.snapshot_id,
                manifest_hash=self.snapshot.manifest_hash,
                capabilities=asdict(self.capabilities),
                result=(session.resolve_module(ref) if depth is None else
                        session.module_impact(ref, max_depth=depth, max_edges=600)),
            )
        return self._sources._run(operation)

    def resolve_module(self, ref):
        return self._query(ref)

    def impact(self, ref, *, depth=1):
        # Keep authorization ahead of invalid public options, including None.
        if depth is None:
            def invalid(session):
                raise CoreError("INVALID_QUERY_OPTIONS", "Impact depth must be 1..5")
            return self._sources._run(invalid)
        return self._query(ref, depth)
