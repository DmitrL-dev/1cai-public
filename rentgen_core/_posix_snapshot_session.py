"""Internal copied POSIX generation owner; no capture or public OS admission."""
from contextlib import ExitStack
from dataclasses import asdict, dataclass
import os
from pathlib import PurePosixPath
import stat
import sys
from threading import get_ident
from time import monotonic

from . import _posix_source_tree as retained
from ._verified_graph import VerifiedGraphLimits
from .context import Principal, SnapshotRef
from .errors import CoreError
from .graph import open_verified_graph
from .manifests import parse_manifest, sha256
from .sources import SourceEntry, SourceRef, _corrupt, _MAX_MANIFEST, _MAX_DERIVED
from .state import ProjectState


@dataclass(frozen=True)
class PosixSnapshotLimits:
    """Explicit byte-image accounting, not a process RSS or filesystem lease cap."""
    copied_byte_budget: int
    resident_byte_budget: int
    max_source_entries: int = 20_000
    max_inventory_items: int = 200_000
    max_retained_descriptors: int = 1024
    max_relative_components: int = 128
    max_manifest_bytes: int = _MAX_MANIFEST
    deadline_seconds: int = 30

    def __post_init__(self):
        maxima = (2560 * 1024**2, 4 * 1024**3, 20_000, 200_000,
                  65_536, 256, _MAX_MANIFEST, 30)
        if any(type(value) is not int or not 1 <= value <= maximum
               for value, maximum in zip(asdict(self).values(), maxima)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed bounded POSIX session budgets required")


def _invalid():
    return CoreError("SNAPSHOT_READ_SESSION_INVALID", "POSIX session is not active on its owner")


def _limit():
    return CoreError("SNAPSHOT_READ_LIMIT_EXCEEDED", "POSIX session resource budget exceeded")


def open_posix_snapshot_session(*, state, principal, snapshot, graph_reader_factory,
                                limits, graph_limits, authorize_read):
    """Trusted internal factory; derive the retained root from the state locator."""
    return _PosixSnapshotSession(state, principal, snapshot, graph_reader_factory,
                                 limits, graph_limits, authorize_read)


class _PosixSnapshotSession:
    def __init__(self, state, principal, snapshot, factory, limits, graph_limits, authorize):
        if (type(state) is not ProjectState or type(principal) is not Principal
                or type(snapshot) is not SnapshotRef or state.project_id != snapshot.project_id
                or type(limits) is not PosixSnapshotLimits
                or type(graph_limits) is not VerifiedGraphLimits or not callable(authorize)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed trusted POSIX session inputs required")
        self._state, self._principal, self.snapshot = state, principal, snapshot
        self._factory, self._limits, self._graph_limits = factory, limits, graph_limits
        self._authorize_read = authorize
        self._phase, self._owner, self._busy = "new", None, False
        self._stack, self._graph_context, self._reader = None, None, None
        self._directories, self._stamps, self._buffers = {}, {}, {}
        self._manifest = self._document = None
        self._entries, self._index = (), {}
        self._used, self._resident_peak = 0, 0
        self._summary = None

    def _owner_check(self):
        if self._owner != (os.getpid(), get_ident()):
            raise _invalid()

    def _checkpoint(self):
        # N invokes this callback during an already-busy graph operation.
        self._owner_check()
        if self._phase not in {"entering", "active"}:
            raise _invalid()
        self._deadline_check()
        self._authorize_read()
        self._deadline_check()
        with self._state.transaction(self._principal) as tx:
            tx.require_all({"project:read"})
            catalog = tx.get_snapshot(self.snapshot.snapshot_id)
        if catalog.snapshot != self.snapshot or (
            hasattr(self, "_catalog") and catalog != self._catalog
        ):
            raise _corrupt("POSIX session catalog binding changed")
        self._deadline_check()
        return catalog

    def _deadline_check(self):
        if monotonic() >= self._deadline:
            raise CoreError("SNAPSHOT_READ_DEADLINE_EXCEEDED", "POSIX session deadline exceeded")

    def _reserve_resident(self, size):
        if size > self._limits.resident_byte_budget:
            raise _limit()
        self._resident_peak = max(self._resident_peak, size)

    def _copy(self, relative, maximum, *, exact=None, digest=None):
        raw = None
        try:
            self._checkpoint()
            parent, name = str(PurePosixPath(relative).parent), PurePosixPath(relative).name
            directory = self._directories["" if parent == "." else parent]
            with directory.file(name) as stream:
                before = os.fstat(stream.fileno())
                stamp = retained._stamp(before)
                if relative in self._stamps and self._stamps[relative] != stamp:
                    raise _corrupt("Retained file changed before copying")
                size = before.st_size
                if size > maximum or (exact is not None and size != exact):
                    raise _corrupt("Retained file size does not match its bound")
                if self._used + size > self._limits.copied_byte_budget:
                    raise _limit()
                # read(size + 1) bounds even a concurrent grow; no whole-file bytearray.
                held = len(self._manifest or b"") + sum(map(len, self._buffers.values()))
                self._reserve_resident(held + size + 1)
                raw = stream.read(size + 1)
                if len(raw) != size or (digest is not None and sha256(raw) != digest):
                    raise _corrupt("Retained artifact bytes do not match manifest")
                self._used += size
                self._stamps[relative] = stamp
            self._checkpoint()
            return raw
        except BaseException:
            raw = None  # Retained tracebacks must not keep an undisclosed image.
            raise

    def _prepare(self):
        document = self._document
        if (document["project_id"] != self.snapshot.project_id
                or document["source_digest"] != self._catalog.source_digest
                or document["graph"]["raw_sha256"] != self._catalog.graph_hash):
            raise _corrupt("Catalog content binding does not match manifest")
        entries = document["source"]["entries"]
        if (len(entries) > self._limits.max_source_entries
                or any(entry["size_bytes"] > 64 * 1024**2 for entry in entries)
                or sum(entry["size_bytes"] for entry in entries) > 1024**3
                or any(entry["size_bytes"] > _MAX_DERIVED for entry in document["derived_inputs"])):
            raise _limit()
        self._expected = {"manifest.json", "graph.sqlite3"}
        self._expected.update(entry["relative_path"] for entry in document["derived_inputs"])
        self._expected.update("sources/" + entry["layer_id"] + "/" + entry["relative_path"] for entry in entries)
        self._required_dirs = set()
        for path in self._expected:
            parts = PurePosixPath(path).parts
            if len(parts) > self._limits.max_relative_components:
                raise _limit()
            self._required_dirs.update("/".join(parts[:index]) for index in range(1, len(parts)))
        # Published manifests list files, not these potentially empty directories.
        self._allowed_dirs = self._required_dirs | {"sources", "inputs", "build-work"}
        self._allowed_dirs.update("sources/" + layer["layer_id"] for layer in document["source"]["layers"])
        self._entries = tuple(SourceEntry(SourceRef(self.snapshot, entry["layer_id"],
            entry["relative_path"], entry["raw_sha256"]), entry["size_bytes"], entry["encoding"]) for entry in entries)
        self._index = {(entry.ref.layer_id, entry.ref.relative_path): entry for entry in self._entries}

    def _inventory(self, *, entering):
        found, directories, count = set(), {""}, 0
        pending = [""]
        while pending:
            self._checkpoint()
            relative = pending.pop()
            directory = self._directories[relative]
            directory.verify()
            current = retained._stamp(os.fstat(directory._fd))
            if relative in self._stamps and self._stamps[relative] != current:
                raise _corrupt("Generation directory changed during session")
            self._stamps[relative] = current
            remaining = self._limits.max_inventory_items - count
            for name in directory.names(maximum=min(retained.MAX_ENTRIES, remaining + 1)):
                self._deadline_check()
                count += 1
                if count > self._limits.max_inventory_items:
                    raise _limit()
                child = relative + "/" + name if relative else name
                if len(PurePosixPath(child).parts) > self._limits.max_relative_components:
                    raise _limit()
                info = directory.stat(name)
                stamp = retained._stamp(info)
                if child in self._expected:
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise _corrupt("Generation leaf must be a single-link regular file")
                    found.add(child)
                elif child in self._allowed_dirs and stat.S_ISDIR(info.st_mode):
                    directories.add(child)
                    if child not in self._directories:
                        if not entering:
                            raise _corrupt("Generation directory inventory changed")
                        self._check_descriptors(extra=1)
                        cap = self._stack.enter_context(directory.child(name, private=True))
                        self._directories[child] = cap
                    if retained._stamp(os.fstat(self._directories[child]._fd)) != stamp:
                        raise _corrupt("Generation directory changed during inventory")
                    pending.append(child)
                else:
                    raise _corrupt("Generation contains an unlisted or unsafe object")
                if child in self._stamps and self._stamps[child] != stamp:
                    raise _corrupt("Generation object changed during session")
                self._stamps[child] = stamp
        if found != self._expected or not self._required_dirs <= directories:
            raise _corrupt("Generation inventory does not match manifest")
        actual = found | directories
        if hasattr(self, "_inventory_paths") and actual != self._inventory_paths:
            raise _corrupt("Generation inventory changed during session")
        self._inventory_paths = actual

    def _check_descriptors(self, *, extra):
        # Root's absolute ancestor chain, generations/selected, held descendants,
        # plus one transient leaf. Charge before the descriptor is opened.
        if self._base_descriptors + max(0, len(self._directories) - 1) + extra + 1 > self._limits.max_retained_descriptors:
            raise _limit()

    def __enter__(self):
        if self._phase != "new":
            raise _invalid()
        self._owner, self._phase, self._busy = (os.getpid(), get_ident()), "entering", True
        self._deadline = monotonic() + self._limits.deadline_seconds
        graph = None
        try:
            if sys.platform not in {"linux", "darwin"}:
                raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "No POSIX generation session")
            self._catalog = self._checkpoint()
            root_path = self._state.path.parent
            self._base_descriptors = len(root_path.parts) + 2
            self._check_descriptors(extra=0)
            self._stack = ExitStack()
            root = self._stack.enter_context(retained.open_directory(root_path, private=True))
            generations = self._stack.enter_context(root.child("generations", private=True))
            selected = self._catalog.generation_relpath.removeprefix("generations/")
            self._directories[""] = self._stack.enter_context(generations.child(selected, private=True))
            self._stamps[""] = retained._stamp(os.fstat(self._directories[""]._fd))
            self._manifest = self._copy("manifest.json", self._limits.max_manifest_bytes,
                                        digest=self.snapshot.manifest_hash)
            self._document = parse_manifest(self._manifest)
            self._prepare()
            self._inventory(entering=True)
            graph_size = self._directories[""].stat("graph.sqlite3").st_size
            if graph_size > self._graph_limits.max_graph_bytes or 2 * graph_size > self._graph_limits.image_buffer_budget:
                raise _limit()
            source_size = sum(entry.size_bytes for entry in self._entries)
            derived = self._document["derived_inputs"]
            if self._used + source_size + sum(entry["size_bytes"] for entry in derived) + graph_size > self._limits.copied_byte_budget:
                raise _limit()
            held = len(self._manifest) + source_size
            self._reserve_resident(held + max(2 * graph_size, max((entry["size_bytes"] + 1 for entry in derived), default=0)))
            for entry in self._entries:
                relative = "sources/" + entry.ref.layer_id + "/" + entry.ref.relative_path
                self._buffers[entry.ref] = self._copy(relative, entry.size_bytes, exact=entry.size_bytes, digest=entry.ref.raw_sha256)
            for entry in derived:
                self._copy(entry["relative_path"], entry["size_bytes"], exact=entry["size_bytes"], digest=entry["raw_sha256"])
            graph = self._copy("graph.sqlite3", self._graph_limits.max_graph_bytes, digest=self._catalog.graph_hash)
            self._graph_context = open_verified_graph(self._factory, graph_bytes=graph,
                manifest_bytes=self._manifest, snapshot=self.snapshot,
                authorize_read=self._checkpoint, limits=self._graph_limits)
            self._reader = self._graph_context.__enter__()
            del graph
            self._inventory(entering=False)
            self._checkpoint()
            self._phase = "active"
            return self
        except BaseException:
            self._cleanup(sys.exc_info())
            raise
        finally:
            graph = None
            self._busy = False

    def _call(self, operation):
        self._owner_check()
        if self._phase != "active" or self._busy:
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

    def checkpoint(self):
        return self._call(lambda: None)

    def entries(self):
        return self._call(lambda: self._entries)

    def manifest_bytes(self):
        return self._call(lambda: self._manifest)

    def _entry(self, ref):
        if type(ref) is not SourceRef or ref.snapshot != self.snapshot:
            raise CoreError("SOURCE_REF_MISMATCH", "Source belongs to another snapshot")
        entry = self._index.get((ref.layer_id, ref.relative_path))
        if entry is None:
            raise CoreError("SOURCE_NOT_FOUND", "Source is absent from selected snapshot")
        if ref != entry.ref:
            raise CoreError("SOURCE_REF_MISMATCH", "Exact retained source reference required")
        return entry

    def read_source(self, ref):
        return self._call(lambda: self._buffers[self._entry(ref).ref])

    def resolve_module(self, ref):
        def query():
            entry = self._entry(ref)
            return self._reader.resolve_module(entry.ref.layer_id + "/" + entry.ref.relative_path)
        return self._call(query)

    def module_impact(self, ref, *, max_depth, max_edges):
        def query():
            entry = self._entry(ref)
            return self._reader.module_impact(entry.ref.layer_id + "/" + entry.ref.relative_path,
                max_depth=max_depth, max_edges=max_edges)
        return self._call(query)

    def _cleanup(self, exception):
        failure = None
        context, self._graph_context = self._graph_context, None
        self._reader = None
        if context is not None:
            try:
                context.__exit__(*exception)
            except BaseException:
                failure = sys.exc_info()
        stack, self._stack = self._stack, None
        if stack is not None:
            try:
                stack.__exit__(*(exception if exception[0] is not None else failure or exception))
            except BaseException:
                failure = failure or sys.exc_info()
        self._phase = "closed"
        self._directories.clear()
        self._stamps.clear()
        self._buffers.clear()
        self._manifest = self._document = self._authorize_read = None
        self._factory = self._state = self._principal = None
        self._entries, self._index = (), {}
        if failure is not None and exception[0] is None:
            raise failure[1].with_traceback(failure[2])

    def __exit__(self, kind, value, traceback):
        self._owner_check()  # Before advancing any private generator or SQLite call.
        if self._busy or self._phase not in {"active", "closed"}:
            raise _invalid()
        if self._phase == "closed":
            return False
        self._busy = True
        try:
            if kind is None:
                try:
                    self._inventory(entering=False)
                    self._checkpoint()
                    summary = {**asdict(self.snapshot), "source_digest": self._catalog.source_digest,
                        "graph_hash": self._catalog.graph_hash, "verified_source_files": len(self._entries),
                        "verified_derived_files": len(self._document["derived_inputs"]),
                        "verified_total_bytes": self._used, "resident_image_accounting": self._resident_peak,
                        "inventory_checks": "entry_postcopy_exit", "expected_bytes_protected": "private_verified_copies",
                        "temporal_atomicity": "not_proven"}
                except BaseException:
                    self._cleanup(sys.exc_info())
                    raise
            self._cleanup((kind, value, traceback))
            if kind is None:
                self._deadline_check()
                self._summary = summary
            return False
        finally:
            self._busy = False

    @property
    def validation_summary(self):
        self._owner_check()
        if self._summary is None or self._busy:
            raise _invalid()
        return dict(self._summary)
