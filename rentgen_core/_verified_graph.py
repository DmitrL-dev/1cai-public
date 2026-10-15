"""Internal byte-owned graph queries; no pathname, filesystem lease or OS admission."""
from dataclasses import dataclass
import json
import os
import sqlite3
from threading import get_ident
from time import monotonic

from .context import SnapshotRef
from .errors import CoreError
from .manifests import parse_manifest, sha256
from .sources import (
    _MAX_GRAPH, _MAX_MANIFEST, _bindings, _corrupt,
    _validate_graph_structure, _verify_graph_digest,
)

_NO_TRAVERSAL = object()


@dataclass(frozen=True)
class VerifiedGraphLimits:
    # Required opt-in: caller-owned bytes plus SQLite's one native image copy.
    image_buffer_budget: int
    max_graph_bytes: int = _MAX_GRAPH
    max_row_bytes: int = 64 * 1024**2
    max_result_bytes: int = 16 * 1024**2
    max_value_bytes: int = 1024**2
    cache_kib: int = 8192
    max_vm_steps: int = 10_000_000
    max_open_cursors: int = 16
    deadline_seconds: int = 30

    def __post_init__(self):
        maxima = {
            "image_buffer_budget": 2 * _MAX_GRAPH,
            "max_graph_bytes": _MAX_GRAPH,
            "max_row_bytes": _MAX_GRAPH,
            "max_result_bytes": 64 * 1024**2,
            "max_value_bytes": 16 * 1024**2,
            "cache_kib": 65536,
            "max_vm_steps": 100_000_000,
            "max_open_cursors": 64,
            "deadline_seconds": 30,
        }
        for key, maximum in maxima.items():
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= maximum:
                raise CoreError("INVALID_QUERY_OPTIONS", "Invalid verified graph limits")


def _invalid():
    return CoreError("SNAPSHOT_READ_SESSION_INVALID", "Verified graph reader is not active on its owner")


def _limit():
    return CoreError("SNAPSHOT_READ_LIMIT_EXCEEDED", "Verified graph read exceeds its resource budget")


class _Rows:
    """Charge rows before accumulating them; never expose a native cursor."""
    def __init__(self, owner, cursor):
        self._owner, self._cursor = owner, cursor

    def _next(self):
        self._owner._checkpoint()
        if self._cursor is None:
            return None
        row = self._owner._sql(self._cursor.fetchone)
        if row is not None:
            cost = 128 + 16 * len(row)
            for value in row:
                if isinstance(value, str):
                    cost += 64 + 4 * len(value.encode("utf-8"))
                elif isinstance(value, bytes):
                    cost += 64 + len(value)
                else:
                    cost += 32
            self._owner._row_bytes += cost
            if self._owner._row_bytes > self._owner._limits.max_row_bytes:
                raise _limit()
        return row

    def close(self, *, preserve=False):
        cursor, self._cursor = self._cursor, None
        self._owner._rows.discard(self)
        if cursor is not None:
            try:
                cursor.close()
            except BaseException as exc:
                self._owner._cursor_failure = exc
                if not preserve:
                    raise

    def fetchone(self):
        # This private one-row operation terminates its statement, even on a hit.
        try:
            row = self._next()
        except BaseException:
            self.close(preserve=True)
            raise
        self.close()
        return row

    def __iter__(self):
        try:
            while (row := self._next()) is not None:
                yield row
        except BaseException:
            self.close(preserve=True)
            raise
        else:
            self.close()

    def fetchall(self):
        return list(self)


class _Queries:
    """Private adapter view; fixed graph methods are the only caller-facing API."""
    def __init__(self, owner):
        self._owner = owner

    def execute(self, statement, parameters=()):
        self._owner._checkpoint()
        if len(self._owner._rows) >= self._owner._limits.max_open_cursors:
            raise _limit()
        cursor = self._owner._sql(lambda: self._owner._db.execute(statement, parameters))
        try:
            rows = _Rows(self._owner, cursor)
            self._owner._rows.add(rows)
            return rows
        except BaseException:
            try:
                cursor.close()
            except BaseException:
                pass
            raise


class _VerifiedGraph:
    def __init__(self, raw, manifest, *, snapshot, authorize_read, limits):
        if (type(limits) is not VerifiedGraphLimits or type(snapshot) is not SnapshotRef
                or not callable(authorize_read)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed graph limits, snapshot and authorization are required")
        self._raw, self._manifest = raw, manifest
        self._snapshot, self._authorize, self._limits = snapshot, authorize_read, limits
        self._phase, self._db, self._busy = "new", None, False
        self._pending = None
        self._cursor_failure = None
        self._rows = set()
        self._row_bytes = 0
        self._steps = 0
        self._queries = _Queries(self)

    def _checkpoint(self):
        if self._phase not in {"entering", "active"} or self._owner != (os.getpid(), get_ident()):
            raise _invalid()
        if self._cursor_failure is not None:
            raise _corrupt("Verified graph statement cleanup failed")
        if monotonic() >= self._deadline:
            raise CoreError("SNAPSHOT_READ_DEADLINE_EXCEEDED", "Verified graph deadline exceeded")
        self._authorize()
        if monotonic() >= self._deadline:
            raise CoreError("SNAPSHOT_READ_DEADLINE_EXCEEDED", "Verified graph deadline exceeded")

    def _progress(self):
        if self._pending is not None:
            return 1  # SQLite may call again while unwinding the first interrupt.
        try:
            self._steps += self._quantum
            if self._steps >= self._limits.max_vm_steps:
                raise _limit()
            self._checkpoint()
        except BaseException as exc:
            self._pending = exc
            return 1
        return 0

    @staticmethod
    def _policy(action, first, second, database, trigger):
        if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_RECURSIVE}:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and second in {
            "count", "min", "length", "substr", "identifier_key",
        }:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_PRAGMA and first in {
            "integrity_check", "foreign_key_check", "table_info", "foreign_key_list",
        }:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    def _sql(self, operation):
        try:
            return operation()
        except sqlite3.Error as exc:
            if self._pending is not None:
                original, self._pending = self._pending, None
                raise original
            self._checkpoint()
            if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_TOOBIG:
                raise _limit() from exc
            raise _corrupt("Verified graph query is unavailable or invalid") from exc

    def __enter__(self):
        if self._phase != "new":
            raise _invalid()
        self._phase, self._owner = "entering", (os.getpid(), get_ident())
        self._deadline = monotonic() + self._limits.deadline_seconds
        try:
            self._checkpoint()
            raw, manifest = self._raw, self._manifest
            if type(raw) is not bytes or type(manifest) is not bytes:
                raise CoreError("INVALID_QUERY_OPTIONS", "Immutable graph and manifest bytes are required")
            if (len(raw) > self._limits.max_graph_bytes
                    or 2 * len(raw) > self._limits.image_buffer_budget
                    or len(manifest) > _MAX_MANIFEST):
                raise _limit()
            if sha256(manifest) != self._snapshot.manifest_hash:
                raise _corrupt("Manifest digest does not match selected snapshot")
            document = parse_manifest(manifest)
            if document["project_id"] != self._snapshot.project_id:
                raise _corrupt("Manifest project does not match selected snapshot")
            digest = sha256(raw)
            if digest != document["graph"]["raw_sha256"]:
                raise _corrupt("Graph digest mismatch")
            # A self-contained rollback-mode image only; WAL images need their sidecar.
            if len(raw) < 100 or raw[:16] != b"SQLite format 3\0" or raw[18:20] != b"\1\1":
                raise _corrupt("A self-contained SQLite graph image is required")
            if not hasattr(sqlite3.Connection, "deserialize"):
                raise CoreError("GRAPH_ADAPTER_UNAVAILABLE", "SQLite byte deserialization is unavailable")
            self._checkpoint()
            self._db = sqlite3.connect(":memory:", cached_statements=16)
            self._db.deserialize(raw)  # Exactly one native image copy; no source path.
            self._raw = self._manifest = None
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA query_only=ON").close()
            self._db.execute("PRAGMA trusted_schema=OFF").close()
            self._db.execute("PRAGMA temp_store=MEMORY").close()
            self._db.execute("PRAGMA cache_size=-" + str(self._limits.cache_kib)).close()
            disable_extensions = getattr(self._db, "enable_load_extension", None)
            if disable_extensions is not None:
                disable_extensions(False)
            self._db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, self._limits.max_value_bytes)
            self._db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 65536)
            self._db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 128)
            self._db.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
            self._db.setlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS, 0)
            self._db.set_authorizer(self._policy)
            self._quantum = min(1000, self._limits.max_vm_steps)
            self._db.set_progress_handler(self._progress, self._quantum)
            if [tuple(row) for row in self._queries.execute("PRAGMA integrity_check")] != [("ok",)]:
                raise _corrupt("Graph integrity check failed")
            if self._queries.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise _corrupt("Graph foreign key check failed")
            meta = dict(self._queries.execute("SELECT key,value FROM meta"))
            _validate_graph_structure(self._queries, meta, document)
            _verify_graph_digest(digest, meta, document)
            self._paths = frozenset(entry["graph_source_path"] for entry in _bindings(document))
            self._checkpoint()
            self._phase = "active"
            return self
        except sqlite3.Error as exc:
            self._close(preserve=True)
            raise _corrupt("Verified graph initialization is unavailable or invalid") from exc
        except BaseException:
            self._close(preserve=True)
            raise

    def run(self, operation, graph_source_path, *, max_depth=_NO_TRAVERSAL, max_edges=None):
        if self._phase != "active" or self._owner != (os.getpid(), get_ident()) or self._busy:
            raise _invalid()
        self._busy = True
        try:
            self._checkpoint()
            if type(graph_source_path) is not str or graph_source_path not in self._paths:
                raise CoreError("SOURCE_REF_MISMATCH", "Exact captured graph source path required")
            if max_depth is not _NO_TRAVERSAL and (
                type(max_depth) is not int or not 1 <= max_depth <= 5
                or type(max_edges) is not int or not 1 <= max_edges <= 600
            ):
                raise CoreError("INVALID_QUERY_OPTIONS", "Invalid graph traversal bounds")
            self._row_bytes = 0
            self._steps = 0
            result = operation()
            self._checkpoint()
            # Bound disclosure separately from cumulative fetched-row accounting.
            size = 0
            for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False).iterencode(result):
                self._checkpoint()
                size += len(chunk.encode("utf-8"))
                if size > self._limits.max_result_bytes:
                    raise _limit()
            self._checkpoint()
            return result
        except BaseException:
            self._close(preserve=True)
            raise
        finally:
            self._busy = False

    def _close(self, *, preserve):
        self._phase = "closed"
        db, self._db = self._db, None
        self._raw = self._manifest = self._authorize = None
        self._pending = None
        self._paths = frozenset()
        failure, self._cursor_failure = self._cursor_failure, None
        for rows in tuple(self._rows):
            try:
                rows.close()
            except BaseException as exc:
                failure = failure or exc
        self._cursor_failure = None
        if db is not None:
            try:
                db.close()
            except BaseException as exc:
                failure = failure or exc
        if failure is not None and not preserve:
            if not isinstance(failure, Exception):
                raise failure
            raise _corrupt("Verified graph cleanup failed") from failure

    def __exit__(self, kind, value, traceback):
        # Foreign/forked/reentrant callers cannot tear down another operation.
        if getattr(self, "_owner", None) != (os.getpid(), get_ident()) or self._busy:
            raise _invalid()
        if self._phase == "closed":
            return False
        if self._phase != "active":
            raise _invalid()
        self._busy = True
        try:
            if kind is None:
                self._checkpoint()
        except BaseException:
            self._close(preserve=True)
            raise
        finally:
            self._busy = False
        self._close(preserve=kind is not None)
        return False
