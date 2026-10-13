"""Experimental local-only graphical workspace for submitted Designer ZIP bytes.

The HTTP session is a transport gate, never project authorization. Startup paths
are trusted process configuration and cannot be replaced by browser requests.
No live source, graph, diagnostic, write, or remote-user API is exposed.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import socket
import sys
import tempfile
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit
import webbrowser

from .errors import CoreError
from .local import LocalRuntime
from .local_identity import current_local_principal
from .rust_input import RustInputSession
from .submitted_export import PERMISSIONS, analyze_export

MAX_UPLOAD = 16 * 1024**2
MAX_SOURCE = 256 * 1024
MAX_SEARCH_QUERY = 256
SEARCH_LIMIT = 200
ASSETS = Path(__file__).with_name("gui_assets")
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/model.js": ("model.js", "text/javascript; charset=utf-8"),
          "/app.css": ("app.css", "text/css; charset=utf-8"),
          "/mark.svg": ("mark.svg", "image/svg+xml")}


def fail(code):
    raise CoreError(code, "Local graphical workspace could not complete the request")


@dataclass(frozen=True)
class Config:
    registry: Path
    identity_profile: Path
    project: str
    input_core: Path
    input_core_sha256: str

    def context(self):
        principal = current_local_principal(identity_profile=self.identity_profile)
        return LocalRuntime(self.registry).state_context(principal, self.project, permissions=PERMISSIONS)

    def authorize(self):
        self.context()


@dataclass
class Job:
    id: str
    filename: str
    path: Path
    status: str = "awaiting_upload"
    sha256: str = ""
    result: dict | None = None
    error: str | None = None
    completed_at: str | None = None
    created_at: float = field(default_factory=time.monotonic)
    cancel: threading.Event = field(default_factory=threading.Event)


@dataclass
class Search:
    id: str
    job: Job
    sha256: str
    query: str
    status: str = "searching"
    result: dict | None = None
    error: str | None = None
    valid: bool = True
    cancel: threading.Event = field(default_factory=threading.Event)


class Workspace:
    def __init__(self, config):
        self.config = config
        config.authorize()
        self.token = secrets.token_urlsafe(32)
        self.temp = tempfile.TemporaryDirectory(prefix="rentgen-gui-")
        self.lock = threading.RLock()
        self.io_lock = threading.Lock()
        self.pending = None
        self.current = None
        self.worker = None
        self.search = None
        self.search_worker = None
        self.closed = False

    def reserve(self, filename):
        self.config.authorize()
        with self.lock:
            if self.closed:
                fail("SESSION_CLOSED")
            if self.pending and self.pending.status == "awaiting_upload" and time.monotonic() - self.pending.created_at >= 30:
                self.abandon(self.pending, "UPLOAD_TIMEOUT")
            if self.pending and self.pending.status in {"awaiting_upload", "uploading", "analyzing"}:
                fail("BUSY")
            self._invalidate_search()
            if self.pending and self.pending is not self.current:
                self.pending.path.unlink(missing_ok=True)
            job = Job(secrets.token_hex(16), filename, Path(self.temp.name) / (secrets.token_hex(16) + ".zip"))
            self.pending = job
            return job

    def abandon(self, job, code):
        with self.lock:
            job.error = code
            job.status = "cancelled" if code == "CANCELLED" else "error"
            job.path.unlink(missing_ok=True)

    def start(self, job):
        with self.lock:
            if self.closed or job.cancel.is_set():
                self.abandon(job, "CANCELLED")
                return
            job.status = "analyzing"
            self.worker = threading.Thread(target=self._analyze, args=(job,), name="rentgen-gui-analysis", daemon=False)
            self.worker.start()

    def _analyze(self, job):
        try:
            ctx = self.config.context()
            result = analyze_export(ctx, archive=job.path, archive_sha256=job.sha256,
                input_core=self.config.input_core, input_core_sha256=self.config.input_core_sha256,
                limit=SEARCH_LIMIT, cancelled=job.cancel.is_set)
            self.config.authorize()
            with self.io_lock, self.lock:
                if job.cancel.is_set() or self.closed:
                    fail("CANCELLED")
                previous = self.current
                self._invalidate_search()
                job.result = result
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.status = "ready"
                self.current = job
                if previous and previous is not job:
                    previous.result = None
                    previous.path.unlink(missing_ok=True)
        except CoreError as error:
            self.abandon(job, error.code)
        except Exception:
            self.abandon(job, "INTERNAL_ERROR")

    def get_job(self, job_id):
        if type(job_id) is not str or re.fullmatch(r"[0-9a-f]{32}", job_id) is None:
            fail("SOURCE_NOT_AVAILABLE")
        with self.lock:
            job = next((item for item in (self.pending, self.current) if item and secrets.compare_digest(item.id, job_id)), None)
            if job is None:
                fail("SOURCE_NOT_AVAILABLE")
            return job

    def status(self, job_id):
        self.config.authorize()
        with self.lock:
            job = self.get_job(job_id)
            if job.status == "awaiting_upload" and time.monotonic() - job.created_at >= 30:
                self.abandon(job, "UPLOAD_TIMEOUT")
            data = {"job": job.id, "status": job.status, "filename": job.filename,
                    "completed_at": job.completed_at, "error": job.error}
            if job.status == "ready":
                data["result"] = job.result
            return data

    def cancel_job(self, job_id):
        self.config.authorize()
        with self.lock:
            job = self.get_job(job_id)
            # Completion already won. Keep the accepted result; the client can
            # suppress presentation but must not silently erase it.
            if job.status in {"awaiting_upload", "uploading", "analyzing"}:
                job.cancel.set()
                if job.status == "awaiting_upload":
                    self.abandon(job, "CANCELLED")
            return {"status": job.status, "cancel_requested": job.cancel.is_set()}

    def _invalidate_search(self):
        """Called with lock held; never discard an unreaped worker reference."""
        if self.search:
            self.search.valid = False
            self.search.cancel.set()
            self.search.result = None
            if self.search.status == "ready":
                self.search.status = "cancelled"
                self.search.error = "CANCELLED"

    def _search_job(self, job_id, sha256):
        if type(sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
            fail("SEARCH_NOT_AVAILABLE")
        job = self.get_job(job_id)
        if self.closed or job is not self.current or job.status != "ready" or not secrets.compare_digest(job.sha256, sha256):
            fail("SEARCH_NOT_AVAILABLE")
        return job

    def _get_search(self, job_id, search_id, sha256, *, valid=True):
        job = self._search_job(job_id, sha256)
        search = self.search
        if (type(search_id) is not str or re.fullmatch(r"[0-9a-f]{32}", search_id) is None
                or search is None or not secrets.compare_digest(search.id, search_id)
                or search.job is not job or search.sha256 != sha256 or (valid and not search.valid)):
            fail("SEARCH_NOT_AVAILABLE")
        return search

    def start_search(self, job_id, sha256, query):
        self.config.authorize()
        if type(query) is not str:
            fail("INVALID_QUERY_OPTIONS")
        try:
            if len(query.encode("utf-8")) > MAX_SEARCH_QUERY:
                fail("INVALID_QUERY_OPTIONS")
        except UnicodeError:
            fail("INVALID_QUERY_OPTIONS")
        with self.lock:
            job = self._search_job(job_id, sha256)
            if self.pending and self.pending.status == "awaiting_upload" and time.monotonic() - self.pending.created_at >= 30:
                self.abandon(self.pending, "UPLOAD_TIMEOUT")
            if self.pending and self.pending.status in {"awaiting_upload", "uploading", "analyzing"}:
                fail("BUSY")
            self._invalidate_search()
            # Supersession cancels the current child. A retry is accepted only
            # after its Rust context and non-daemon worker have both exited.
            if self.search_worker and self.search_worker.is_alive():
                fail("BUSY")
            search = Search(secrets.token_hex(16), job, job.sha256, query)
            self.search = search
            self.search_worker = threading.Thread(target=self._search, args=(search,), name="rentgen-gui-search", daemon=False)
            self.search_worker.start()
            return {"search": search.id, "job": job.id, "input_sha256": job.sha256}

    def _search(self, search):
        try:
            # The immutable Rust reader and archive replacement/unlink share
            # one IO gate. No Python ZIP fallback or live source is involved.
            with self.io_lock:
                with self.lock:
                    if self.closed or search.cancel.is_set() or not search.valid:
                        fail("CANCELLED")
                    self._get_search(search.job.id, search.id, search.sha256)
                result = analyze_export(self.config.context(), archive=search.job.path,
                    archive_sha256=search.sha256, input_core=self.config.input_core,
                    input_core_sha256=self.config.input_core_sha256, query=search.query,
                    limit=SEARCH_LIMIT, cancelled=search.cancel.is_set)
                self.config.authorize()
                with self.lock:
                    if self.closed or search.cancel.is_set() or not search.valid:
                        fail("CANCELLED")
                    self._get_search(search.job.id, search.id, search.sha256)
                    search.result = result
                    search.status = "ready"
        except Exception as error:
            with self.lock:
                code = error.code if isinstance(error, CoreError) else "INTERNAL_ERROR"
                search.error = "CANCELLED" if search.cancel.is_set() or self.closed else code
                search.status = "cancelled" if search.error == "CANCELLED" else "error"
                search.result = None

    def search_status(self, job_id, search_id, sha256):
        self.config.authorize()
        with self.lock:
            search = self._get_search(job_id, search_id, sha256)
            data = {"search": search.id, "job": search.job.id, "input_sha256": search.sha256,
                    "query": search.query, "status": search.status, "error": search.error}
            if search.status == "ready":
                data["result"] = search.result
            return data

    def cancel_search(self, job_id, search_id, sha256):
        self.config.authorize()
        with self.lock:
            job = self._search_job(job_id, sha256)
            # A lost start response can leave the client without the ID. This
            # bounded recovery selector can cancel only this current ZIP/job.
            if search_id is None:
                search = self.search
                if search is None or search.job is not job or search.sha256 != sha256:
                    return {"status": "cancelled", "cancel_requested": False}
            else:
                search = self._get_search(job_id, search_id, sha256, valid=False)
            if search.status == "searching":
                search.cancel.set()
            return {"status": search.status, "cancel_requested": search.cancel.is_set()}

    def _source_reference(self, job_id, path):
        job = self.get_job(job_id)
        if self.closed or job is not self.current or job.status != "ready":
            fail("SOURCE_NOT_AVAILABLE")
        rows = job.result["objects"] + job.result["modules"]
        search = self.search
        if (search and search.valid and search.job is job and search.sha256 == job.sha256
                and search.status == "ready" and not search.cancel.is_set()):
            rows += search.result["objects"]
        row = next((r for r in rows if r["input_ref"]["relative_path"] == path), None)
        if row is None or row["input_ref"]["input_sha256"] != job.sha256:
            fail("SOURCE_NOT_AVAILABLE")
        return job, row["input_ref"]

    def validate_source(self, job_id, path, reference):
        if self._source_reference(job_id, path)[1] != reference:
            fail("SOURCE_NOT_AVAILABLE")

    def source(self, job_id, path):
        self.config.authorize()
        # Serializes bounded source read against result replacement/unlink.
        if not self.io_lock.acquire(blocking=False):
            fail("BUSY")
        try:
            with self.lock:
                job, reference = self._source_reference(job_id, path)
            # Never use a supplied path as an OS locator or extract an archive.
            with RustInputSession(self.config.input_core, self.config.input_core_sha256,
                                  authorize=self.config.authorize) as session:
                manifest = session.open_import(job.path, job.sha256)
                entries = session.entries(manifest)
                entry = next((item for item in entries if item["path"] == path), None)
                if entry is None or entry["raw_sha256"] != reference["raw_sha256"] or manifest["input_sha256"] != reference["input_sha256"]:
                    fail("SOURCE_NOT_AVAILABLE")
                if entry["size_bytes"] > MAX_SOURCE:
                    fail("SOURCE_TOO_LARGE")
                raw = session.read_entry(entry)
            try:
                text = raw.decode("utf-8-sig", errors="strict")
            except UnicodeError:
                fail("SOURCE_ENCODING_UNSUPPORTED")
            # Exclude control characters that can disguise displayed source.
            if any(ord(char) < 32 and char not in "\r\n\t" for char in text):
                fail("SOURCE_ENCODING_UNSUPPORTED")
            self.config.authorize()
            return {"text": text, "encoding": "UTF-8", "size_bytes": len(raw), "input_ref": reference}
        finally:
            self.io_lock.release()

    def begin_close(self):
        with self.lock:
            self.closed = True
            if self.pending:
                self.pending.cancel.set()
            self._invalidate_search()

    def close(self):
        self.begin_close()
        with self.lock:
            worker = self.worker
            search_worker = self.search_worker
        if worker:
            worker.join()  # Rust session has its own deadline and confirmed reap.
        if search_worker:
            search_worker.join()
        with self.io_lock:
            self.temp.cleanup()


class Server(ThreadingHTTPServer):
    daemon_threads = False
    request_queue_size = 8

    def __init__(self, workspace, port=0):
        self.workspace = workspace
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.host = f"127.0.0.1:{self.server_port}"

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        # Tracebacks and request targets can contain project paths or session data.
        pass


class Handler(BaseHTTPRequestHandler):
    server_version = "RentgenLocalGUI"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def handle(self):
        # Bound even a slow header/body trickle. Socket deadlines alone limit
        # inactivity, not total request lifetime.
        timer = threading.Timer(75, self._expire)
        timer.daemon = True
        timer.start()
        try:
            super().handle()
        finally:
            timer.cancel()

    def _expire(self):
        try:
            self.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def log_message(self, format, *args):
        pass

    def _headers(self, status, content_type, length):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'")
        self.end_headers()

    def _json(self, value, status=200, authorize=True, error=False, validate=None):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(raw) > 4 * 1024**2:
            fail("OUTPUT_LIMIT")
        if authorize:
            try:
                self.server.workspace.config.authorize()
            except Exception:
                if not error:
                    raise
                raw = b'{"error":"FORBIDDEN"}'
                status = 403
        if validate is not None:
            validate()
        self._headers(status, "application/json; charset=utf-8", len(raw))
        self.wfile.write(raw)

    def _check(self, api=False):
        if len(self.path) > 4096 or self.headers.get_all("Host") != [self.server.host]:
            fail("UNAUTHORIZED")
        if self.headers.get("Transfer-Encoding") is not None:
            fail("INVALID_REQUEST")
        origins = self.headers.get_all("Origin", [])
        if origins and origins != [self.server.origin]:
            fail("UNAUTHORIZED")
        if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
            fail("UNAUTHORIZED")
        if api:
            tokens = self.headers.get_all("X-Rentgen-Session", [])
            if len(tokens) != 1 or re.fullmatch(r"[A-Za-z0-9_-]{43}", tokens[0]) is None or not secrets.compare_digest(tokens[0], self.server.workspace.token):
                fail("UNAUTHORIZED")
            if self.command in {"POST", "PUT"} and origins != [self.server.origin]:
                fail("UNAUTHORIZED")
            self.server.workspace.config.authorize()

    def _length(self, maximum):
        values = self.headers.get_all("Content-Length", [])
        if len(values) != 1 or not re.fullmatch(r"[0-9]{1,9}", values[0]):
            fail("INVALID_REQUEST")
        length = int(values[0])
        if not 0 < length <= maximum:
            fail("INVALID_UPLOAD")
        return length

    def _body(self, maximum):
        remaining = self._length(maximum)
        deadline = time.monotonic() + 5
        chunks = []
        while remaining:
            budget = deadline - time.monotonic()
            if budget <= 0:
                fail("UPLOAD_TIMEOUT")
            self.connection.settimeout(budget)
            chunk = self.rfile.read1(remaining)
            if not chunk:
                fail("INVALID_REQUEST")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _query(self, allowed):
        value = parse_qs(urlsplit(self.path).query, keep_blank_values=True, max_num_fields=3)
        if set(value) != set(allowed) or any(len(items) != 1 for items in value.values()):
            fail("INVALID_REQUEST")
        return {key: items[0] for key, items in value.items()}

    def _dispatch(self):
        path = urlsplit(self.path).path
        self._check(api=path.startswith("/api/"))
        app = self.server.workspace
        if self.command == "GET" and path in STATIC and not urlsplit(self.path).query:
            filename, mime = STATIC[path]
            raw = (ASSETS / filename).read_bytes()
            self._headers(200, mime, len(raw))
            self.wfile.write(raw)
        elif self.command == "GET" and path == "/api/session":
            app.config.authorize()
            project = LocalRuntime(app.config.registry).registry.get(app.config.project)
            self._json({"project_name": project.display_name, "platform": "experimental-linux", "max_upload_bytes": MAX_UPLOAD})
        elif self.command == "GET" and path == "/api/job":
            query = self._query({"job"})
            self._json(app.status(query["job"]))
        elif self.command == "GET" and path == "/api/source":
            query = self._query({"job", "path"})
            result = app.source(query["job"], query["path"])
            # Keep replacement/supersession serialized through disclosure and
            # check again after JSON construction, just like authorization.
            with app.lock:
                validate = lambda: app.validate_source(query["job"], query["path"], result["input_ref"])
                validate()
                self._json(result, validate=validate)
        elif self.command == "GET" and path == "/api/search":
            query = self._query({"job", "search", "input_sha256"})
            with app.lock:
                validate = lambda: app._get_search(query["job"], query["search"], query["input_sha256"])
                result = app.search_status(query["job"], query["search"], query["input_sha256"])
                self._json(result, validate=validate)
        elif self.command == "POST" and path in {"/api/search-start", "/api/search-cancel"}:
            if self.headers.get_all("Content-Type") != ["application/json"]:
                fail("INVALID_REQUEST")
            payload = json.loads(self._body(2048))
            selector = "query" if path == "/api/search-start" else "search"
            if type(payload) is not dict or set(payload) != {"job", "input_sha256", selector}:
                fail("INVALID_REQUEST")
            with app.lock:
                if selector == "query":
                    result = app.start_search(payload["job"], payload["input_sha256"], payload["query"])
                    validate = lambda: app._get_search(result["job"], result["search"], result["input_sha256"])
                    self._json(result, status=201, validate=validate)
                else:
                    result = app.cancel_search(payload["job"], payload["search"], payload["input_sha256"])
                    validate = lambda: app._search_job(payload["job"], payload["input_sha256"])
                    self._json(result, validate=validate)
        elif self.command == "POST" and path == "/api/import-start":
            if self.headers.get_all("Content-Type") != ["application/json"]:
                fail("INVALID_REQUEST")
            payload = json.loads(self._body(2048))
            if type(payload) is not dict or set(payload) != {"filename"} or type(payload["filename"]) is not str:
                fail("INVALID_UPLOAD")
            filename = payload["filename"]
            if len(filename) > 240 or any(ord(c) < 32 or c in "/\\" for c in filename) or not filename.lower().endswith(".zip"):
                fail("INVALID_UPLOAD")
            job = app.reserve(filename)
            self._json({"job": job.id}, status=201)
        elif self.command == "PUT" and path == "/api/import":
            if self.headers.get_all("Content-Type") != ["application/zip"]:
                fail("INVALID_UPLOAD")
            length = self._length(MAX_UPLOAD)
            query = self._query({"job"})
            with app.lock:
                job = app.get_job(query["job"])
                if job.status == "awaiting_upload" and time.monotonic() - job.created_at >= 30:
                    app.abandon(job, "UPLOAD_TIMEOUT")
                    fail("UPLOAD_TIMEOUT")
                if job is not app.pending or job.status != "awaiting_upload" or job.cancel.is_set() or app.closed:
                    fail("CANCELLED")
                job.status = "uploading"
            try:
                digest = hashlib.sha256()
                deadline = time.monotonic() + 30
                with job.path.open("xb") as output:
                    job.path.chmod(0o600)
                    remaining = length
                    while remaining:
                        if job.cancel.is_set() or app.closed:
                            fail("CANCELLED")
                        budget = deadline - time.monotonic()
                        if budget <= 0:
                            fail("UPLOAD_TIMEOUT")
                        self.connection.settimeout(min(5, budget))
                        chunk = self.rfile.read1(min(65536, remaining))
                        if not chunk:
                            fail("INVALID_UPLOAD")
                        output.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                        app.config.authorize()
                job.sha256 = digest.hexdigest()
                app.start(job)
            except BaseException as error:
                app.abandon(job, "CANCELLED" if job.cancel.is_set() or app.closed else error.code if isinstance(error, CoreError) else "INVALID_UPLOAD")
                raise
            self._json({"job": job.id}, status=202)
        elif self.command == "POST" and path == "/api/cancel":
            if self.headers.get_all("Content-Type") != ["application/json"]:
                fail("INVALID_REQUEST")
            raw = self._body(128)
            payload = json.loads(raw)
            if type(payload) is not dict or set(payload) != {"job"} or type(payload["job"]) is not str:
                fail("INVALID_REQUEST")
            self._json(app.cancel_job(payload["job"]))
        else:
            self._json({"error": "NOT_FOUND"}, status=404, authorize=False)

    def _handle(self):
        try:
            self._dispatch()
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            return
        except Exception as error:
            code = error.code if isinstance(error, CoreError) else "INVALID_REQUEST" if isinstance(error, (ValueError, UnicodeError)) else "INTERNAL_ERROR"
            # A revoked project must not release stale source-specific errors.
            if code != "UNAUTHORIZED":
                try:
                    self.server.workspace.config.authorize()
                except Exception:
                    code = "FORBIDDEN"
            status = 401 if code == "UNAUTHORIZED" else 403 if code == "FORBIDDEN" else 409 if code == "BUSY" else 400
            try:
                self._json({"error": code}, status=status, authorize=code != "UNAUTHORIZED", error=True)
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                pass

    do_GET = _handle
    do_POST = _handle
    do_PUT = _handle


def main(argv=None):
    parser = argparse.ArgumentParser(description="Experimental local Rentgen graphical workspace (Linux)")
    for name in ("registry", "identity-profile", "input-core"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--input-core-sha256", required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args(argv)
    if sys.platform != "linux":
        parser.error("This experimental ZIP workflow is currently supported on Linux only")
    if not 0 <= args.port <= 65535 or re.fullmatch(r"[0-9a-f]{64}", args.input_core_sha256) is None:
        parser.error("Invalid port or executable SHA-256")
    config = Config(args.registry.absolute(), args.identity_profile.absolute(), args.project,
                    args.input_core.absolute(), args.input_core_sha256)
    app = None
    server = None
    try:
        app = Workspace(config)
        server = Server(app, args.port)
        url = server.origin + "/#" + app.token
        print("Рентген: откройте адрес на этом компьютере. Не пересылайте ссылку сеанса.", flush=True)
        print(url, flush=True)
        if args.open_browser:
            webbrowser.open(url)
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    except CoreError as error:
        print("Рентген: " + error.code, file=sys.stderr)
        return 1
    finally:
        if app:
            app.begin_close()
        if server:
            server.server_close()
        if app:
            app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
