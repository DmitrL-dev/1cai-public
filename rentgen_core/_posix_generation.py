"""Internal exclusive complete generation; no catalog mutation or promotion."""
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
import sys
from threading import get_ident
from time import monotonic
from uuid import uuid4

from . import _posix_source_tree as retained
from ._posix_captured_sources import _CapturedSources
from ._posix_capture_candidate import _json_size
from ._posix_snapshot_session import PosixSnapshotLimits, _PosixSnapshotSession
from ._verified_graph import VerifiedGraphLimits
from .context import Principal, SnapshotRef
from .errors import CoreError
from .graph import GraphBuildReceipt
from .manifests import build_manifest, parse_source_document, sha256
from .snapshots import ProjectHead, SnapshotCatalogEntry, SnapshotLayer, validate_operation_id
from .state import ProjectState


def _invalid():
    return CoreError("SOURCE_READ_SESSION_INVALID", "Generation owner is not active on its owner")


def _limit():
    return CoreError("SOURCE_CAPTURE_LIMIT_EXCEEDED", "Complete generation resource budget exceeded")


def _changed():
    return CoreError("SOURCE_CAPTURE_CHANGED", "Complete generation bytes or namespace changed")


def _manifest_size(value):
    if type(value) is bool:
        return 4 if value else 5
    if type(value) is list:
        return 2 + sum(map(_manifest_size, value)) + max(0, len(value) - 1)
    if type(value) is dict:
        return 2 + sum(_json_size(key) + 1 + _manifest_size(item) for key, item in value.items()) + max(0, len(value) - 1)
    return _json_size(value)


@dataclass(frozen=True)
class PosixGenerationLimits:
    # All caller source/graph/derived images plus verification copies and JSON.
    resident_byte_budget: int
    max_generation_bytes: int = 1536 * 1024**2
    max_manifest_bytes: int = 64 * 1024**2
    max_derived_bytes: int = 64 * 1024**2
    max_source_entries: int = 20_000
    max_inventory_items: int = 100_000
    max_retained_descriptors: int = 4096
    max_relative_components: int = 128
    deadline_seconds: int = 30

    def __post_init__(self):
        maxima = (4 * 1024**3, 2560 * 1024**2, 64 * 1024**2, 64 * 1024**2,
                  20_000, 200_000, 65_536, 256, 30)
        if any(type(value) is not int or not 1 <= value <= maximum
               for value, maximum in zip(asdict(self).values(), maxima)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed bounded generation limits required")


@dataclass(frozen=True)
class CompletePosixGeneration:
    """A proposal for a later short CAS; constructing it commits no state."""
    catalog: SnapshotCatalogEntry
    layers: tuple[SnapshotLayer, ...]
    expected_head: ProjectHead
    source_revision: int
    verified_total_bytes: int
    resident_image_accounting: int
    status: str = "complete_unpublished_generation"
    published: bool = False

    @property
    def snapshot(self):
        return self.catalog.snapshot


def open_posix_generation(*, state, principal, expected_head, captured, limits,
                          authorize_capture, generation_id=None):
    return _PosixGeneration(state, principal, expected_head, captured, limits,
                            authorize_capture, generation_id)


class _PrecommitSession(_PosixSnapshotSession):
    """Reuse the real copied-byte/SQLite verifier without a published catalog row."""
    def __init__(self, generation, catalog, factory, limits, graph_limits):
        self._generation = generation
        self._provided_catalog = catalog
        super().__init__(generation._state, generation._principal, catalog.snapshot,
                         factory, limits, graph_limits, generation._checkpoint)

    def _checkpoint(self):
        self._owner_check()
        if self._phase not in {"entering", "active"}:
            raise _invalid()
        self._deadline_check()
        self._generation._checkpoint()
        self._deadline_check()
        return self._provided_catalog


class _PosixGeneration:
    def __init__(self, state, principal, head, captured, limits, authorize, identifier):
        if (type(state) is not ProjectState or type(principal) is not Principal
                or type(head) is not ProjectHead or head.project_id != state.project_id
                or type(captured) is not _CapturedSources or type(limits) is not PosixGenerationLimits
                or not callable(authorize)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed trusted complete generation inputs required")
        self.generation_id = validate_operation_id(str(uuid4()) if identifier is None else identifier)
        self._state, self._principal, self._head, self._captured = state, principal, head, captured
        self._limits, self._authorize = limits, authorize
        self._phase, self._owner, self._busy = "new", None, False
        self._stack, self._root, self._generations = None, None, None
        self._directories, self._files = {}, {}
        self._result, self._proposal, self._seal_inputs = None, None, None
        self._used, self._resident = 0, 0

    def _owner_check(self):
        if self._owner != (os.getpid(), get_ident()):
            raise _invalid()

    def _checkpoint(self):
        self._owner_check()
        if self._phase not in {"entering", "active", "sealed"}:
            raise _invalid()
        if monotonic() >= self._deadline:
            raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "Generation deadline exceeded")
        self._authorize()
        self._captured.checkpoint()  # Also retains the original F2 operation deadline.
        if (self._captured._state != self._state or self._captured._principal != self._principal
                or self._captured._head != self._head):
            raise CoreError("SOURCE_REF_MISMATCH", "Copied owner belongs to another capture context")
        for directory in (self._root, self._generations, self._directories.get("")):
            if directory is not None:
                directory.verify()
        if monotonic() >= self._deadline:
            raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "Generation deadline exceeded")

    def _fd_bound(self, extra=0):
        fds = {entry[0] for directory in (self._root, self._generations, *self._directories.values())
               if directory is not None for entry in directory._chain}
        # Include scandir's duplicate or a transient leaf before it is opened.
        if len(fds) + extra + 1 > self._limits.max_retained_descriptors:
            raise _limit()

    def _exclusive_child(self, parent, name):
        self._checkpoint(); self._fd_bound(1)
        os.mkdir(name, mode=0o700, dir_fd=parent._fd)
        identity = retained._identity(parent.stat(name))
        parent.sync()
        child = self._stack.enter_context(parent.child(name, private=True))
        if retained._identity(os.fstat(child._fd)) != identity:
            raise _changed()
        return child

    def _directory(self, relative):
        if relative in self._directories:
            self._directories[relative].verify()
            return self._directories[relative]
        if (len(relative.split("/")) > self._limits.max_relative_components
                or len(self._directories) + len(self._files) >= self._limits.max_inventory_items):
            raise _limit()
        parent, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
        directory = self._exclusive_child(self._directory(parent), name)
        self._directories[relative] = directory
        return directory

    def _write(self, relative, raw):
        try:
            self._checkpoint()
            if type(raw) is not bytes or relative in self._files:
                raise CoreError("GRAPH_INPUT_MISMATCH", "New immutable generation bytes required")
            if (self._used + len(raw) > self._limits.max_generation_bytes
                    or len(self._directories) + len(self._files) >= self._limits.max_inventory_items
                    or len(relative.split("/")) > self._limits.max_relative_components):
                raise _limit()
            parent, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
            directory = self._directory(parent)
            self._fd_bound(1)
            with directory.create_file(name) as stream:
                identity = retained._identity(os.fstat(stream.fileno()))
                if stream.write(raw) != len(raw):
                    raise _changed()
            stamp = retained._stamp(directory.stat(name))
            if retained._identity(directory.stat(name)) != identity:
                raise _changed()
            self._files[relative] = (stamp, len(raw), sha256(raw))
            self._used += len(raw)
            self._verify_file(relative)
        finally:
            raw = None

    def _verify_file(self, relative):
        self._checkpoint(); self._fd_bound(1)
        stamp, size, digest = self._files[relative]
        parent, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
        raw = None
        try:
            with self._directories[parent].file(name) as stream:
                if retained._stamp(os.fstat(stream.fileno())) != stamp:
                    raise _changed()
                raw = stream.read(size + 1)
                if len(raw) != size or sha256(raw) != digest:
                    raise _changed()
            self._checkpoint()
        finally:
            raw = None

    def _inventory(self):
        expected = {relative: set() for relative in self._directories}
        for relative in (*self._directories, *self._files):
            if relative:
                parent, name = relative.rsplit("/", 1) if "/" in relative else ("", relative)
                expected[parent].add(name)
        for relative, directory in self._directories.items():
            self._checkpoint(); self._fd_bound()
            if set(directory.names()) != expected[relative]:
                raise _changed()
        for relative in self._files:
            self._verify_file(relative)

    def _sync(self):
        for relative in sorted(self._directories, key=lambda value: value.count("/") + bool(value), reverse=True):
            self._checkpoint()
            self._directories[relative].sync()
        self._generations.sync(); self._root.sync()
        self._checkpoint()

    def _reserve(self, value):
        if value > self._limits.resident_byte_budget:
            raise _limit()
        self._resident = max(self._resident, value)

    def __enter__(self):
        if self._phase != "new":
            raise _invalid()
        self._owner, self._phase, self._busy = (os.getpid(), get_ident()), "entering", True
        try:
            self._deadline = min(self._captured.operation_deadline, monotonic() + self._limits.deadline_seconds)
            self._checkpoint()
            self._entries, self._source = self._captured.entries, self._captured.source_document
            self._source_digest = self._captured.source_digest
            self._source_revision = self._captured.source_revision
            if (len(self._entries) > self._limits.max_source_entries
                    or len(self._source) > self._limits.max_manifest_bytes
                    or any(entry.size_bytes > 64 * 1024**2 for entry in self._entries)):
                raise _limit()
            self._source_total = sum(entry.size_bytes for entry in self._entries)
            self._reserve(self._source_total + 9 * len(self._source)
                          + max((entry.size_bytes + 1 for entry in self._entries), default=0))
            self._stack = ExitStack()
            if len(self._state.path.parent.parts) + 4 > self._limits.max_retained_descriptors:
                raise _limit()
            self._root = self._stack.enter_context(retained.open_directory(self._state.path.parent, private=True))
            self._generations = self._stack.enter_context(self._root.child("generations", create=True, private=True))
            self._directories[""] = self._exclusive_child(self._generations, self.generation_id)
            self._directory("sources")
            for layer in parse_source_document(self._source)["layers"]:
                self._directory("sources/" + layer["layer_id"])
            for entry in self._entries:
                self._write("sources/" + entry.layer_id + "/" + entry.relative_path,
                            self._captured.read_bytes(entry))
            self._inventory(); self._sync()
            self._phase = "active"
            return self
        except BaseException:
            self._cleanup(sys.exc_info())
            raise
        finally:
            self._busy = False

    def _call(self, operation, *, phases=("active",)):
        self._owner_check()
        if self._phase not in phases or self._busy:
            raise _invalid()
        self._busy = True
        result = None
        try:
            self._checkpoint()
            result = operation()
            self._checkpoint()
            return result
        except BaseException:
            result = None
            self._cleanup(sys.exc_info())
            raise
        finally:
            self._busy = False

    @property
    def scan_directory(self):
        """Borrowed private capability: caller must not close, mutate or retain it."""
        return self._call(lambda: self._directories["sources"])

    def checkpoint(self):
        return self._call(lambda: None, phases=("active", "sealed"))

    def seal(self, bundle, *, graph_reader_factory, graph_limits):
        def seal():
            # Import here keeps core module loading independent of concrete graph code.
            from rentgen_graph.posix_snapshot_adapter import PosixGraphBundle
            if (type(bundle) is not PosixGraphBundle or type(graph_limits) is not VerifiedGraphLimits
                    or type(bundle.receipt) is not GraphBuildReceipt
                    or type(bundle.sqlite_version) is not str or not 1 <= len(bundle.sqlite_version) <= 128):
                raise CoreError("GRAPH_INPUT_MISMATCH", "Typed graph bundle and verified reader limits required")
            images = (bundle.graph_bytes, bundle.ndjson, bundle.coverage)
            if (any(type(raw) is not bytes for raw in images)
                    or bundle.receipt.source_digest != self._source_digest
                    or len(bundle.graph_bytes) > graph_limits.max_graph_bytes
                    or any(len(raw) > self._limits.max_derived_bytes for raw in images[1:])):
                raise CoreError("GRAPH_INPUT_MISMATCH", "Graph bundle source or byte bounds differ")
            image_total = sum(map(len, images))
            # At peak the supplied graph remains alongside one verification copy
            # and SQLite's image. Manifest/source parsing and serialization use a
            # conservative 9x reservation; Python metadata is not a hard RSS cap.
            self._reserve(self._source_total + image_total + 9 * len(self._source)
                          + max(2 * len(bundle.graph_bytes) + 2 * graph_limits.cache_kib * 1024,
                                max(map(len, images), default=0) + 1))
            self._write("graph.sqlite3", bundle.graph_bytes)
            self._write("inputs/callgraph.ndjson", bundle.ndjson)
            self._write("inputs/scanner-coverage.json", bundle.coverage)
            graph = dict(asdict(bundle.receipt), relative_path="graph.sqlite3", raw_sha256=sha256(bundle.graph_bytes),
                         sqlite_version=bundle.sqlite_version, quality="unavailable")
            derived = [dict(relative_path=name, raw_sha256=sha256(raw), size_bytes=len(raw)) for name, raw in
                       (("inputs/callgraph.ndjson", bundle.ndjson), ("inputs/scanner-coverage.json", bundle.coverage))]
            source = parse_source_document(self._source)
            bound = _manifest_size(dict(format_version=1, canonicalization="rentgen-json-v1",
                project_id=self._state.project_id, source=source, source_digest=self._source_digest,
                capture=dict(bytes_immutable=True, method="working_tree_verified_passes_v1", temporal_atomicity="not_proven"),
                graph=graph, derived_inputs=derived))
            if bound > self._limits.max_manifest_bytes:
                raise _limit()
            self._reserve(self._source_total + image_total + 9 * (len(self._source) + bound)
                          + max(self._source_total + 2 * len(bundle.graph_bytes)
                                + 2 * graph_limits.cache_kib * 1024,
                                max(map(len, images), default=0) + 1))
            manifest = None
            try:
                manifest = build_manifest(self._source, graph, derived)
                if len(manifest) != bound:
                    raise _changed()
                # Final canonical manifest is the last new leaf, never a promotion.
                self._write("manifest.json", manifest)
                snapshot = SnapshotRef(self._state.project_id, sha256(manifest), sha256(manifest))
            finally:
                manifest = None
            layers = tuple(SnapshotLayer(**{key: layer[key] for key in
                ("layer_id", "ordinal", "kind", "configuration_uuid", "identity_status", "source_format")})
                for layer in source["layers"])
            catalog = SnapshotCatalogEntry(snapshot, self._source_digest, sha256(bundle.graph_bytes),
                "generations/" + self.generation_id, 1, datetime.now(timezone.utc).isoformat())
            self._proposal = CompletePosixGeneration(catalog, layers, self._head, self._source_revision,
                                                    self._used, self._resident)
            self._seal_inputs = graph_reader_factory, graph_limits
            self._inventory(); self._sync(); self._validate_complete()
            self._phase = "sealed"
        return self._call(seal)

    def _validate_complete(self):
        factory, graph_limits = self._seal_inputs
        limits = PosixSnapshotLimits(copied_byte_budget=self._limits.max_generation_bytes,
            resident_byte_budget=self._limits.resident_byte_budget,
            max_source_entries=self._limits.max_source_entries,
            max_inventory_items=self._limits.max_inventory_items,
            max_retained_descriptors=self._limits.max_retained_descriptors,
            max_relative_components=self._limits.max_relative_components,
            max_manifest_bytes=self._limits.max_manifest_bytes,
            deadline_seconds=self._limits.deadline_seconds)
        # Reader adds another descriptor chain and descendants while this owner
        # still holds its directories. Bound their combined simultaneous use.
        current = {entry[0] for cap in (self._root, self._generations, *self._directories.values())
                   for entry in cap._chain}
        verifier_cap = self._limits.max_retained_descriptors - len(current)
        if verifier_cap < 1:
            raise _limit()
        from dataclasses import replace
        limits = replace(limits, max_retained_descriptors=verifier_cap)
        with _PrecommitSession(self, self._proposal.catalog, factory, limits, graph_limits):
            pass
        self._checkpoint()

    def _cleanup(self, exception):
        failure = None
        stack, self._stack = self._stack, None
        if stack is not None:
            try:
                stack.__exit__(*exception)
            except BaseException:
                failure = sys.exc_info()
        self._phase = "closed"
        self._directories.clear(); self._files.clear()
        self._source = self._entries = self._seal_inputs = self._proposal = None
        self._root = self._generations = self._authorize = self._captured = None
        self._state = self._principal = None
        if failure is not None and exception[0] is None:
            raise failure[1].with_traceback(failure[2])

    def __exit__(self, kind, value, traceback):
        self._owner_check()
        if self._busy or self._phase not in {"active", "sealed", "closed"}:
            raise _invalid()
        if self._phase == "closed":
            return False
        self._busy = True
        result = None
        try:
            if kind is None:
                if self._phase != "sealed":
                    raise CoreError("GRAPH_INPUT_MISMATCH", "Unsealed generation cannot complete")
                self._inventory(); self._sync(); self._validate_complete()
                result = self._proposal
        except BaseException:
            self._cleanup(sys.exc_info())
            raise
        else:
            self._cleanup((kind, value, traceback))
            if kind is None:
                if monotonic() >= self._deadline:
                    raise CoreError("SOURCE_READ_DEADLINE_EXCEEDED", "Generation deadline exceeded during cleanup")
                self._result = result
        finally:
            self._busy = False
        return False

    @property
    def result(self):
        self._owner_check()
        if self._result is None or self._busy:
            raise _invalid()
        return self._result
