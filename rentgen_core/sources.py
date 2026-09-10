"""Authorized capabilities over one published immutable generation (Windows)."""
import base64
from contextlib import contextmanager, closing, ExitStack
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import sqlite3
import sys
from threading import get_ident
from time import monotonic
from typing import Literal

from .context import SnapshotRef
from .errors import CoreError
from .manifests import CapturedInput, canonical_bytes, parse_manifest, sha256, _decode
from .source_paths import validate_source_path
from .source_catalog import source_query, selected_entries

_MAX_MANIFEST = 64 * 1024 * 1024
_MAX_GRAPH = 1024 * 1024 * 1024
_MAX_DERIVED = 128 * 1024 * 1024

# Independent schema-2 read contract. Do not import a concrete builder to decide
# whether an injected artifact is safe to advertise as an available graph.
_GRAPH_COLUMNS = {
    "meta": "key value",
    "module": "name object_name module_kind n_subs n_export n_functions avg_complexity max_complexity sum_complexity fan_in fan_out display_name display_key source_path source_key source_provenance common_key",
    "subroutine": "id name module line is_export is_function complexity name_key source_path end_line declaration_ambiguous source_provenance",
    "call_edge": "caller_id callee_id line tier site_id",
    "module_edge": "src dst weight",
    "call_site": "id caller_id callee_id target line column end_line end_column kind span_provenance reason declaration_line",
    "quality": "module_path module_type domain loc complexity_score documentation_score maintainability_score code_quality has_n_plus_one has_select_star has_empty_catch has_deep_nesting has_magic_numbers num_todo_fixme object_name module_kind fan_in fan_out module_id source_key",
}
_GRAPH_COUNTS = {
    "module": "n_modules",
    "subroutine": "n_subroutines",
    "call_edge": "n_call_edges",
    "module_edge": "n_module_edges",
    "call_site": "n_call_sites",
    "quality": "n_quality",
}
_GRAPH_PRIMARY_KEYS = {
    "meta": ["key"],
    "module": ["name"],
    "subroutine": ["id"],
    "call_site": ["id"],
    "quality": ["module_path"],
    "module_edge": ["src", "dst"],
    "call_edge": [],
}
_GRAPH_FOREIGN_KEYS = {
    "meta": set(),
    "module": set(),
    "subroutine": {("module", "module", "name")},
    "call_edge": {
        ("caller_id", "subroutine", "id"),
        ("callee_id", "subroutine", "id"),
        ("site_id", "call_site", "id"),
    },
    "call_site": {("caller_id", "subroutine", "id"), ("callee_id", "subroutine", "id")},
    "module_edge": {("src", "module", "name"), ("dst", "module", "name")},
    "quality": {("module_id", "module", "name")},
}


def _corrupt(message="Published generation is corrupt"):
    return CoreError("SNAPSHOT_CORRUPT", message)


def _read(path, maximum):
    from ._windows_source_tree import read_retained

    try:
        return read_retained(path, maximum)
    except (OSError, CoreError) as exc:
        if isinstance(exc, CoreError) and exc.code == "CAPTURE_PLATFORM_UNSUPPORTED":
            raise
        raise _corrupt("Retained file is unavailable") from exc


def _manifest(path, snapshot):
    raw = _read(path / "manifest.json", _MAX_MANIFEST)
    if sha256(raw) != snapshot.manifest_hash:
        raise _corrupt("Manifest digest does not match publication")
    document = parse_manifest(raw)
    if document["project_id"] != snapshot.project_id:
        raise _corrupt("Manifest project does not match publication")
    _verify_inventory(path, document)
    return document


def _verify_inventory(path, document):
    """Enumerate held directory handles; unknown paths never cause content IO."""
    from ._windows_source_tree import WindowsHandleOps, pinned_directory

    expected = {"manifest.json", "graph.sqlite3"}
    expected.update(entry["relative_path"] for entry in document["derived_inputs"])
    expected.update(
        "sources/" + entry["layer_id"] + "/" + entry["relative_path"]
        for entry in document["source"]["entries"]
    )
    ops = WindowsHandleOps()
    found, count = set(), 0
    try:
        with ExitStack() as pins:
            pins.enter_context(pinned_directory(path))
            pending = [(path, None)]
            while pending:
                directory, enumerated = pending.pop()
                handle = ops.open(directory, directory=True)
                pins.callback(ops.close, handle)
                actual = ops.stamp(handle)
                if (
                    not actual.directory
                    or ops.final_path(handle) != directory
                    or (
                        enumerated is not None
                        and actual.identity != enumerated.identity
                    )
                ):
                    raise _corrupt("Generation directory changed during inventory")
                for name, stamp in ops.enumerate(handle):
                    count += 1
                    if count > 200_000:
                        raise _corrupt("Generation inventory exceeds resource limit")
                    child = directory / name
                    if stamp.directory:
                        pending.append((child, stamp))
                    else:
                        relative = child.relative_to(path).as_posix()
                        if relative not in expected or relative in found:
                            raise _corrupt("Generation contains an unlisted file")
                        found.add(relative)
            if found != expected:
                raise _corrupt("Generation file inventory does not match manifest")
    except (OSError, CoreError) as exc:
        if isinstance(exc, CoreError) and exc.code == "CAPTURE_PLATFORM_UNSUPPORTED":
            raise
        raise _corrupt("Generation inventory is unavailable or invalid") from exc


def _bindings(document):
    return sorted(
        [
            dict(
                entry,
                graph_source_path=entry["layer_id"] + "/" + entry["relative_path"],
            )
            for entry in document["source"]["entries"]
            if Path(entry["relative_path"]).suffix.lower() in (".bsl", ".os", ".bsp")
        ],
        key=lambda entry: entry["graph_source_path"].encode("utf-8"),
    )


@contextmanager
def _graph_metadata(path, document=None):
    """Keep no-follow read-only leaf/ancestor pins through every SQLite handle."""
    from ._windows_source_tree import pinned_retained

    try:
        with pinned_retained(path, _MAX_GRAPH) as raw:
            _reject_sidecars(path)
            with closing(
                sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
            ) as db:
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise _corrupt("Graph integrity check failed")
                if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise _corrupt("Graph foreign key check failed")
                meta = dict(db.execute("SELECT key,value FROM meta"))
                _validate_graph_structure(db, meta, document)
                yield raw, meta
            _reject_sidecars(path)
    except (OSError, sqlite3.Error) as exc:
        raise _corrupt("Graph is unavailable or invalid") from exc


def _validate_graph_structure(db, meta, document):
    tables = {
        row[0]
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if not _GRAPH_COLUMNS.keys() <= tables:
        raise _corrupt("Graph schema is missing required tables")
    for table, required in _GRAPH_COLUMNS.items():
        info = db.execute("PRAGMA table_info(" + table + ")").fetchall()
        columns = {row[1] for row in info}
        if not set(required.split()) <= columns:
            raise _corrupt("Graph schema is missing required columns")
        primary = [row[1] for row in sorted(info, key=lambda row: row[5]) if row[5]]
        foreign = {
            (row[3], row[2], row[4])
            for row in db.execute("PRAGMA foreign_key_list(" + table + ")")
        }
        if (
            primary != _GRAPH_PRIMARY_KEYS[table]
            or foreign != _GRAPH_FOREIGN_KEYS[table]
        ):
            raise _corrupt("Graph schema key constraints do not match schema 2")
    for table, key in _GRAPH_COUNTS.items():
        actual = db.execute("SELECT count(*) FROM " + table).fetchone()[0]
        if meta.get(key) != str(actual):
            raise _corrupt("Graph row counts do not match provenance")
    if meta.get("n_quality") != "0" or meta.get("quality") != "unavailable":
        raise _corrupt("Snapshot graph must not fabricate quality availability")
    if document is not None:
        expected = [entry["graph_source_path"] for entry in _bindings(document)]
        actual = [row[0] for row in db.execute("SELECT source_path FROM module")]
        if len(actual) != len(expected) or set(actual) != set(expected):
            raise _corrupt("Graph modules do not match captured source paths")
        if (
            db.execute(
                "SELECT 1 FROM subroutine s JOIN module m ON m.name=s.module WHERE s.source_path IS NOT m.source_path LIMIT 1"
            ).fetchone()
            is not None
        ):
            raise _corrupt("Graph declarations do not match their source modules")


def _reject_sidecars(path):
    for suffix in ("-wal", "-shm", "-journal"):
        if path.with_name(path.name + suffix).exists():
            raise _corrupt("Immutable graph has a journal sidecar")


def _verify_graph(raw, meta, document):
    _verify_graph_digest(sha256(raw), meta, document)


def _verify_graph_digest(digest, meta, document):
    graph = document["graph"]
    if digest != graph["raw_sha256"]:
        raise _corrupt("Graph digest mismatch")
    for key, value in graph.items():
        if key not in ("relative_path", "raw_sha256") and meta.get(key) != value:
            raise _corrupt("Graph provenance does not match manifest")
    if sha256(canonical_bytes(_bindings(document))) != graph["input_binding_hash"]:
        raise _corrupt("Graph input binding does not match source entries")


def verify_generation(path, catalog):
    """Verify every retained artifact before publishing or issuing capabilities."""
    document = _manifest(path, catalog.snapshot)
    if (
        document["source_digest"] != catalog.source_digest
        or document["graph"]["raw_sha256"] != catalog.graph_hash
    ):
        raise _corrupt("Catalog content binding does not match manifest")
    for entry in document["source"]["entries"]:
        raw = _read(
            path / "sources" / entry["layer_id"] / entry["relative_path"],
            entry["size_bytes"],
        )
        if len(raw) != entry["size_bytes"] or sha256(raw) != entry["raw_sha256"]:
            raise _corrupt("Retained source digest mismatch")
    for entry in document["derived_inputs"]:
        if entry["size_bytes"] > _MAX_DERIVED:
            raise _corrupt("Derived input exceeds resource limit")
        raw = _read(path / entry["relative_path"], entry["size_bytes"])
        if len(raw) != entry["size_bytes"] or sha256(raw) != entry["raw_sha256"]:
            raise _corrupt("Derived input digest mismatch")
    with _graph_metadata(path / "graph.sqlite3", document) as (raw, meta):
        _verify_graph(raw, meta, document)
    _verify_inventory(path, document)
    return document


@dataclass(frozen=True)
class SourceRef:
    snapshot: SnapshotRef
    layer_id: str
    relative_path: str
    raw_sha256: str

    def __post_init__(self):
        if not isinstance(self.snapshot, SnapshotRef):
            raise CoreError(
                "SOURCE_REF_MISMATCH", "A pinned snapshot reference is required"
            )
        CapturedInput(self.layer_id, self.relative_path, self.raw_sha256, 0, None)


@dataclass(frozen=True)
class SourceEntry:
    ref: SourceRef
    size_bytes: int
    encoding: str | None
    identity_status: Literal["unresolved"] = "unresolved"


@dataclass(frozen=True)
class SourcePage:
    entries: tuple[SourceEntry, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class SnapshotCapabilities:
    source_bytes: Literal["available"] = "available"
    graph: Literal["available"] = "available"
    quality: Literal["unavailable"] = "unavailable"
    identity: Literal["source_path_only"] = "source_path_only"
    capture_method: Literal[
        "working_tree_verified_passes_v1"
    ] = "working_tree_verified_passes_v1"
    temporal_atomicity: Literal["not_proven"] = "not_proven"
    semantic_scope: str = (
        "bounded_static_calls; preprocessing and dynamic types unresolved"
    )


@dataclass(frozen=True)
class SnapshotSources:
    snapshot: SnapshotRef
    _state: object
    _principal: object
    _path: Path

    def read_session(self, *, limits):
        """Create a one-operation owner; entry authorizes and pins all artifacts."""
        return SnapshotReadSession(self, limits)

    def _document(self):
        with self._state.transaction(self._principal) as tx:
            tx.require_all({"project:read"})
            catalog = tx.get_snapshot(self.snapshot.snapshot_id)
        if catalog.snapshot != self.snapshot:
            raise _corrupt()
        return _manifest(self._path, self.snapshot)

    def _entry(self, ref, document):
        if not isinstance(ref, SourceRef) or ref.snapshot != self.snapshot:
            raise CoreError(
                "SOURCE_REF_MISMATCH", "Source reference belongs to another snapshot"
            )
        for entry in document["source"]["entries"]:
            if (entry["layer_id"], entry["relative_path"]) == (
                ref.layer_id,
                ref.relative_path,
            ):
                if entry["raw_sha256"] != ref.raw_sha256:
                    raise CoreError(
                        "SOURCE_REF_MISMATCH", "Source reference hash does not match"
                    )
                return entry
        raise CoreError("SOURCE_NOT_FOUND", "Source is absent from this snapshot")

    def resolve(self, layer_id, relative_path):
        document = self._document()
        validate_source_path(relative_path)
        for entry in document["source"]["entries"]:
            if (entry["layer_id"], entry["relative_path"]) == (layer_id, relative_path):
                return SourceRef(
                    self.snapshot, layer_id, relative_path, entry["raw_sha256"]
                )
        raise CoreError("SOURCE_NOT_FOUND", "Source is absent from this snapshot")

    def read_source(self, ref):
        entry = self._entry(ref, self._document())
        raw = _read(
            self._path / "sources" / ref.layer_id / ref.relative_path,
            entry["size_bytes"],
        )
        if len(raw) != entry["size_bytes"] or sha256(raw) != ref.raw_sha256:
            raise _corrupt("Retained source digest mismatch")
        return raw

    def list_entries(self, *, limit=100, cursor=None, query="", kind="all", layer=None):
        document = self._document()
        filters = source_query(query=query, kind=kind, layer=layer)
        if type(limit) is not int or not 1 <= limit <= 200:
            raise CoreError("INVALID_QUERY_OPTIONS", "Source page limit must be 1..200")
        entries = selected_entries(document, filters)
        ordinals = {
            layer["layer_id"]: layer["ordinal"]
            for layer in document["source"]["layers"]
        }
        binding = {
            "version": 1,
            "project_id": self.snapshot.project_id,
            "snapshot_id": self.snapshot.snapshot_id,
            "limit": limit,
        }
        if filters != {"query": "", "kind": "all", "layer": None}:
            binding.update(
                version=2, filters=filters, manifest_hash=self.snapshot.manifest_hash
            )
        start = 0
        if cursor is not None:
            try:
                if not isinstance(cursor, str) or len(cursor) > 8192:
                    raise ValueError()
                decoded = _decode(
                    base64.b64decode(cursor, altchars=b"-_", validate=True)
                )
                if (
                    not isinstance(decoded, dict)
                    or type(decoded.get("version")) is not int
                    or type(decoded.get("limit")) is not int
                ):
                    raise ValueError()
                last = decoded.pop("last")
                if (
                    decoded != binding
                    or type(last) is not list
                    or len(last) != 2
                    or type(last[0]) is not int
                ):
                    raise ValueError()
                matches = [
                    i
                    for i, entry in enumerate(entries)
                    if [ordinals[entry["layer_id"]], entry["relative_path"]] == last
                ]
                if len(matches) != 1:
                    raise ValueError()
                start = matches[0] + 1
            except (ValueError, KeyError, TypeError, CoreError) as exc:
                raise CoreError(
                    "INVALID_SOURCE_CURSOR",
                    "Cursor does not match this snapshot, page size and filters",
                ) from exc
        page = entries[start : start + limit]
        next_cursor = None
        if start + len(page) < len(entries):
            last = page[-1]
            next_cursor = base64.urlsafe_b64encode(
                canonical_bytes(
                    dict(
                        binding,
                        last=[ordinals[last["layer_id"]], last["relative_path"]],
                    )
                )
            ).decode("ascii")
        return SourcePage(
            tuple(
                SourceEntry(
                    SourceRef(
                        self.snapshot,
                        e["layer_id"],
                        e["relative_path"],
                        e["raw_sha256"],
                    ),
                    e["size_bytes"],
                    e["encoding"],
                )
                for e in page
            ),
            next_cursor,
        )


@dataclass(frozen=True)
class SnapshotReadLimits:
    """Hard bounds; Win32 handles are counted separately from one SQLite connection."""

    max_source_entries: int = 20_000
    max_open_handles: int = 65_536
    max_inventory_items: int = 200_000
    max_manifest_bytes: int = _MAX_MANIFEST
    max_total_verified_bytes: int = 2560 * 1024 * 1024
    deadline_seconds: int = 30

    def __post_init__(self):
        maxima = (20_000, 65_536, 200_000, _MAX_MANIFEST, 2560 * 1024 * 1024, 30)
        if any(
            type(value) is not int or not 1 <= value <= maximum
            for value, maximum in zip(asdict(self).values(), maxima)
        ):
            raise CoreError(
                "INVALID_QUERY_OPTIONS",
                "Read session limits must be positive and bounded",
            )


class SnapshotReadSession:
    """One synchronous operation over held expected bytes and boundary inventories.

    Temporary unlisted files between observations are not claimed detected.
    This object is an internal capability, never a transport-selected locator.
    """

    def __init__(self, sources, limits):
        if not isinstance(limits, SnapshotReadLimits):
            raise CoreError(
                "INVALID_QUERY_OPTIONS", "Typed read session limits required"
            )
        self._sources, self._limits = sources, limits
        self._phase = "new"
        self._owner = None
        self._handles = []
        self._pins = {}
        self._used = 0
        self._broken = False
        self._success = False
        self._busy = False

    @staticmethod
    def _invalid():
        return CoreError(
            "SNAPSHOT_READ_SESSION_INVALID", "Read session is not active on this thread"
        )

    def _limit(self):
        raise CoreError(
            "SNAPSHOT_READ_LIMIT_EXCEEDED", "Read session resource limit exceeded"
        )

    def _deadline_check(self):
        if monotonic() >= self._deadline:
            raise CoreError(
                "SNAPSHOT_READ_DEADLINE_EXCEEDED", "Read session deadline exceeded"
            )

    def checkpoint(self):
        """Metadata checks before/after parsing and materializing private results."""
        if self._phase != "active" or self._owner != get_ident() or self._busy:
            raise self._invalid()
        self._deadline_check()

    @contextmanager
    def _operation(self):
        self.checkpoint()
        self._busy = True
        try:
            yield
        finally:
            self._busy = False

    def _authorize(self):
        self._deadline_check()
        source = self._sources
        with source._state.transaction(source._principal) as tx:
            tx.require_all({"project:read"})
            catalog = tx.get_snapshot(source.snapshot.snapshot_id)
        if catalog.snapshot != source.snapshot:
            raise _corrupt("Read session catalog identity changed")
        if hasattr(self, "_catalog") and catalog != self._catalog:
            raise _corrupt("Read session catalog binding changed")
        self._deadline_check()
        return catalog

    @contextmanager
    def _retained_errors(self):
        try:
            yield
        except CoreError as exc:
            if exc.code.startswith("SOURCE_") and exc.code not in {
                "SOURCE_REF_MISMATCH",
                "SOURCE_NOT_FOUND",
            }:
                raise _corrupt("Retained session artifact is unavailable") from exc
            raise
        except (OSError, sqlite3.Error) as exc:
            self._deadline_check()
            raise _corrupt(
                "Retained session artifact is unavailable or invalid"
            ) from exc

    def _open(self, path, *, directory):
        from ._windows_source_tree import _retained_stamp

        self._deadline_check()
        if len(self._handles) >= self._limits.max_open_handles:
            self._limit()
        handle = self._ops.open(path, directory=directory)
        self._handles.append(handle)
        stamp = (
            self._ops.stamp(handle) if directory else _retained_stamp(self._ops, handle)
        )
        if stamp.directory != directory or self._ops.final_path(handle) != path:
            raise _corrupt("Retained session path identity mismatch")
        self._deadline_check()
        return handle, stamp

    def _close_from(self, start, *, preserve):
        # Every acquired handle gets one close attempt. A lost acknowledgement is
        # not permission to retry a possibly recycled native handle value.
        failure = None
        for handle in reversed(self._handles[start:]):
            try:
                self._ops.close(handle)
            except BaseException as exc:
                failure = failure or exc
        del self._handles[start:]
        if failure is not None:
            self._broken = True
            if not preserve:
                if not isinstance(failure, Exception):
                    raise failure
                raise _corrupt("Retained session cleanup failed") from failure

    def _cleanup(self, *, preserve):
        self._phase = "closed"
        self._close_from(0, preserve=preserve)

    def __enter__(self):
        from ._windows_source_tree import WindowsHandleOps, _require_local_path

        if self._phase != "new":
            raise self._invalid()
        self._phase, self._owner = "entering", get_ident()
        self._deadline = monotonic() + self._limits.deadline_seconds
        try:
            self._catalog = self._authorize()
            with self._retained_errors():
                self._ops = WindowsHandleOps()
                path = self._sources._path
                _require_local_path(self._ops, path)
                for ancestor in (*reversed(path.parents), path):
                    self._pins[ancestor] = self._open(ancestor, directory=True)
                manifest = path / "manifest.json"
                self._pins[manifest] = self._open(manifest, directory=False)
                if self._pins[manifest][1].size > self._limits.max_manifest_bytes:
                    self._limit()
                raw, digest = self._stream(
                    manifest, self._limits.max_manifest_bytes, materialize=True
                )
                if digest != self._sources.snapshot.manifest_hash:
                    raise _corrupt("Manifest digest does not match publication")
                self._document = parse_manifest(raw)
                del raw
                self._deadline_check()
                self._prepare()
                self._inventory(entering=True)
                self._validate_all()
                self._authorize()
            self._phase = "active"
            return self
        except BaseException:
            self._cleanup(preserve=True)
            raise

    def _prepare(self):
        doc = self._document
        if (
            doc["project_id"] != self._sources.snapshot.project_id
            or doc["source_digest"] != self._catalog.source_digest
            or doc["graph"]["raw_sha256"] != self._catalog.graph_hash
        ):
            raise _corrupt("Catalog content binding does not match manifest")
        entries = doc["source"]["entries"]
        if len(entries) > self._limits.max_source_entries:
            self._limit()
        sizes = [entry["size_bytes"] for entry in entries]
        if (
            any(size > 64 * 1024 * 1024 for size in sizes)
            or sum(sizes) > 1024 * 1024 * 1024
        ):
            self._limit()
        derived = doc["derived_inputs"]
        if any(entry["size_bytes"] > _MAX_DERIVED for entry in derived):
            self._limit()
        if (
            self._used + sum(sizes) + sum(entry["size_bytes"] for entry in derived)
            > self._limits.max_total_verified_bytes
        ):
            self._limit()
        self._expected = {"manifest.json", "graph.sqlite3"}
        self._expected.update(entry["relative_path"] for entry in derived)
        self._expected.update(
            "sources/" + entry["layer_id"] + "/" + entry["relative_path"]
            for entry in entries
        )
        if len(self._expected) + len(self._handles) - 1 > self._limits.max_open_handles:
            self._limit()
        self._entries = tuple(
            SourceEntry(
                SourceRef(
                    self._sources.snapshot,
                    entry["layer_id"],
                    entry["relative_path"],
                    entry["raw_sha256"],
                ),
                entry["size_bytes"],
                entry["encoding"],
            )
            for entry in entries
        )
        self._index = {
            (entry.ref.layer_id, entry.ref.relative_path): entry
            for entry in self._entries
        }

    def _inventory(self, *, entering):
        root = self._sources._path
        pending, found, count = [root], set(), 0
        while pending:
            self._deadline_check()
            directory = pending.pop()
            handle, before = self._pins[directory]
            actual = self._ops.stamp(handle)
            if (
                actual.identity != before.identity
                or not actual.directory
                or self._ops.final_path(handle) != directory
            ):
                raise _corrupt("Retained directory identity changed")
            for name, enumerated in self._ops.enumerate(handle):
                self._deadline_check()
                count += 1
                if count > self._limits.max_inventory_items:
                    self._limit()
                child = directory / name
                if not enumerated.directory:
                    relative = child.relative_to(root).as_posix()
                    if relative not in self._expected or relative in found:
                        raise _corrupt("Generation contains an unlisted file")
                    found.add(relative)
                if child not in self._pins:
                    if not entering and not enumerated.directory:
                        raise _corrupt("Generation expected file lost its pin")
                    self._pins[child] = self._open(
                        child, directory=enumerated.directory
                    )
                _, held = self._pins[child]
                if (
                    held.identity != enumerated.identity
                    or held.directory != enumerated.directory
                ):
                    raise _corrupt("Generation entry changed during inventory")
                if enumerated.directory:
                    pending.append(child)
        if found != self._expected:
            raise _corrupt("Generation file inventory does not match manifest")

    def _stream(self, path, maximum, *, materialize=False, exact=None, full=True):
        from ._windows_source_tree import _retained_stamp

        self._authorize()
        handle, before = self._pins[path]
        if before.size > maximum or (exact is not None and before.size != exact):
            raise _corrupt("Retained file size mismatch")
        size, digest = 0, hashlib.sha256()
        raw = bytearray() if materialize else None
        for chunk in self._ops.chunks(handle):
            self._deadline_check()
            size += len(chunk)
            if size > maximum:
                raise _corrupt("Retained file exceeds size bound")
            if full:
                self._used += len(chunk)
                if self._used > self._limits.max_total_verified_bytes:
                    self._limit()
            digest.update(chunk)
            if raw is not None:
                raw.extend(chunk)
        if size != before.size or _retained_stamp(self._ops, handle) != before:
            raise _corrupt("Retained bytes changed during read")
        self._deadline_check()
        return (bytes(raw) if raw is not None else None), digest.hexdigest()

    def _validate_all(self):
        path = self._sources._path
        for entry in self._document["source"]["entries"]:
            _, digest = self._stream(
                path / "sources" / entry["layer_id"] / entry["relative_path"],
                entry["size_bytes"],
                exact=entry["size_bytes"],
            )
            if digest != entry["raw_sha256"]:
                raise _corrupt("Retained source digest mismatch")
        for entry in self._document["derived_inputs"]:
            _, digest = self._stream(
                path / entry["relative_path"],
                entry["size_bytes"],
                exact=entry["size_bytes"],
            )
            if digest != entry["raw_sha256"]:
                raise _corrupt("Derived input digest mismatch")
        graph = path / "graph.sqlite3"
        _, digest = self._stream(graph, _MAX_GRAPH)
        self._validate_sqlite(graph, digest)

    def _validate_sqlite(self, path, digest):
        self._authorize()
        _reject_sidecars(path)
        db = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            db.set_progress_handler(lambda: int(monotonic() >= self._deadline), 1000)
            if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise _corrupt("Graph integrity check failed")
            if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise _corrupt("Graph foreign key check failed")
            meta = dict(db.execute("SELECT key,value FROM meta"))
            _validate_graph_structure(db, meta, self._document)
            _verify_graph_digest(digest, meta, self._document)
            self._deadline_check()
        finally:
            active = sys.exc_info()[0] is not None
            try:
                db.close()
            except BaseException:
                if not active:
                    raise
        _reject_sidecars(path)

    def entries(self):
        with self._operation():
            self._authorize()
            return self._entries

    def read_source(self, ref):
        with self._operation(), self._retained_errors():
            self._authorize()
            if not isinstance(ref, SourceRef) or ref.snapshot != self._sources.snapshot:
                raise CoreError(
                    "SOURCE_REF_MISMATCH",
                    "Source reference belongs to another snapshot",
                )
            entry = self._index.get((ref.layer_id, ref.relative_path))
            if entry is None:
                raise CoreError(
                    "SOURCE_NOT_FOUND", "Source is absent from this snapshot"
                )
            if ref != entry.ref:
                raise CoreError(
                    "SOURCE_REF_MISMATCH", "Source reference hash does not match"
                )
            path = self._sources._path / "sources" / ref.layer_id / ref.relative_path
            # Count the complete transient ancestor chain before opening any of it.
            if (
                len(self._handles) + len(path.parents) + 1
                > self._limits.max_open_handles
            ):
                self._limit()
            start, original = len(self._handles), self._pins[path]
            try:
                for ancestor in reversed(path.parents):
                    self._open(ancestor, directory=True)
                transient = self._open(path, directory=False)
                if transient[1] != original[1]:
                    raise _corrupt("Retained source identity changed")
                self._pins[path] = transient
                raw, digest = self._stream(
                    path,
                    entry.size_bytes,
                    materialize=True,
                    exact=entry.size_bytes,
                    full=False,
                )
                if digest != ref.raw_sha256:
                    raise _corrupt("Retained source digest mismatch")
                return raw
            finally:
                self._pins[path] = original
                self._close_from(start, preserve=sys.exc_info()[0] is not None)

    def __exit__(self, exc_type, exc, traceback):
        from ._windows_source_tree import _retained_stamp

        if self._phase != "active" or self._owner != get_ident() or self._busy:
            raise self._invalid()
        try:
            if exc_type is None:
                with self._retained_errors():
                    if self._broken:
                        raise _corrupt("Read session cleanup was incomplete")
                    self._inventory(entering=False)
                    for path, (handle, before) in self._pins.items():
                        self._deadline_check()
                        after = (
                            self._ops.stamp(handle)
                            if before.directory
                            else _retained_stamp(self._ops, handle)
                        )
                        if self._ops.final_path(handle) != path or (
                            after.identity != before.identity
                            if before.directory
                            else after != before
                        ):
                            raise _corrupt("Retained identity changed during session")
                    self._authorize()
        except BaseException:
            self._cleanup(preserve=True)
            raise
        self._cleanup(preserve=exc_type is not None)
        if exc_type is None:
            self._deadline_check()
            self._success = True
        return False

    @property
    def validation_summary(self):
        if not self._success or self._owner != get_ident():
            raise self._invalid()
        return {
            **asdict(self._sources.snapshot),
            "source_digest": self._catalog.source_digest,
            "graph_hash": self._catalog.graph_hash,
            "verified_source_files": len(self._entries),
            "verified_derived_files": len(self._document["derived_inputs"]),
            "verified_source_bytes": sum(entry.size_bytes for entry in self._entries),
            "verified_total_bytes": self._used,
            "all_expected_files_verified": True,
            "inventory_checks": "entry_exit",
            "expected_bytes_protected": "retained_handles",
            "temporal_namespace_atomicity": "not_proven",
        }


@dataclass(frozen=True)
class SnapshotGraph:
    snapshot: SnapshotRef
    _sources: SnapshotSources
    _factory: object
    capabilities: SnapshotCapabilities = SnapshotCapabilities()

    def _query(self, ref, depth=None):
        document = self._sources._document()
        self._sources._entry(ref, document)
        # Detect source damage as well as graph damage; never reread the live tree.
        self._sources.read_source(ref)
        if depth is not None and (type(depth) is not int or not 1 <= depth <= 5):
            raise CoreError("INVALID_QUERY_OPTIONS", "Impact depth must be 1..5")
        path = self._sources._path / "graph.sqlite3"
        with _graph_metadata(path, document) as (raw, meta):
            _verify_graph(raw, meta, document)
            reader = self._factory.open(graph_path=path, snapshot=self.snapshot)
            locator = ref.layer_id + "/" + ref.relative_path
            result = (
                reader.resolve_module(locator)
                if depth is None
                else reader.module_impact(locator, max_depth=depth, max_edges=600)
            )
        return dict(
            project_id=self.snapshot.project_id,
            snapshot_id=self.snapshot.snapshot_id,
            manifest_hash=self.snapshot.manifest_hash,
            capabilities=asdict(self.capabilities),
            result=result,
        )

    def resolve_module(self, ref):
        return self._query(ref)

    def impact(self, ref, *, depth=1):
        if type(depth) is not int or not 1 <= depth <= 5:
            # Authorization still precedes rejection of public query options.
            self._sources._document()
            raise CoreError("INVALID_QUERY_OPTIONS", "Impact depth must be 1..5")
        return self._query(ref, depth)


def read_source(ctx, ref):
    from .resolver import require_snapshot

    require_snapshot(ctx)
    if ctx.sources is None:
        raise CoreError("SNAPSHOT_REQUIRED", "Snapshot sources are unavailable")
    return ctx.sources.read_source(ref)
