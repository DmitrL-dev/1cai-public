"""Bounded, read-only byte comparison of two explicitly submitted Designer ZIPs.

The accepted import owns BEFORE; only a second explicit upload supplies AFTER.
Rows describe exact path/raw-hash/size differences, never semantic changes or a
snapshot. One accepted pair and one replacement are retained; page IDs confer
only temporary, server-owned row authority. All Rust lifetimes share the GUI IO
gate, including validation and source preview. Python never opens ZIP entries.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
import secrets
import threading
import time

from .errors import CoreError
from .rust_input import RustInputSession
from .submitted_export import analyze_export

PAGE_LIMIT = 200
MAX_OFFSET = 8000
MAX_ROWS = 8192
MAX_SOURCE = 256 * 1024
ACTIVE = frozenset({"awaiting_upload", "uploading", "analyzing"})
FILTERS = frozenset({"all", "changes", "added", "removed", "modified", "unchanged"})


def fail(code):
    raise CoreError(code, "Local ZIP comparison could not complete the request")


def _id(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def _hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_filename(filename):
    if (type(filename) is not str or len(filename) > 240 or not filename.lower().endswith(".zip")
            or any(ord(char) < 32 or char in "/\\" for char in filename)):
        fail("INVALID_UPLOAD")
    try:
        filename.encode("utf-8")
    except UnicodeError:
        fail("INVALID_UPLOAD")


def compare_entries(before, after):
    """Pure byte inventory comparison; no text decoding or rename guessing."""
    sides = [{entry["path"]: {"raw_sha256": entry["raw_sha256"], "size_bytes": entry["size_bytes"]}
              for entry in entries} for entries in (before, after)]
    paths = sorted(sides[0].keys() | sides[1].keys(), key=lambda path: path.encode("utf-8"))
    if len(paths) > MAX_ROWS:
        fail("IMPORTED_EXPORT_LIMIT")
    rows = []
    counts = dict.fromkeys(("added", "removed", "modified", "unchanged"), 0)
    for path in paths:
        left, right = (side.get(path) for side in sides)
        status = "added" if left is None else "removed" if right is None else "unchanged" if left == right else "modified"
        counts[status] += 1
        rows.append({"path": path, "status": status, "before": left, "after": right})
    counts.update(total=len(rows), files=len(rows), changes=len(rows) - counts["unchanged"])
    return tuple(rows), counts


@dataclass
class Comparison:
    id: str
    before: object
    before_sha256: str
    filename: str
    path: Path
    status: str = "awaiting_upload"
    sha256: str = ""
    error: str | None = None
    completed_at: str | None = None
    created_at: float = field(default_factory=time.monotonic)
    cancel: threading.Event = field(default_factory=threading.Event)
    rows: tuple = ()
    counts: dict | None = None
    page: dict | None = None


class ComparisonWorkspace:
    """Workspace mixin. Callers hold lock for disclosure validation."""

    def _init_comparison(self):
        self.comparison_pending = None
        self.comparison_current = None
        self.comparison_worker = None
        self.report_lock = threading.Lock()
        self._report_generation = 0

    def _invalidate_comparison_page(self):
        self._report_generation += 1
        if self.comparison_current:
            self.comparison_current.page = None

    def _expire_comparison(self):
        item = self.comparison_pending
        if item and item.status == "awaiting_upload" and time.monotonic() - item.created_at >= 30:
            self.abandon_comparison(item, "UPLOAD_TIMEOUT")

    def _comparison_busy(self):
        self._expire_comparison()
        return (self.comparison_pending and self.comparison_pending.status in ACTIVE) or (
            self.comparison_worker and self.comparison_worker.is_alive())

    def _comparison_before(self, job_id, sha256):
        if not _id(job_id) or not _hash(sha256):
            fail("COMPARISON_NOT_AVAILABLE")
        job = self.current
        if (self.closed or job is None or job.status != "ready"
                or not secrets.compare_digest(job.id, job_id) or not secrets.compare_digest(job.sha256, sha256)):
            fail("COMPARISON_NOT_AVAILABLE")
        return job

    def reserve_comparison(self, job_id, sha256, filename):
        self.config.authorize()
        validate_filename(filename)
        with self.lock:
            before = self._comparison_before(job_id, sha256)
            if self.pending and self.pending.status == "awaiting_upload" and time.monotonic() - self.pending.created_at >= 30:
                self.abandon(self.pending, "UPLOAD_TIMEOUT")
            if ((self.pending and self.pending.status in ACTIVE) or (self.worker and self.worker.is_alive())
                    or self._comparison_busy()):
                fail("BUSY")
            self._invalidate_comparison_page()
            previous = self.comparison_pending
            if previous and previous is not self.comparison_current:
                previous.path.unlink(missing_ok=True)
            self._reserve_zip_slots(1, excluding=[previous.path] if previous and previous is not self.comparison_current else [])
            item = Comparison(secrets.token_hex(16), before, before.sha256, filename,
                              Path(self.temp.name) / (secrets.token_hex(16) + ".zip"))
            self.comparison_pending = item
            return self._comparison_status(item)

    def abandon_comparison(self, item, code):
        with self.lock:
            item.error = "CANCELLED" if item.cancel.is_set() or self.closed else code
            item.status = "cancelled" if item.error == "CANCELLED" else "error"
            item.rows = ()
            item.counts = None
            item.page = None
            item.path.unlink(missing_ok=True)

    def _get_comparison(self, comparison):
        if not _id(comparison):
            fail("COMPARISON_NOT_AVAILABLE")
        item = next((item for item in (self.comparison_pending, self.comparison_current)
                     if item and secrets.compare_digest(item.id, comparison)), None)
        if item is None or self._comparison_before(item.before.id, item.before_sha256) is not item.before:
            fail("COMPARISON_NOT_AVAILABLE")
        return item

    def _pair(self, pair, before_sha256, after_sha256):
        item = self._get_comparison(pair)
        if (item is not self.comparison_current or item.status != "ready" or not _hash(before_sha256)
                or not _hash(after_sha256) or not secrets.compare_digest(item.before_sha256, before_sha256)
                or not secrets.compare_digest(item.sha256, after_sha256)):
            fail("COMPARISON_NOT_AVAILABLE")
        return item

    def _binding(self, item):
        return {"pair": item.id, "job": item.before.id, "before_sha256": item.before_sha256,
                "after_sha256": item.sha256, "before_filename": item.before.filename,
                "after_filename": item.filename, "counts": dict(item.counts),
                "scope": "submitted_zip_bytes", "comparison": "raw_sha256_and_size"}

    def _comparison_status(self, item):
        data = {"comparison": item.id, "job": item.before.id, "input_sha256": item.before_sha256,
                "filename": item.filename, "status": item.status, "error": item.error,
                "completed_at": item.completed_at}
        if item.status == "ready":
            data["result"] = self._binding(item)
        return data

    def comparison_status(self, comparison):
        self.config.authorize()
        with self.lock:
            self._expire_comparison()
            return self._comparison_status(self._get_comparison(comparison))

    def comparison_current_status(self, job_id, sha256):
        self.config.authorize()
        with self.lock:
            self._comparison_before(job_id, sha256)
            self._expire_comparison()
            pending, current = self.comparison_pending, self.comparison_current
            return {"job": job_id, "input_sha256": sha256,
                    "pending": self._comparison_status(pending) if pending and pending is not current else None,
                    "current": self._comparison_status(current) if current else None}

    def cancel_comparison(self, comparison):
        self.config.authorize()
        with self.lock:
            item = self._get_comparison(comparison)
            if item.status in ACTIVE:
                item.cancel.set()
                if item.status == "awaiting_upload":
                    self.abandon_comparison(item, "CANCELLED")
            return {"status": item.status, "cancel_requested": item.cancel.is_set()}

    def start_comparison(self, item):
        with self.lock:
            if self.closed or item.cancel.is_set():
                self.abandon_comparison(item, "CANCELLED")
                return
            item.status = "analyzing"
            self.comparison_worker = threading.Thread(target=self._analyze_comparison, args=(item,),
                                                     name="rentgen-gui-comparison", daemon=False)
            self.comparison_worker.start()

    def _comparison_authorize(self, item):
        self.config.authorize()
        with self.lock:
            if self.closed or item.cancel.is_set():
                fail("CANCELLED")
            if self._get_comparison(item.id) is not item or item is not self.comparison_pending:
                fail("COMPARISON_NOT_AVAILABLE")

    def _manifest(self, archive, sha256, authorize):
        with RustInputSession(self.config.input_core, self.config.input_core_sha256, authorize=authorize) as session:
            manifest = session.open_import(archive, sha256)
            return session.entries(manifest)

    def _analyze_comparison(self, item):
        try:
            # Three sequential Rust children, all fully reaped before the next:
            # validate AFTER as Designer, read BEFORE manifest, read AFTER manifest.
            with self.io_lock:
                self._comparison_authorize(item)
                analyze_export(self.config.context(), archive=item.path, archive_sha256=item.sha256,
                    input_core=self.config.input_core, input_core_sha256=self.config.input_core_sha256,
                    limit=PAGE_LIMIT, cancelled=item.cancel.is_set)
                authorize = lambda: self._comparison_authorize(item)
                before = self._manifest(item.before.path, item.before_sha256, authorize)
                after = self._manifest(item.path, item.sha256, authorize)
                rows, counts = compare_entries(before, after)
                del before, after
                authorize()
                with self.lock:
                    self._comparison_authorize(item)
                    previous = self.comparison_current
                    item.rows, item.counts = rows, counts
                    item.status = "ready"
                    item.completed_at = datetime.now(timezone.utc).isoformat()
                    self.comparison_current = item
                    if previous and previous is not item:
                        previous.rows = ()
                        previous.counts = None
                        previous.page = None
                        previous.path.unlink(missing_ok=True)
        except Exception as error:
            self.abandon_comparison(item, error.code if isinstance(error, CoreError) else "INTERNAL_ERROR")

    def comparison_page(self, pair, before_sha256, after_sha256, offset, status):
        self.config.authorize()
        if (type(offset) is not int or not 0 <= offset <= MAX_OFFSET or offset % PAGE_LIMIT
                or type(status) is not str or status not in FILTERS):
            fail("INVALID_QUERY_OPTIONS")
        with self.lock:
            item = self._pair(pair, before_sha256, after_sha256)
            rows = tuple(row for row in item.rows if status == "all" or row["status"] == status
                         or (status == "changes" and row["status"] != "unchanged"))
            if offset and offset >= len(rows):
                fail("INVALID_QUERY_OPTIONS")
            selected = rows[offset:offset + PAGE_LIMIT]
            page = {"id": secrets.token_hex(16), "offset": offset, "limit": PAGE_LIMIT,
                    "total": len(rows), "returned": len(selected), "has_previous": offset > 0,
                    "has_next": offset + len(selected) < len(rows)}
            item.page = {"id": page["id"], "rows": selected}
            return {**self._binding(item), "status": status, "page": page, "rows": list(selected)}

    def validate_comparison_page(self, pair, before_sha256, after_sha256, page):
        item = self._pair(pair, before_sha256, after_sha256)
        if not _id(page) or not item.page or not secrets.compare_digest(item.page["id"], page):
            fail("COMPARISON_NOT_AVAILABLE")
        return item

    def _comparison_source_reference(self, pair, before_sha256, after_sha256, page, side, path):
        try:
            item = self.validate_comparison_page(pair, before_sha256, after_sha256, page)
        except CoreError:
            fail("SOURCE_NOT_AVAILABLE")
        if type(side) is not str or side not in {"before", "after"} or type(path) is not str:
            fail("SOURCE_NOT_AVAILABLE")
        row = next((row for row in item.page["rows"] if row["path"] == path), None)
        if row is None or row[side] is None:
            fail("SOURCE_NOT_AVAILABLE")
        archive, sha256 = (item.before.path, item.before_sha256) if side == "before" else (item.path, item.sha256)
        reference = {"input_sha256": sha256, "relative_path": row["path"], "raw_sha256": row[side]["raw_sha256"]}
        return archive, reference, row[side]["size_bytes"]

    def comparison_source(self, pair, before_sha256, after_sha256, page, side, path):
        selectors = (pair, before_sha256, after_sha256, page, side, path)
        self.config.authorize()
        if not self.io_lock.acquire(blocking=False):
            fail("BUSY")
        try:
            with self.lock:
                archive, reference, size = self._comparison_source_reference(*selectors)
            def authorize():
                self.config.authorize()
                with self.lock:
                    if self._comparison_source_reference(*selectors) != (archive, reference, size):
                        fail("SOURCE_NOT_AVAILABLE")
            with RustInputSession(self.config.input_core, self.config.input_core_sha256, authorize=authorize) as session:
                manifest = session.open_import(archive, reference["input_sha256"])
                entry = next((entry for entry in session.entries(manifest) if entry["path"] == path), None)
                if entry is None or entry["raw_sha256"] != reference["raw_sha256"] or entry["size_bytes"] != size:
                    fail("SOURCE_NOT_AVAILABLE")
                if size > MAX_SOURCE:
                    fail("SOURCE_TOO_LARGE")
                raw = session.read_entry(entry)
            try:
                text = raw.decode("utf-8-sig", errors="strict")
            except UnicodeError:
                fail("SOURCE_ENCODING_UNSUPPORTED")
            if any(ord(char) < 32 and char not in "\r\n\t" for char in text):
                fail("SOURCE_ENCODING_UNSUPPORTED")
            authorize()
            return {"pair": pair, "before_sha256": before_sha256, "after_sha256": after_sha256,
                    "page": page, "side": side, "text": text, "encoding": "UTF-8",
                    "size_bytes": len(raw), "input_ref": reference}
        finally:
            self.io_lock.release()

    def _clear_comparison(self):
        """Caller owns both io_lock and lock. No accepted reader can remain."""
        for item in (self.comparison_pending, self.comparison_current):
            if item:
                item.rows = ()
                item.counts = None
                item.page = None
                item.path.unlink(missing_ok=True)
        self.comparison_pending = self.comparison_current = None


def dispatch_comparison(handler, path):
    """Strict HTTP schema and post-serialization capability revalidation."""
    import json
    app = handler.server.workspace
    method = handler.command
    if method == "PUT" and path == "/api/comparison-upload":
        query = handler._query({"comparison"})
        handler._upload_comparison(query["comparison"])
        return True
    if method == "GET" and path == "/api/comparison-source":
        query = handler._query({"pair", "before_sha256", "after_sha256", "page", "side", "path"})
        result = app.comparison_source(**query)
        with app.lock:
            def validate():
                _, reference, size = app._comparison_source_reference(**query)
                if reference != result["input_ref"] or size != result["size_bytes"]:
                    fail("SOURCE_NOT_AVAILABLE")
            validate()
            handler._json(result, validate=validate)
        return True
    if method == "GET" and path == "/api/comparison":
        query = handler._query({"comparison"})
        with app.lock:
            result = app.comparison_status(query["comparison"])
            handler._json(result, validate=lambda: app._get_comparison(query["comparison"]))
        return True
    if method == "GET" and path == "/api/comparison-current":
        query = handler._query({"job", "input_sha256"})
        with app.lock:
            result = app.comparison_current_status(query["job"], query["input_sha256"])
            handler._json(result, validate=lambda: app._comparison_before(query["job"], query["input_sha256"]))
        return True
    fields = {
        "/api/comparison-start": {"job", "input_sha256", "filename"},
        "/api/comparison-cancel": {"comparison"},
        "/api/comparison-page": {"pair", "before_sha256", "after_sha256", "offset", "status"},
        "/api/comparison-report": {"pair", "before_sha256", "after_sha256", "format"},
    }
    if method != "POST" or path not in fields:
        return False
    if handler.headers.get_all("Content-Type") != ["application/json"]:
        fail("INVALID_REQUEST")
    if path == "/api/comparison-report":
        from .gui_report import dispatch_report, parse_request
        handler._query(set())
        dispatch_report(handler, parse_request(handler._body(2048)))
        return True
    payload = json.loads(handler._body(2048))
    if type(payload) is not dict or set(payload) != fields[path]:
        fail("INVALID_REQUEST")
    with app.lock:
        if path == "/api/comparison-start":
            result = app.reserve_comparison(payload["job"], payload["input_sha256"], payload["filename"])
            handler._json(result, status=201, validate=lambda: app._get_comparison(result["comparison"]))
        elif path == "/api/comparison-cancel":
            result = app.cancel_comparison(payload["comparison"])
            handler._json(result, validate=lambda: app._get_comparison(payload["comparison"]))
        else:
            result = app.comparison_page(**payload)
            validate = lambda: app.validate_comparison_page(payload["pair"], payload["before_sha256"],
                                                             payload["after_sha256"], result["page"]["id"])
            handler._json(result, validate=validate)
    return True
