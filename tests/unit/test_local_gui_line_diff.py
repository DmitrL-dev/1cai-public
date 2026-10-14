"""Actual Rust/HTTP selected-row line alignment and disclosure boundaries."""
import json
import sys
import threading

import pytest

from rentgen_core import gui, gui_comparison
from rentgen_core.errors import CoreError
from test_local_gui import post, request, running, upload
from test_local_gui_comparison import binding, page, ready_pair, source, start, submit
from test_metadata_three_way_materialize import PATH, xml
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Experimental GUI ZIP backend is Linux-only")
ENDPOINT = "/api/comparison-line-diff"


def args(result, selected, path="assets/modified.txt", offset=0):
    return {**binding(result), "page": selected["page"]["id"], "path": path, "offset": offset}


def pair(app, server, left, right):
    job, before = upload(server, zip_bytes({PATH: xml(), **left}))
    app.worker.join(timeout=5)
    _, outcome = submit(app, server, job, before, zip_bytes({PATH: xml(), **right}))
    assert outcome["status"] == "ready", outcome
    return outcome["result"]


def test_actual_rust_modified_added_removed_empty_and_bom(running):
    app, server, root = running
    untouched = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = pair(app, server, {"assets/m.txt": b"\xef\xbb\xbfleft\r\n", "assets/removed.txt": b""},
                  {"assets/m.txt": b"right\n", "assets/added.txt": b""})
    selected = page(server, result)
    for path in ("assets/m.txt", "assets/removed.txt", "assets/added.txt"):
        code, found = post(server, ENDPOINT, args(result, selected, path))
        assert code == 200, found
        assert found["status"] == "complete" and found["coverage"] == {"alignment": "complete", "full_scan": True}
        row = next(r for r in selected["rows"] if r["path"] == path)
        for side in ("before", "after"):
            assert found[side]["present"] == (row[side] is not None)
            ref = found["input_refs"][side]
            if row[side] is None:
                assert ref is None and found[side]["size_bytes"] is None
            else:
                assert ref == {**row[side], "input_sha256": result[side + "_sha256"], "relative_path": path}
        if path == "assets/m.txt":
            assert found["before"]["bom"] is True and found["after"]["bom"] is False
            assert [r["kind"] for r in found["rows"]] == ["delete", "insert"]
            assert [r["eol"] for r in found["rows"]] == ["CRLF", "LF"]
        else:
            assert found["rows"] == []
    assert untouched == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_complete_recomputed_pages_and_exact_coverage(running):
    app, server, _ = running
    raw = b"same\n" * 401
    result = pair(app, server, {"assets/m.txt": raw}, {"assets/m.txt": raw})
    selected = page(server, result)
    rows = []
    for offset, count in ((0, 200), (200, 200), (400, 1)):
        code, found = post(server, ENDPOINT, args(result, selected, "assets/m.txt", offset))
        assert code == 200, found
        assert found["pagination"] == {"offset": offset, "limit": 200, "total": 401, "returned": count,
                                        "has_previous": offset > 0, "has_next": offset < 400}
        assert found["before"]["line_count"] == 401 and found["coverage"]["full_scan"]
        rows.extend(found["rows"])
    assert [r["before_line"] for r in rows] == list(range(1, 402))
    assert app.comparison_current.page["id"] == selected["page"]["id"]
    assert post(server, ENDPOINT, args(result, selected, "assets/m.txt", 600)) == (400, {"error": "INVALID_QUERY_OPTIONS"})


@pytest.mark.parametrize("raw,reason", [(b"x" * (256 * 1024 + 1), "SOURCE_TOO_LARGE"),
    (b"\xff", "SOURCE_ENCODING_UNSUPPORTED"), (b"x\x00", "SOURCE_ENCODING_UNSUPPORTED"),
    (b"a\n" * 4097, "LINE_LIMIT"), (b"a\n" * 1100, "WORK_LIMIT")])
def test_unavailable_is_row_free_and_original_sources_preserved(running, raw, reason):
    app, server, _ = running
    result = pair(app, server, {"assets/m.txt": raw}, {"assets/m.txt": b"b\n" * 1100})
    selected = page(server, result)
    code, found = post(server, ENDPOINT, args(result, selected, "assets/m.txt"))
    assert code == 200 and found["status"] == "unavailable" and found["reason"] == reason
    assert found["rows"] == [] and found["pagination"]["total"] == 0
    assert found["coverage"] == {"alignment": "unavailable", "full_scan": False}
    assert post(server, ENDPOINT, args(result, selected, "assets/m.txt", 200)) == (400, {"error": "INVALID_QUERY_OPTIONS"})
    code, found = source(server, result, selected, "after", "assets/m.txt")
    assert code == 200 and found["text"] == "b\n" * 1100


@pytest.mark.parametrize("change", [{"offset": True}, {"offset": -200}, {"offset": 1}, {"offset": 8200},
    {"offset": "0"}, {"path": "../secret"}, {"path": PATH + "/extra"}, {"pair": "0" * 32},
    {"before_sha256": "0" * 64}, {"after_sha256": "0" * 64}, {"page": "0" * 32}, {"extra": "x"}])
def test_strict_schema_and_selection_authority(running, change):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    selected = page(server, result)
    assert post(server, ENDPOINT, {**args(result, selected), **change})[0] == 400


def test_old_page_replacement_and_reader_gate(running):
    app, server, _ = running
    job, before, _, result = ready_pair(app, server)
    selected = page(server, result)
    app.io_lock.acquire()
    try:
        assert post(server, ENDPOINT, args(result, selected)) == (409, {"error": "BUSY"})
    finally:
        app.io_lock.release()
    new = page(server, result)
    assert post(server, ENDPOINT, args(result, selected)) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    start(server, job, before)
    assert post(server, ENDPOINT, args(result, new)) == (400, {"error": "SOURCE_NOT_AVAILABLE"})


@pytest.mark.parametrize("stage", ["read", "alignment", "serialization"])
@pytest.mark.parametrize("invalidate", ["page", "permission", "hash", "cancel"])
def test_authority_loss_suppresses_all_rows(running, monkeypatch, stage, invalidate):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    selected = page(server, result)
    revoked = threading.Event()
    original_authorize = gui.Config.authorize
    def authorize(config):
        if revoked.is_set():
            raise CoreError("ACCESS_DENIED", "denied")
        original_authorize(config)
    monkeypatch.setattr(gui.Config, "authorize", authorize)
    def lose():
        if invalidate == "page":
            app._invalidate_comparison_page()
        elif invalidate == "permission":
            revoked.set()
        elif invalidate == "cancel":
            app.comparison_current.cancel.set()
        else:
            # Use the selected row itself, regardless of its inventory position.
            next(r for r in app.comparison_current.page["rows"] if r["path"] == "assets/modified.txt")["after"]["raw_sha256"] = "0" * 64
    if stage == "read":
        original = gui_comparison.RustInputSession.read_entry
        def read(session, entry):
            value = original(session, entry)
            lose()
            return value
        monkeypatch.setattr(gui_comparison.RustInputSession, "read_entry", read)
    elif stage == "alignment":
        original = gui_comparison.bounded_line_diff
        def align(*a, **kw):
            lose()
            return original(*a, **kw)
        monkeypatch.setattr(gui_comparison, "bounded_line_diff", align)
    else:
        original = gui.json.dumps
        def dumps(value, *a, **kw):
            raw = original(value, *a, **kw)
            if isinstance(value, dict) and "pagination" in value:
                lose()
            return raw
        monkeypatch.setattr(gui.json, "dumps", dumps)
    code, found = post(server, ENDPOINT, args(result, selected))
    assert code in (400, 403) and set(found) == {"error"}, found
    assert "rows" not in found


def test_transport_query_and_escaping_response_bound(running):
    app, server, _ = running
    raw = b'"\\\t' * (256 * 1024 // 3)
    result = pair(app, server, {"assets/m.txt": raw}, {"assets/m.txt": raw[::-1]})
    selected = page(server, result)
    payload = json.dumps(args(result, selected, "assets/m.txt")).encode()
    headers = {"Content-Type": "application/json"}
    assert request(server, ENDPOINT, "POST", payload, headers, token=False)[0] == 401
    assert request(server, ENDPOINT + "?extra=x", "POST", payload, headers)[0] == 400
    code, body, _ = request(server, ENDPOINT, "POST", payload, headers)
    assert code == 200 and len(body) < 4 * 1024**2
    found = json.loads(body)
    assert found["status"] == "complete" and len(found["rows"]) <= 200


@pytest.mark.parametrize("budget", ["LINE_DIFF_WALL_SECONDS", "LINE_DIFF_CPU_SECONDS"])
@pytest.mark.parametrize("stage", ["read", "serialization"])
def test_budget_expiry_never_discloses_partial_rows(running, monkeypatch, budget, stage):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    selected = page(server, result)
    if stage == "read":
        original = gui_comparison.RustInputSession.read_entry
        def read(session, entry):
            raw = original(session, entry)
            monkeypatch.setattr(gui_comparison, budget, -1)
            return raw
        monkeypatch.setattr(gui_comparison.RustInputSession, "read_entry", read)
    else:
        original = gui.json.dumps
        def dumps(value, *a, **kw):
            raw = original(value, *a, **kw)
            if isinstance(value, dict) and "pagination" in value:
                monkeypatch.setattr(gui_comparison, budget, -1)
            return raw
        monkeypatch.setattr(gui.json, "dumps", dumps)
    assert post(server, ENDPOINT, args(result, selected)) == (400, {"error": "LINE_DIFF_TIMEOUT"})
    assert app.io_lock.acquire(blocking=False)
    app.io_lock.release()


def test_oversize_never_reads_and_cannot_exceed_json_guard(running, monkeypatch):
    app, server, _ = running
    result = pair(app, server, {"assets/m.txt": b"x" * (256 * 1024 + 1)}, {"assets/m.txt": b"x"})
    selected = page(server, result)
    def forbidden_read(*_):
        pytest.fail("Oversized source must not be read")
    monkeypatch.setattr(gui_comparison.RustInputSession, "read_entry", forbidden_read)
    code, found = post(server, ENDPOINT, args(result, selected, "assets/m.txt"))
    assert code == 200 and found["reason"] == "SOURCE_TOO_LARGE"
    original = gui.json.dumps
    def dumps(value, *a, **kw):
        if isinstance(value, dict) and "pagination" in value:
            return " " * (4 * 1024**2 + 1)
        return original(value, *a, **kw)
    monkeypatch.setattr(gui.json, "dumps", dumps)
    assert post(server, ENDPOINT, args(result, selected, "assets/m.txt")) == (400, {"error": "OUTPUT_LIMIT"})



def test_long_unicode_selected_path_uses_bounded_post_body(running):
    app, server, _ = running
    path = "/".join(["я" * 100] * 4) + ".txt"
    result = pair(app, server, {path: b"before"}, {path: b"after"})
    selected = page(server, result)
    payload = args(result, selected, path)
    assert len(json.dumps(payload).encode()) > 2048
    code, found = post(server, ENDPOINT, payload)
    assert code == 200 and found["path"] == path
