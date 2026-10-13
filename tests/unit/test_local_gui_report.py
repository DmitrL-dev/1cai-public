"""Current accepted-pair report: real ZIP/HTTP, privacy, races and bounded memory."""
import hashlib
from html.parser import HTMLParser
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import tracemalloc

import pytest

from rentgen_core import gui, gui_comparison, gui_report
from rentgen_core.errors import CoreError
from test_local_gui import post, prepare, request, running, upload, wait
from test_local_gui_comparison import binding, finish, page, ready_pair, start, submit
from test_metadata_three_way_materialize import PATH, xml
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Experimental GUI ZIP backend is Linux-only")


def report(server, result, format="json", **overrides):
    return request(server, "/api/comparison-report", "POST",
                   json.dumps({**binding(result), "format": format, **overrides}).encode(),
                   {"Content-Type": "application/json"})


def receipt(result, raw, headers, format):
    assert headers["Content-Type"] == gui_report.FORMATS[format]
    assert int(headers["Content-Length"]) == len(raw)
    assert headers["X-Rentgen-Pair"] == result["pair"]
    for side in ("before", "after"):
        assert headers["X-Rentgen-" + side.title() + "-SHA256"] == result[side + "_sha256"]
    assert headers["X-Rentgen-Report-SHA256"] == hashlib.sha256(raw).hexdigest()
    name = f'rentgen-change-review-{result["before_sha256"][:12]}-{result["after_sha256"][:12]}.{format}'
    assert headers["Content-Disposition"] == f'attachment; filename="{name}"'
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in headers


def test_all_changes_beyond_page_filters_and_no_zip_reopen(running, monkeypatch):
    app, server, root = running
    same = {PATH: xml(), "assets/same.txt": b"private source body unchanged"}
    before_files = {**same, **{f"assets/modified{i:03}.txt": b"private before source body" for i in range(250)},
                    **{f"assets/removed{i:03}.txt": b"private removed source body" for i in range(201)}}
    after_files = {**same, **{f"assets/modified{i:03}.txt": b"private after source body" for i in range(250)},
                   **{f"assets/added{i:03}.txt": b"private added source body" for i in range(201)}}
    job, before = upload(server, zip_bytes(before_files)); app.worker.join(timeout=5)
    _, outcome = submit(app, server, job, before, zip_bytes(after_files))
    result = outcome["result"]
    selected = page(server, result, 200, "modified")
    assert len(selected["rows"]) == 50
    def forbidden(*args, **kwargs):
        raise AssertionError("Report must not read ZIPs or spawn Rust")
    monkeypatch.setattr(gui_comparison, "RustInputSession", forbidden)
    for format in ("json", "html"):
        code, raw, headers = report(server, result, format)
        assert code == 200, raw
        receipt(result, raw, headers, format)
        for secret in (app.token, job, result["pair"], app.config.project, str(root), app.temp.name,
                       "private before source body", "private after source body", "private source body unchanged"):
            assert secret.encode() not in raw
        if format == "json":
            data = json.loads(raw)
            assert set(data) == {"schema_version", "scope", "comparison", "path_scope", "before_filename",
                                 "after_filename", "before_sha256", "after_sha256", "counts", "rows"}
            assert data["schema_version"] == 1
            assert data["path_scope"] == "exact_relative_path"
            assert data["counts"] == {"added": 201, "removed": 201, "modified": 250,
                                      "unchanged": 2, "total": 654, "files": 654, "changes": 652}
            assert data["rows"] == [row for row in app.comparison_current.rows if row["status"] != "unchanged"]
            for row in data["rows"]:
                assert set(row) == {"path", "status", "before", "after"}
                for side, files in (("before", before_files), ("after", after_files)):
                    if row["path"] in files:
                        expected = files[row["path"]]
                        assert row[side] == {"raw_sha256": hashlib.sha256(expected).hexdigest(), "size_bytes": len(expected)}
                    else:
                        assert row[side] is None
        else:
            assert raw.count(b"<tr>") == 653
            assert b"assets/modified249.txt" in raw and b"assets/added200.txt" in raw and b"assets/removed200.txt" in raw
    assert app.comparison_current.page["id"] == selected["page"]["id"]


def test_identical_pair_has_zero_changes_with_complete_counts(running):
    app, server, _ = running
    raw = zip_bytes({PATH: xml(), "assets/file.txt": b"secret source"})
    job, before = upload(server, raw); app.worker.join(timeout=5)
    _, outcome = submit(app, server, job, before, raw)
    result = outcome["result"]
    for format in ("json", "html"):
        code, raw, headers = report(server, result, format)
        assert code == 200
        receipt(result, raw, headers, format)
        if format == "json":
            data = json.loads(raw)
            assert data["counts"]["unchanged"] == 2 and data["counts"]["changes"] == 0
            assert data["rows"] == []
        else:
            assert b"No added, removed, or modified entries." in raw
            assert raw.count(b"<tr>") == 1


class Parsed(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.attributes, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag); self.attributes.extend(attrs)

    def handle_data(self, data):
        self.text.append(data)


def test_escaped_original_names_paths_and_script_free_html(running):
    app, server, _ = running
    before_name = "BEFORE <img src=x onerror=alert(1)> & '\".zip"
    after_name = "AFTER <svg onload=alert(1)> & '\".zip"
    evil_path = "assets/Модуль & 'entry.txt"
    job = prepare(server, before_name)
    raw = zip_bytes({PATH: xml()})
    assert request(server, "/api/import?job=" + job, "PUT", raw, {"Content-Type": "application/zip"})[0] == 202
    before = wait(server, job); app.worker.join(timeout=5)
    comparison = start(server, job, before, after_name)
    raw = zip_bytes({PATH: xml(), evil_path: b"source body not disclosed"})
    assert request(server, "/api/comparison-upload?comparison=" + comparison, "PUT", raw,
                   {"Content-Type": "application/zip"})[0] == 202
    outcome = finish(app, server, comparison)
    assert outcome["status"] == "ready", outcome
    result = outcome["result"]
    code, raw, headers = report(server, result)
    assert code == 200
    data = json.loads(raw)
    assert data["before_filename"] == before_name and data["after_filename"] == after_name
    assert data["rows"][0]["path"] == evil_path
    code, raw, headers = report(server, result, "html")
    assert code == 200
    parsed = Parsed(); parsed.feed(raw.decode())
    assert before_name in parsed.text and after_name in parsed.text and evil_path in parsed.text
    assert not set(parsed.tags) & {"script", "img", "svg", "iframe", "object", "embed", "a", "form"}
    assert not any(key.startswith("on") or key in {"src", "href"} for key, _ in parsed.attributes)
    assert ("content", gui_report.CSP) in parsed.attributes
    assert "default-src 'none'" in gui_report.CSP
    assert hashlib.sha256(gui_report.STYLE.encode()).digest() == __import__("base64").b64decode(gui_report.STYLE_HASH)
    assert b"source body not disclosed" not in raw
    assert b"no source bodies, semantic analysis, snapshot or live-base verification" in raw
    assert b"or approval verdict." in raw


@pytest.mark.parametrize("overrides,error", [({"format": None}, "INVALID_REQUEST"),
    ({"format": []}, "INVALID_REQUEST"), ({"format": True}, "INVALID_REQUEST"),
    ({"format": "JSON"}, "INVALID_REQUEST"), ({"format": "xml"}, "INVALID_REQUEST"),
    ({"pair": "0" * 32}, "COMPARISON_NOT_AVAILABLE"), ({"pair": []}, "COMPARISON_NOT_AVAILABLE"),
    ({"before_sha256": "0" * 64}, "COMPARISON_NOT_AVAILABLE"),
    ({"after_sha256": True}, "COMPARISON_NOT_AVAILABLE")])
def test_report_selector_and_format_refusals(running, overrides, error):
    _, server, _ = running
    _, _, _, result = ready_pair(*running[:2])
    code, raw, headers = report(server, result, **overrides)
    assert (code, json.loads(raw)) == (400, {"error": error})
    assert "Content-Disposition" not in headers


def test_report_strict_request_and_transport_gate(running):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    data = {**binding(result), "format": "json"}
    raw = json.dumps(data).encode()
    for body in (b"[]", b"null", b"{", json.dumps({**data, "page": "anything"}).encode(),
                 json.dumps({key: value for key, value in data.items() if key != "format"}).encode(),
                 raw[:-1] + b',"format":"json"}'):
        code, response, _ = request(server, "/api/comparison-report", "POST", body, {"Content-Type": "application/json"})
        assert (code, json.loads(response)) == (400, {"error": "INVALID_REQUEST"})
    assert request(server, "/api/comparison-report?extra=x", "POST", raw, {"Content-Type": "application/json"})[0] == 400
    assert request(server, "/api/comparison-report", "POST", raw, {"Content-Type": "text/plain"})[0] == 400
    for headers, token in (({}, False), ({"Origin": "https://evil.test"}, True),
                            ({"Host": "evil.test"}, True), ({"X-Rentgen-Session": "wrong"}, True)):
        code, response, _ = request(server, "/api/comparison-report", "POST", raw,
                                  {"Content-Type": "application/json", **headers}, token=token)
        assert (code, json.loads(response)) == (401, {"error": "UNAUTHORIZED"})


@pytest.mark.parametrize("kind", ["comparison", "ordinary", "closed", "revoked"])
def test_serialize_race_revalidates_generation_and_authorization(running, monkeypatch, kind):
    app, server, _ = running
    job, before, _, result = ready_pair(app, server)
    original, authorize = gui_report.serialize_report, gui.Config.authorize
    revoked = threading.Event()
    def serialize(*args):
        value = original(*args)
        if kind == "comparison":
            app.reserve_comparison(job, result["before_sha256"], "replacement.zip")
            app.abandon_comparison(app.comparison_pending, "INVALID_ARCHIVE")
        elif kind == "ordinary":
            app.abandon(app.reserve("replacement.zip"), "INVALID_ARCHIVE")
        elif kind == "closed":
            app.begin_close()
        else:
            revoked.set()
        return value
    def check(config):
        if revoked.is_set():
            raise CoreError("ACCESS_DENIED", "revoked")
        authorize(config)
    monkeypatch.setattr(gui_report, "serialize_report", serialize)
    monkeypatch.setattr(gui.Config, "authorize", check)
    code, raw, headers = report(server, result)
    assert (code, json.loads(raw)) == ((403, {"error": "FORBIDDEN"}) if kind == "revoked"
                                     else (400, {"error": "COMPARISON_NOT_AVAILABLE"}))
    assert "Content-Disposition" not in headers
    assert not app.report_lock.locked()
    assert app.comparison_current.id == result["pair"]


def test_page_change_during_serialization_does_not_invalidate_report(running, monkeypatch):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    original = gui_report.serialize_report
    def serialize(*args):
        value = original(*args)
        app.comparison_page(**binding(result), offset=0, status="unchanged")
        return value
    monkeypatch.setattr(gui_report, "serialize_report", serialize)
    assert report(server, result)[0] == 200


@pytest.mark.parametrize("kind", ["comparison", "ordinary"])
def test_active_replacement_blocks_report_then_failed_replacement_restores_new_export(running, kind):
    app, server, _ = running
    job, _, _, result = ready_pair(app, server)
    if kind == "comparison":
        app.reserve_comparison(job, result["before_sha256"], "replacement.zip")
    else:
        app.reserve("replacement.zip")
    code, raw, _ = report(server, result)
    assert (code, json.loads(raw)) == (400, {"error": "COMPARISON_NOT_AVAILABLE"})
    if kind == "comparison":
        app.abandon_comparison(app.comparison_pending, "INVALID_ARCHIVE")
    else:
        app.abandon(app.pending, "INVALID_ARCHIVE")
    assert report(server, result)[0] == 200


def test_parallel_busy_close_waits_without_workspace_lock_and_spool_cleanup(running, monkeypatch):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    entered, proceed, closed = threading.Event(), threading.Event(), threading.Event()
    files, responses = [], []
    original = gui_report.serialize_report
    def serialize(file, *args):
        file.rollover(); files.append(file)
        entered.set()
        assert proceed.wait(10)
        return original(file, *args)
    monkeypatch.setattr(gui_report, "serialize_report", serialize)
    download = threading.Thread(target=lambda: responses.append(report(server, result)))
    download.start()
    try:
        assert entered.wait(5)
        code, raw, _ = report(server, result, "html")
        assert (code, json.loads(raw)) == (409, {"error": "BUSY"})
        closer = threading.Thread(target=lambda: (app.close(), closed.set()))
        closer.start()
        assert not closed.wait(.05)
        assert app.lock.acquire(timeout=1)
        app.lock.release()
        assert Path(app.temp.name).exists() and not files[0].closed
    finally:
        proceed.set()
        download.join(timeout=10)
        if "closer" in locals():
            closer.join(timeout=10)
    assert not download.is_alive() and closed.is_set()
    assert responses[0][0] == 400
    assert json.loads(responses[0][1]) == {"error": "COMPARISON_NOT_AVAILABLE"}
    assert files[0].closed and not Path(app.temp.name).exists() and not app.report_lock.locked()


@pytest.mark.parametrize("format,limit_name", [("json", "JSON_LIMIT"), ("html", "HTML_LIMIT")])
def test_limit_returns_explicit_error_without_attachment_or_partial_report(running, monkeypatch, format, limit_name):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    monkeypatch.setattr(gui_report, limit_name, 64)
    code, raw, headers = report(server, result, format)
    assert (code, json.loads(raw)) == (400, {"error": "REPORT_TOO_LARGE"})
    assert "Content-Disposition" not in headers and not app.report_lock.locked()


@pytest.mark.parametrize("kind", ["revoked", "replacement", "closed"])
def test_midstream_invalidation_closes_incomplete_body_without_json_error(running, monkeypatch, kind):
    app, server, _ = running
    files = {PATH: xml(), **{f"assets/{i:04}.txt": b"before" for i in range(400)}}
    job, before = upload(server, zip_bytes(files)); app.worker.join(timeout=5)
    _, outcome = submit(app, server, job, before, zip_bytes({path: xml() if path == PATH else b"after" for path in files}))
    result = outcome["result"]
    original_headers, authorize = gui.Handler._headers, gui.Config.authorize
    revoked = threading.Event()
    class Writer:
        def __init__(self, stream): self.stream = stream
        def write(self, value):
            count = self.stream.write(value)
            if kind == "revoked":
                revoked.set()
            elif kind == "replacement":
                app.abandon(app.reserve("replacement.zip"), "INVALID_ARCHIVE")
            else:
                app.begin_close()
            return count
        def __getattr__(self, name): return getattr(self.stream, name)
    def headers(handler, *args, **kwargs):
        original_headers(handler, *args, **kwargs)
        if getattr(handler, "_report_started", False):
            handler.wfile = Writer(handler.wfile)
    def check(config):
        if revoked.is_set(): raise CoreError("ACCESS_DENIED", "revoked")
        authorize(config)
    monkeypatch.setattr(gui.Handler, "_headers", headers)
    monkeypatch.setattr(gui.Config, "authorize", check)
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=15)
    connection.request("POST", "/api/comparison-report", json.dumps({**binding(result), "format": "json"}),
                       {"Origin": server.origin, "X-Rentgen-Session": app.token, "Content-Type": "application/json"})
    response = connection.getresponse()
    assert response.status == 200 and int(response.headers["Content-Length"]) > gui_report.CHUNK_SIZE
    with pytest.raises(http.client.IncompleteRead) as found:
        response.read()
    connection.close()
    assert len(found.value.partial) == gui_report.CHUNK_SIZE
    assert found.value.partial.startswith(b'{"schema_version":1')
    assert b'"error":' not in found.value.partial and b'HTTP/1.' not in found.value.partial
    assert not app.report_lock.locked()


def worst_case_rows(character):
    # Conservative envelope of the union/path bounds: 8,192 maximum-size rows.
    # Double quotes are outside the accepted portable path contract and test
    # the writer cap defensively; apostrophes and ampersands are accepted.
    rows = []
    for index in range(gui_comparison.MAX_ROWS):
        prefix = f"assets/{index:04}/"
        path = prefix + character * (1024 - len(prefix))
        assert len(path.encode()) == 1024
        rows.append({"path": path, "status": "modified",
                     "before": {"raw_sha256": "a" * 64, "size_bytes": 4 * 1024**2},
                     "after": {"raw_sha256": "b" * 64, "size_bytes": 4 * 1024**2}})
    return tuple(rows)


def maximum_metadata():
    return {"schema_version": 1, "scope": "submitted_zip_bytes", "comparison": "raw_sha256_and_size",
            "path_scope": "exact_relative_path", "before_filename": '"' * 236 + ".zip",
            "after_filename": '"' * 236 + ".zip", "before_sha256": "c" * 64, "after_sha256": "d" * 64,
            "counts": {"added": 0, "removed": 0, "modified": 8192, "unchanged": 0,
                       "total": 8192, "files": 8192, "changes": 8192}}


@pytest.mark.parametrize("format,character,too_large", [("json", "'", False), ("json", '"', True),
                                                        ("html", "'", False), ("html", "&", False)])
def test_maximum_path_row_bounds_and_incremental_peak_memory(tmp_path, format, character, too_large, record_property):
    rows, metadata = worst_case_rows(character), maximum_metadata()
    # Measure incremental export allocations, excluding the already retained pair.
    tracemalloc.start()
    try:
        with tempfile.SpooledTemporaryFile(max_size=gui_report.SPOOL_LIMIT, mode="w+b", dir=tmp_path) as file:
            if too_large:
                with pytest.raises(CoreError) as found:
                    gui_report.serialize_report(file, metadata, rows, format)
                assert found.value.code == "REPORT_TOO_LARGE"
                length = file.tell()
                assert length <= gui_report.JSON_LIMIT
            else:
                length, digest = gui_report.serialize_report(file, metadata, rows, format)
                actual = hashlib.sha256()
                read_length = 0
                while raw := file.read(gui_report.CHUNK_SIZE):
                    actual.update(raw); read_length += len(raw)
                assert read_length == length and actual.hexdigest() == digest
                assert length <= (gui_report.JSON_LIMIT if format == "json" else gui_report.HTML_LIMIT)
            assert file._rolled
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    record_property("serialized_bytes", length)
    record_property("incremental_peak_bytes", peak)
    print(f"REPORT_MEMORY format={format} escape={ord(character)} bytes={length} peak={peak} too_large={too_large}")
    assert peak < 2 * 1024**2
    assert list(tmp_path.iterdir()) == []


def test_real_rust_maximum_union_and_1024_byte_escaped_paths(running):
    app, server, _ = running
    archives = []
    for side, metadata_path in (("before", PATH), ("after", "Catalogs/Other.xml")):
        files = {metadata_path: xml(name="Products" if side == "before" else "Other")}
        for index in range(4095):
            prefix = f"assets/{side}/{index:04}/"
            path = prefix + "'" * (1024 - len(prefix))
            files[path] = b"a" if side == "before" else b"b"
        archives.append(zip_bytes(files))
    job, before = upload(server, archives[0]); app.worker.join(timeout=5)
    assert before["status"] == "ready", before
    _, outcome = submit(app, server, job, before, archives[1])
    assert outcome["status"] == "ready", outcome
    result = outcome["result"]
    assert result["counts"] == {"added": 4096, "removed": 4096, "modified": 0,
                                "unchanged": 0, "total": 8192, "files": 8192, "changes": 8192}
    page(server, result, offset=8000, status="all")
    for format in ("json", "html"):
        code, raw, headers = report(server, result, format)
        assert code == 200
        receipt(result, raw, headers, format)
        if format == "json":
            data = json.loads(raw)
            assert len(data["rows"]) == 8192 and data["counts"] == result["counts"]
            assert sum(len(row["path"].encode()) == 1024 for row in data["rows"]) == 8190
        else:
            assert raw.count(b"<tr>") == 8193
            assert raw.count(b"&#x27;") == gui_report.CSP.count("'") + sum(
                row["path"].count("'") for row in app.comparison_current.rows)
    assert not app.report_lock.locked()


def test_successful_replacement_denies_old_pair_report(running):
    app, server, _ = running
    job, before, _, old = ready_pair(app, server)
    _, outcome = submit(app, server, job, before, zip_bytes({PATH: xml(), "assets/new.txt": b"new"}))
    assert outcome["status"] == "ready"
    code, raw, headers = report(server, old)
    assert (code, json.loads(raw)) == (400, {"error": "COMPARISON_NOT_AVAILABLE"})
    assert "Content-Disposition" not in headers
    assert report(server, outcome["result"])[0] == 200
