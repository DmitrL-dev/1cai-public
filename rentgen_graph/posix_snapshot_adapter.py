"""Internal bounded graph images; no scanner launch, filesystem or publication IO."""
from dataclasses import asdict, dataclass
import io
import json
import os
from pathlib import Path
import sqlite3
from threading import get_ident
from time import monotonic

from rentgen_core._linux_scanner import LinuxScannerOutput
from rentgen_core._verified_graph import _VerifiedGraph
from rentgen_core.errors import CoreError
from rentgen_core.graph import GraphBuildReceipt
from rentgen_core.manifests import CapturedInput, canonical_bytes, sha256
from rentgen_core.sources import _validate_graph_structure, _verify_graph_digest

from .build_store import BuildMode, _populate_store
from .identity import IDENTITY_VERSION, SCHEMA_VERSION, source_key
from .snapshot_adapter import (
    BSL_SUFFIXES, BUILDER_VERSION, SEMANTIC_SCOPE,
    _validate_outputs,
)

ADAPTER_VERSION = "rentgen-captured-owned-go-v1"


def _limit():
    return CoreError("GRAPH_BUILD_LIMIT_EXCEEDED", "Owned graph resource limit exceeded")


def _mismatch(message="Scanner output does not match copied sources"):
    return CoreError("GRAPH_INPUT_MISMATCH", message)


@dataclass(frozen=True)
class PosixGraphLimits:
    """Large-image accounting is explicit; this is not a hard process RSS cap."""
    image_buffer_budget: int
    max_source_bytes: int = 64 * 1024**2
    max_scanner_output_bytes: int = 16 * 1024**2
    max_graph_bytes: int = 64 * 1024**2
    max_files: int = 4096
    max_records: int = 100_000
    max_record_bytes: int = 1024**2
    max_vm_steps: int = 10_000_000
    cache_kib: int = 8192
    deadline_seconds: int = 30

    def __post_init__(self):
        maxima = (4 * 1024**3, 1024**3, 256 * 1024**2, 1024**3,
                  20_000, 1_000_000, 16 * 1024**2, 100_000_000, 65_536, 30)
        if any(type(value) is not int or not 1 <= value <= maximum
               for value, maximum in zip(asdict(self).values(), maxima)):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed bounded graph limits required")


@dataclass(frozen=True)
class PosixGraphBundle:
    receipt: GraphBuildReceipt
    graph_bytes: bytes
    ndjson: bytes
    coverage: bytes
    sqlite_version: str
    resident_image_accounting: int


def build_posix_graph_bundle(captured, scanner_output, *, limits, authorize):
    """Consume trusted copied inputs plus a terminal scanner result; return bytes only.

    Constructing a LinuxScannerOutput in Python is not evidence that its process
    contract ran. Actual Linux scanner, complete-generation and installed-product
    acceptance belong to the caller's separate integration tests.
    """
    try:
        return _Build(captured, scanner_output, limits, authorize).run()
    finally:
        captured = scanner_output = authorize = None


class _Build:
    def __init__(self, captured, output, limits, authorize):
        if (type(limits) is not PosixGraphLimits or not callable(authorize)
                or type(output) is not LinuxScannerOutput):
            raise CoreError("INVALID_QUERY_OPTIONS", "Typed scanner output and graph limits required")
        self._captured, self._output = captured, output
        self._limits, self._authorize = limits, authorize
        self._owner = os.getpid(), get_ident()
        self._deadline = monotonic() + limits.deadline_seconds
        self._db, self._pending = None, None
        self._steps, self._phase = 0, "active"
        self._busy = False
        self._quantum = min(1000, limits.max_vm_steps)

    def _checkpoint(self):
        if self._phase != "active" or self._owner != (os.getpid(), get_ident()):
            raise CoreError("GRAPH_BUILD_SESSION_INVALID", "Owned graph build is not active on its owner")
        if monotonic() >= self._deadline:
            raise CoreError("GRAPH_BUILD_DEADLINE_EXCEEDED", "Owned graph deadline exceeded")
        self._authorize()
        if monotonic() >= self._deadline:
            raise CoreError("GRAPH_BUILD_DEADLINE_EXCEEDED", "Owned graph deadline exceeded")

    def _progress(self):
        if self._pending is not None:
            return 1
        try:
            self._steps += 1
            if self._steps >= self._limits.max_vm_steps:
                raise _limit()
            if self._steps % self._quantum == 0:
                self._checkpoint()
        except BaseException as exc:
            self._pending = exc
            return 1
        return 0

    def _connection(self):
        self._checkpoint()
        db = sqlite3.connect(":memory:", cached_statements=16)
        self._db = db  # Register ownership before any fallible configuration.
        db.execute("PRAGMA trusted_schema=OFF").close()
        db.execute("PRAGMA temp_store=MEMORY").close()
        db.execute("PRAGMA cache_size=-" + str(self._limits.cache_kib)).close()
        db.execute("PRAGMA foreign_keys=ON").close()
        disable = getattr(db, "enable_load_extension", None)
        if disable is not None:
            disable(False)
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, self._limits.max_record_bytes)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 65_536)
        db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 128)
        db.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        db.setlimit(sqlite3.SQLITE_LIMIT_WORKER_THREADS, 0)
        # Count every opcode across short statements; batch state callbacks.
        db.set_progress_handler(self._progress, 1)
        db.execute("PRAGMA page_size=4096").close()
        db.execute("PRAGMA auto_vacuum=FULL").close()
        db.execute("PRAGMA secure_delete=ON").close()
        pages = self._limits.max_graph_bytes // 4096
        if pages < 1:
            raise _limit()
        actual = db.execute("PRAGMA max_page_count=" + str(pages)).fetchone()[0]
        if actual != pages:
            raise _limit()
        return db

    def _close(self, *, preserve):
        db, self._db = self._db, None
        if db is not None:
            try:
                db.close()
            except BaseException:
                if not preserve:
                    raise

    def _records(self, raw):
        stream = line = None
        try:
            with io.BytesIO(raw) as stream:
                for line in stream:
                    self._checkpoint()
                    if len(line) > self._limits.max_record_bytes:
                        raise _limit()
                    # _validate_outputs already validates every consumed field.
                    yield json.loads(line)
            self._checkpoint()
        finally:
            raw = line = stream = None

    @staticmethod
    def _forget_failed_input_frame(exception, operation):
        # These completed private callees consume our copies. Their traceback
        # locals must not outlive a denied operation; never clear caller frames
        # or replace the original exception, cause or traceback structure.
        current = exception.__traceback__
        while current is not None:
            if current.tb_frame.f_code is operation.__code__:
                current.tb_frame.clear()
            current = current.tb_next

    def _inputs(self):
        raw = line = lines = output = ndjson = coverage = texts = None
        try:
            self._checkpoint()
            output, limits = self._output, self._limits
            if (type(output.ndjson) is not bytes or type(output.coverage) is not bytes
                    or output.protocol != "rentgen-owned-scanner-linux-v1"
                    or type(output.executable_sha256) is not str
                    or len(output.executable_sha256) != 64
                    or any(c not in "0123456789abcdef" for c in output.executable_sha256)):
                raise _mismatch("Invalid terminal scanner output binding")
            output_size = len(output.ndjson) + len(output.coverage)
            if output_size > limits.max_scanner_output_bytes:
                raise _limit()
            with io.BytesIO(output.ndjson) as lines:
                for count, line in enumerate(lines, start=1):
                    self._checkpoint()
                    if count > limits.max_records or len(line) > limits.max_record_bytes:
                        raise _limit()
            entries = self._captured.entries
            if (type(entries) is not tuple
                    or any(type(entry) is not CapturedInput for entry in entries)):
                raise _mismatch("Exact typed copied source entries required")
            if len(entries) > limits.max_files:
                raise _limit()
            total = sum(entry.size_bytes for entry in entries)
            bsl_total = sum(entry.size_bytes for entry in entries if Path(entry.relative_path).suffix.lower() in BSL_SUFFIXES)
            if total > limits.max_source_bytes:
                raise _limit()
            path_bytes = 0
            for entry in entries:
                self._checkpoint()
                size = len((entry.layer_id + "/" + entry.relative_path).encode("utf-8"))
                if size > 4096:
                    raise _mismatch("Unsupported copied source path")
                path_bytes += size
            # Caller source images, decoded source text/transient UTF-8, conservative
            # source line splits/canonical scanner/binding images, graph plus its
            # serialize/deserialize native image and configured connection caches.
            plan = (total + 9 * bsl_total + 16 * output_size + 24 * path_bytes
                    + 3072 * len(entries) + 2 * limits.max_graph_bytes + 2 * limits.cache_kib * 1024)
            if plan > limits.image_buffer_budget:
                raise _limit()
            expected, texts, bindings, keys = {}, {}, [], set()
            for entry in entries:
                self._checkpoint()
                path = entry.layer_id + "/" + entry.relative_path
                key = source_key(path)
                if key in keys or len(path.encode("utf-8")) > 4096:
                    raise _mismatch("Duplicate or unsupported copied source path")
                keys.add(key)
                if Path(entry.relative_path).suffix.lower() not in BSL_SUFFIXES:
                    continue
                try:
                    raw = self._captured.read_bytes(entry)
                    self._checkpoint()
                    if type(raw) is not bytes or len(raw) != entry.size_bytes or sha256(raw) != entry.raw_sha256:
                        raise _mismatch("Copied source image differs from its entry")
                    if entry.encoding not in {"utf-8", "utf-8-sig"}:
                        raise CoreError("SOURCE_ENCODING_UNSUPPORTED", "BSL requires verified UTF-8 encoding")
                    try:
                        texts[path] = raw.decode("utf-8-sig")
                    except UnicodeError as exc:
                        raise CoreError("SOURCE_ENCODING_UNSUPPORTED", "BSL requires verified UTF-8 encoding") from exc
                finally:
                    raw = None
                expected[path] = entry
                bindings.append(dict(asdict(entry), graph_source_path=path))
            self._checkpoint()
            try:
                ndjson, coverage = _validate_outputs(output.ndjson, output.coverage, expected, texts)
            except BaseException as exc:
                self._forget_failed_input_frame(exc, _validate_outputs)
                raise
            self._checkpoint()
            if len(ndjson) + len(coverage) > limits.max_scanner_output_bytes:
                raise _limit()
            bindings.sort(key=lambda item: item["graph_source_path"].encode("utf-8"))
            receipt = GraphBuildReceipt(SCHEMA_VERSION, IDENTITY_VERSION, self._captured.source_digest,
                sha256(canonical_bytes(bindings)), ADAPTER_VERSION,
                output.protocol + ";sha256=" + output.executable_sha256, BUILDER_VERSION,
                sha256(canonical_bytes(dict(mode="owned-linux-v1", coverage_version=1,
                    encoding="utf-8-sig", quality="unavailable"))), SEMANTIC_SCOPE)
            self._checkpoint()
            return entries, tuple(expected), receipt, ndjson, coverage, plan
        finally:
            if texts is not None:
                texts.clear()
            raw = line = lines = output = ndjson = coverage = texts = None

    def _build(self):
        graph = ndjson = coverage = records = None
        try:
            entries, paths, receipt, ndjson, coverage, plan = self._inputs()
            db = self._connection()
            records = self._records(ndjson)
            try:
                meta, _ = _populate_store(db, 0, 0, mode=BuildMode.SNAPSHOT, binding=receipt,
                                         source_paths=paths, _records=records)
            except BaseException as exc:
                self._forget_failed_input_frame(exc, _populate_store)
                raise
            finally:
                records.close()
                records = None
            self._checkpoint()
            size = db.execute("PRAGMA page_count").fetchone()[0] * db.execute("PRAGMA page_size").fetchone()[0]
            if size > self._limits.max_graph_bytes:
                raise _limit()
            self._checkpoint()
            graph = db.serialize()
            if len(graph) != size or len(graph) < 100 or graph[:16] != b"SQLite format 3\0" or graph[18:20] != b"\1\1":
                raise _mismatch("A bounded self-contained SQLite image is required")
            self._close(preserve=False)
            self._checkpoint()
            # Validate the actual serialized image using a separate owned connection.
            db = self._connection()
            db.deserialize(graph)
            db.execute("PRAGMA query_only=ON").close()
            db.set_authorizer(_VerifiedGraph._policy)
            document = dict(source=dict(entries=[asdict(entry) for entry in entries]),
                graph=dict(asdict(receipt), relative_path="graph.sqlite3", raw_sha256=sha256(graph),
                           sqlite_version=sqlite3.sqlite_version, quality="unavailable"))
            if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or db.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise _mismatch("Serialized graph integrity check failed")
            actual_meta = dict(db.execute("SELECT key,value FROM meta"))
            _validate_graph_structure(db, actual_meta, document)
            _verify_graph_digest(sha256(graph), actual_meta, document)
            if actual_meta != meta:
                raise _mismatch("Serialized graph metadata differs from builder metadata")
            self._checkpoint()
            return PosixGraphBundle(receipt, graph, ndjson, coverage, sqlite3.sqlite_version, plan)
        finally:
            graph = ndjson = coverage = records = None

    def run(self):
        if (self._owner != (os.getpid(), get_ident()) or self._busy
                or self._phase != "active"):
            raise CoreError("GRAPH_BUILD_SESSION_INVALID", "Owned graph build is not active on its owner")
        self._busy = True
        result = None
        try:
            self._checkpoint()
            if not hasattr(sqlite3.Connection, "serialize") or not hasattr(sqlite3.Connection, "deserialize"):
                raise CoreError("GRAPH_ADAPTER_UNAVAILABLE", "SQLite image serialization is unavailable")
            result = self._build()
            self._close(preserve=False)
            self._checkpoint()
            return result
        except sqlite3.Error as exc:
            result = None
            if self._pending is not None:
                raise self._pending
            if getattr(exc, "sqlite_errorcode", None) in {sqlite3.SQLITE_FULL, sqlite3.SQLITE_TOOBIG}:
                raise _limit() from exc
            raise CoreError("GRAPH_BUILD_FAILED", "Owned SQLite graph build failed") from exc
        except BaseException:
            result = None
            raise
        finally:
            self._close(preserve=True)
            self._captured = self._output = self._authorize = self._pending = None
            self._phase = "closed"
            self._busy = False
