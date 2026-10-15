"""Injected graph contracts. The core imports no concrete scanner or HTTP adapter."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, ContextManager, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from ._verified_graph import VerifiedGraphLimits

from .errors import CoreError
from .manifests import CapturedInput
from .context import SnapshotRef
from .snapshots import _validate_hash


class CapturedTree(Protocol):
    project_id: str
    source_digest: str
    entries: tuple[CapturedInput, ...]

    def read_bytes(self, entry: CapturedInput) -> bytes:
        ...


@dataclass(frozen=True)
class GraphBuildReceipt:
    schema_version: str
    identity_version: str
    source_digest: str
    input_binding_hash: str
    adapter_version: str
    scanner_version: str
    builder_version: str
    options_hash: str
    semantic_scope: str

    def __post_init__(self):
        for value in (self.source_digest, self.input_binding_hash, self.options_hash):
            _validate_hash(value)
        for value in (
            self.schema_version,
            self.identity_version,
            self.adapter_version,
            self.scanner_version,
            self.builder_version,
            self.semantic_scope,
        ):
            if not isinstance(value, str) or not value or len(value) > 1024:
                raise CoreError("GRAPH_INPUT_MISMATCH", "Invalid graph build receipt")


class GraphBuilder(Protocol):
    def build(
        self, captured: CapturedTree, *, output_path: Path, work_dir: Path
    ) -> GraphBuildReceipt:
        ...


class GraphReader(Protocol):
    def resolve_module(self, graph_source_path: str) -> dict:
        ...

    def module_impact(
        self, graph_source_path: str, *, max_depth: int, max_edges: int
    ) -> dict:
        ...


class GraphReaderFactory(Protocol):
    def open(self, *, graph_path: Path, snapshot: SnapshotRef) -> GraphReader:
        ...


class VerifiedGraphReaderFactory(Protocol):
    def open_verified(
        self, *, graph_bytes: bytes, manifest_bytes: bytes, snapshot: SnapshotRef,
        authorize_read: Callable[[], None], limits: "VerifiedGraphLimits",
    ) -> ContextManager[GraphReader]:
        ...


def open_verified_graph(factory, **options):
    """Require the reviewed byte seam; a path-only adapter is never a fallback."""
    opener = getattr(factory, "open_verified", None)
    if not callable(opener):
        raise CoreError("GRAPH_ADAPTER_UNAVAILABLE", "A verified-byte graph reader is required")
    # Do not interpose a generator context: a refused foreign/reentrant exit
    # must leave the adapter context available for its real owner to close.
    return opener(**options)
