"""Bounded current-pair change-review downloads from already accepted byte rows.

No ZIP reads or source bodies. A single workspace gate owns the private spool
through delivery; replacement reservations invalidate its private generation.
Once headers are sent, failed revalidation closes an incomplete response rather
than appending an error to a report. Already delivered bytes cannot be recalled.
"""
import base64
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
from html import escape
import json
import tempfile

from .gui_comparison import ACTIVE, fail

JSON_LIMIT = 16 * 1024**2
HTML_LIMIT = 64 * 1024**2
SPOOL_LIMIT = 256 * 1024
CHUNK_SIZE = 64 * 1024
FORMATS = {"json": "application/json; charset=utf-8", "html": "text/html; charset=utf-8"}
FIELDS = {"pair", "before_sha256", "after_sha256", "format"}
STYLE = ("body{font:15px system-ui,sans-serif;margin:2rem;color:#172331;background:#fff}"
         "h1{font-size:1.7rem}dl{display:grid;grid-template-columns:max-content 1fr;gap:.35rem 1rem}"
         "dd{margin:0;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;table-layout:fixed}"
         "th,td{border:1px solid #bbc5ce;padding:.5rem;text-align:left;vertical-align:top;overflow-wrap:anywhere}"
         "th{background:#edf1f5}code{font-size:.8rem}caption{text-align:left;margin:1rem 0;font-weight:600}"
         "@media print{body{margin:0;font-size:10pt}thead{display:table-header-group}tr{break-inside:avoid}}")
STYLE_HASH = base64.b64encode(hashlib.sha256(STYLE.encode("utf-8")).digest()).decode("ascii")
CSP = "default-src 'none'; style-src 'sha256-" + STYLE_HASH + "'; base-uri 'none'; form-action 'none'"


def parse_request(raw):
    def unique(pairs):
        data = {}
        for key, value in pairs:
            if key in data:
                fail("INVALID_REQUEST")
            data[key] = value
        return data
    payload = json.loads(raw, object_pairs_hook=unique)
    if type(payload) is not dict or set(payload) != FIELDS:
        fail("INVALID_REQUEST")
    return payload


class BoundedWriter:
    """Encode one bounded token/row at a time, hash bytes, and fail before overflow."""

    def __init__(self, file, limit):
        self.file = file
        self.limit = limit
        self.length = 0
        self.digest = hashlib.sha256()

    def write(self, text):
        raw = text.encode("utf-8")
        if self.length + len(raw) > self.limit:
            fail("REPORT_TOO_LARGE")
        self.file.write(raw)
        self.digest.update(raw)
        self.length += len(raw)


def _row(row):
    # Explicit disclosure allowlist, even if accepted rows later gain fields.
    return {"path": row["path"], "status": row["status"], **{
        side: None if row[side] is None else {
            "raw_sha256": row[side]["raw_sha256"], "size_bytes": row[side]["size_bytes"]}
        for side in ("before", "after")}}


def _json_parts(metadata, rows):
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    yield "{"
    for index, (key, value) in enumerate(metadata.items()):
        if index:
            yield ","
        yield from encoder.iterencode(key)
        yield ":"
        yield from encoder.iterencode(value)
    yield ',"rows":['
    first = True
    for row in rows:
        if row["status"] == "unchanged":
            continue
        if not first:
            yield ","
        first = False
        yield from encoder.iterencode(_row(row))
    yield "]}\n"


def _html_parts(metadata, rows):
    yield ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<meta http-equiv="Content-Security-Policy" content="' + escape(CSP, quote=True) + '">'
           '<title>Submitted ZIP change review</title><style>' + STYLE + '</style></head><body>'
           '<h1>Submitted ZIP change review</h1>'
           '<p>Exact relative paths of the submitted ZIP entries. Each change compares raw SHA-256 '
           'and byte size. All added, removed, and modified entries are listed; unchanged entries are counted.</p>'
           '<p>This report contains no source bodies, semantic analysis, snapshot or live-base verification, '
           'or approval verdict.</p><dl><dt>Schema version</dt><dd>1</dd>')
    for side in ("before", "after"):
        yield '<dt>' + side.upper() + ' filename</dt><dd>' + escape(metadata[side + "_filename"], quote=True) + '</dd>'
        yield '<dt>' + side.upper() + ' ZIP SHA-256</dt><dd><code>' + metadata[side + "_sha256"] + '</code></dd>'
    for key in ("scope", "comparison", "path_scope"):
        yield '<dt>' + key + '</dt><dd>' + metadata[key] + '</dd>'
    yield '</dl><h2>Complete counts</h2><dl>'
    for key, value in metadata["counts"].items():
        yield '<dt>' + escape(key, quote=True) + '</dt><dd>' + str(value) + '</dd>'
    yield ('</dl><table><caption>All changes</caption><thead><tr><th>Exact relative path</th><th>Status</th>'
           '<th>BEFORE raw SHA-256</th><th>BEFORE bytes</th><th>AFTER raw SHA-256</th><th>AFTER bytes</th>'
           '</tr></thead><tbody>')
    for row in rows:
        if row["status"] == "unchanged":
            continue
        safe = _row(row)
        yield '<tr><td>' + escape(safe["path"], quote=True) + '</td><td>' + safe["status"] + '</td>'
        for side in ("before", "after"):
            value = safe[side]
            yield ('<td>—</td><td>—</td>' if value is None else '<td><code>' + value["raw_sha256"]
                   + '</code></td><td>' + str(value["size_bytes"]) + '</td>')
        yield '</tr>'
    yield '</tbody></table>'
    if metadata["counts"]["changes"] == 0:
        yield '<p>No added, removed, or modified entries.</p>'
    yield '</body></html>\n'


def serialize_report(file, metadata, rows, format):
    writer = BoundedWriter(file, JSON_LIMIT if format == "json" else HTML_LIMIT)
    parts = _json_parts(metadata, rows) if format == "json" else _html_parts(metadata, rows)
    for part in parts:
        writer.write(part)
    file.seek(0)
    return writer.length, writer.digest.hexdigest()


def _available(app):
    # A failed replacement may preserve the pair. Reservations still invalidate
    # an in-flight export, independently of whether that replacement succeeds.
    if ((app.pending and app.pending.status in ACTIVE)
            or (app.comparison_pending and app.comparison_pending.status in ACTIVE)):
        fail("COMPARISON_NOT_AVAILABLE")


@dataclass
class Report:
    file: object
    length: int
    sha256: str
    filename: str
    mime: str
    validate: object


@contextmanager
def comparison_report(app, pair, before_sha256, after_sha256, format):
    if type(format) is not str or format not in FORMATS:
        fail("INVALID_REQUEST")
    app.config.authorize()
    if not app.report_lock.acquire(blocking=False):
        fail("BUSY")
    try:
        with app.lock:
            item = app._pair(pair, before_sha256, after_sha256)
            _available(app)
            generation = app._report_generation
            rows = item.rows
            metadata = {"schema_version": 1, "scope": "submitted_zip_bytes",
                        "comparison": "raw_sha256_and_size", "path_scope": "exact_relative_path",
                        "before_filename": item.before.filename, "after_filename": item.filename,
                        "before_sha256": item.before_sha256, "after_sha256": item.sha256,
                        "counts": {key: item.counts[key] for key in
                                   ("added", "removed", "modified", "unchanged", "total", "files", "changes")}}

        def validate():
            # Callers also hold lock across the bounded header/chunk write.
            with app.lock:
                if (app._report_generation != generation
                        or app._pair(pair, before_sha256, after_sha256) is not item):
                    fail("COMPARISON_NOT_AVAILABLE")
                _available(app)

        with tempfile.SpooledTemporaryFile(max_size=SPOOL_LIMIT, mode="w+b", dir=app.temp.name) as file:
            length, digest = serialize_report(file, metadata, rows, format)
            app.config.authorize()
            validate()
            filename = f"rentgen-change-review-{before_sha256[:12]}-{after_sha256[:12]}.{format}"
            yield Report(file, length, digest, filename, FORMATS[format], validate)
    finally:
        app.report_lock.release()


def dispatch_report(handler, payload):
    app = handler.server.workspace
    with comparison_report(app, **payload) as report:
        headers = {"Content-Disposition": 'attachment; filename="' + report.filename + '"',
                   "X-Rentgen-Pair": payload["pair"],
                   "X-Rentgen-Before-SHA256": payload["before_sha256"],
                   "X-Rentgen-After-SHA256": payload["after_sha256"],
                   "X-Rentgen-Report-SHA256": report.sha256}
        app.config.authorize()
        with app.lock:
            report.validate()
            # The generic error handler must never append JSON after this point,
            # even if a network failure interrupts the header write itself.
            handler._report_started = True
            handler._headers(200, report.mime, report.length, extra=headers)
        while True:
            raw = report.file.read(CHUNK_SIZE)
            if not raw:
                break
            app.config.authorize()
            with app.lock:
                report.validate()
                handler.wfile.write(raw)
