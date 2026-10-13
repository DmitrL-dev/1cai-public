"""Actual Rust + loopback HTTP comparison ownership and disclosure boundaries."""
import hashlib
import json
from pathlib import Path
import socket
import sys
import threading
import time
from urllib.parse import urlencode

import pytest

from rentgen_core import gui, gui_comparison, submitted_export
from rentgen_core.errors import CoreError
from test_local_gui import fixture_zip, post, prepare, request, running, upload, wait
from test_local_gui_search import payload as search_payload, start as search_start, search_wait
from test_metadata_three_way_materialize import PATH, xml
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Experimental GUI ZIP backend is Linux-only")


def start(server, job, before, name="after.zip"):
    status, result = post(server, "/api/comparison-start", {"job": job,
        "input_sha256": before["result"]["input"]["input_sha256"], "filename": name})
    assert status == 201, result
    return result["comparison"]


def poll(server, comparison):
    status, raw, _ = request(server, "/api/comparison?" + urlencode({"comparison": comparison}))
    return status, json.loads(raw)


def finish(app, server, comparison):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        status, outcome = poll(server, comparison)
        assert status == 200, outcome
        if outcome["status"] not in gui_comparison.ACTIVE:
            if app.comparison_worker:
                app.comparison_worker.join(timeout=5)
                assert not app.comparison_worker.is_alive()
            return outcome
        time.sleep(.01)
    pytest.fail("Comparison did not finish")


def submit(app, server, job, before, raw):
    comparison = start(server, job, before)
    status, body, _ = request(server, "/api/comparison-upload?comparison=" + comparison,
                             "PUT", raw, {"Content-Type": "application/zip"})
    assert status == 202, body
    return comparison, finish(app, server, comparison)


def binding(result):
    return {key: result[key] for key in ("pair", "before_sha256", "after_sha256")}


def page(server, result, offset=0, status="all"):
    code, data = post(server, "/api/comparison-page", {**binding(result), "offset": offset, "status": status})
    assert code == 200, data
    return data


def source(server, result, selected, selected_side, selected_path, **overrides):
    args = {**binding(result), "page": selected["page"]["id"], "side": selected_side, "path": selected_path, **overrides}
    code, raw, _ = request(server, "/api/comparison-source?" + urlencode(args))
    return code, json.loads(raw)


def current(server, job, before):
    code, raw, _ = request(server, "/api/comparison-current?" + urlencode({"job": job,
                               "input_sha256": before["result"]["input"]["input_sha256"]}))
    return code, json.loads(raw)


def pair_fixture():
    before = {PATH: xml(), "assets/removed.txt": b"removed\n", "assets/modified.txt": b"before\n",
              "assets/same.txt": b"same\n", "assets/bom.txt": b"\xef\xbb\xbfbom\n"}
    after = {PATH: xml(), "assets/added.txt": b"added\n", "assets/modified.txt": b"after\n",
             "assets/same.txt": b"same\n", "assets/bom.txt": b"bom\n"}
    return before, after


def ready_pair(app, server):
    left, right = pair_fixture()
    job, before = upload(server, zip_bytes(left))
    app.worker.join(timeout=5)
    comparison, found = submit(app, server, job, before, zip_bytes(right))
    assert found["status"] == "ready", found
    return job, before, comparison, found["result"]


def test_raw_classification_full_counts_bom_and_sources(running):
    app, server, root = running
    untouched = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    job, before, comparison, result = ready_pair(app, server)
    assert result["job"] == job and result["pair"] == comparison
    assert result["counts"] == {"added": 1, "removed": 1, "modified": 2, "unchanged": 2,
                                "changes": 4, "files": 6, "total": 6}
    assert result["scope"] == "submitted_zip_bytes" and result["comparison"] == "raw_sha256_and_size"
    assert set(result) == {"pair", "job", "before_sha256", "after_sha256", "before_filename", "after_filename", "counts", "scope", "comparison"}
    selected = page(server, result)
    assert [r["path"] for r in selected["rows"]] == sorted(set().union(*pair_fixture()), key=lambda p: p.encode())
    for row in selected["rows"]:
        for side, files in zip(("before", "after"), pair_fixture()):
            code, found = source(server, result, selected, side, row["path"])
            if row["path"] not in files:
                assert (code, found) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
            else:
                raw = files[row["path"]]
                assert code == 200 and found["text"] == raw.decode("utf-8-sig")
                assert found["size_bytes"] == len(raw)
                assert found["input_ref"]["raw_sha256"] == hashlib.sha256(raw).hexdigest()
                assert found["input_ref"]["input_sha256"] == result[side + "_sha256"]
    assert app.current.result == before["result"]
    assert untouched == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert len(list(Path(app.temp.name).glob("*.zip"))) == 2
    assert app.comparison_current.path.stat().st_mode & 0o777 == 0o600
    code, recovered = current(server, job, before)
    assert code == 200 and recovered["current"]["result"] == result and recovered["pending"] is None


def test_reversal_identical_archives_and_same_bytes_different_zip_hash(running):
    app, server, _ = running
    left, right = pair_fixture()
    job, before = upload(server, zip_bytes(right))
    app.worker.join(timeout=5)
    _, outcome = submit(app, server, job, before, zip_bytes(left))
    selected = page(server, outcome["result"])
    statuses = {row["path"]: row["status"] for row in selected["rows"]}
    assert statuses["assets/removed.txt"] == "added" and statuses["assets/added.txt"] == "removed"
    raw = zip_bytes(right)
    _, outcome = submit(app, server, job, before, raw)
    assert outcome["result"]["counts"]["changes"] == 0
    assert outcome["result"]["counts"]["unchanged"] == len(right)
    # ZIP container order can change without any entry-byte change.
    _, outcome = submit(app, server, job, before, zip_bytes(dict(reversed(list(right.items())))))
    assert outcome["result"]["before_sha256"] != outcome["result"]["after_sha256"]
    assert outcome["result"]["counts"]["changes"] == 0


def test_401_three_pages_filters_and_old_page_authority(running):
    app, server, _ = running
    files = {PATH: xml(), **{f"assets/Модуль{i:03}.txt": b"a\n" for i in range(400)}}
    job, before = upload(server, zip_bytes(files)); app.worker.join(timeout=5)
    _, outcome = submit(app, server, job, before, zip_bytes(files))
    result = outcome["result"]
    seen, previous = [], None
    for offset in (0, 200, 400):
        selected = page(server, result, offset)
        assert selected["page"] == {"id": selected["page"]["id"], "offset": offset, "limit": 200,
            "total": 401, "returned": 1 if offset == 400 else 200, "has_previous": offset > 0, "has_next": offset < 400}
        if previous:
            assert source(server, result, previous, "after", previous["rows"][0]["path"]) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
        assert source(server, result, selected, "after", selected["rows"][-1]["path"])[0] == 200
        seen += [row["path"] for row in selected["rows"]]
        previous = selected
    assert seen == sorted(files, key=lambda p: p.encode())
    empty = page(server, result, status="changes")
    assert empty["rows"] == [] and empty["page"]["total"] == 0 and empty["counts"]["total"] == 401
    assert len(app.comparison_current.page["rows"]) <= 200
    for status in ("added", "removed", "modified", "unchanged"):
        selected = page(server, result, status=status)
        assert selected["page"]["total"] == (401 if status == "unchanged" else 0)
        assert selected["counts"] == result["counts"]


@pytest.mark.parametrize("offset", [None, True, False, "200", [], {}, 200.0, -200, 1, 199, 201, 8001, 8200, 10**100])
def test_strict_offsets_preserve_current_page(running, offset):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    selected = page(server, result)
    assert post(server, "/api/comparison-page", {**binding(result), "offset": offset, "status": "all"}) == (400, {"error": "INVALID_QUERY_OPTIONS"})
    assert source(server, result, selected, "before", PATH)[0] == 200


@pytest.mark.parametrize("status", [None, True, [], {}, "ALL", "", "rename"])
def test_strict_filters(running, status):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    assert post(server, "/api/comparison-page", {**binding(result), "offset": 0, "status": status}) == (400, {"error": "INVALID_QUERY_OPTIONS"})


@pytest.mark.parametrize("override", [{"pair": "0" * 32}, {"before_sha256": "0" * 64}, {"after_sha256": "0" * 64},
    {"page": "0" * 32}, {"side": "other"}, {"side": "BEFORE"}, {"path": "../../etc/passwd"}, {"path": "/etc/passwd"}])
def test_forged_source_selectors(running, override):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    selected = page(server, result)
    assert source(server, result, selected, "before", PATH, **override) == (400, {"error": "SOURCE_NOT_AVAILABLE"})


def test_known_pending_reconciliation_cancel_timeout_and_no_upload_replay(running):
    app, server, _ = running
    job, before, _, result = ready_pair(app, server)
    selected = page(server, result)
    replacement = start(server, job, before)
    assert source(server, result, selected, "before", PATH)[0] == 400
    assert current(server, job, before)[1]["pending"]["comparison"] == replacement
    assert current(server, job, before)[1]["current"]["result"] == result
    assert post(server, "/api/import-start", {"filename": "new.zip"}) == (409, {"error": "BUSY"})
    assert post(server, "/api/comparison-cancel", {"comparison": replacement}) == (200, {"status": "cancelled", "cancel_requested": True})
    assert poll(server, replacement)[1]["status"] == "cancelled"
    assert request(server, "/api/comparison-upload?comparison=" + replacement, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 400
    replacement = start(server, job, before)
    app.comparison_pending.created_at -= 31
    assert poll(server, replacement)[1]["error"] == "UPLOAD_TIMEOUT"
    selected = page(server, result)
    assert source(server, result, selected, "after", PATH)[0] == 200


@pytest.mark.parametrize("raw", [b"invalid", zip_bytes({"unsupported.txt": b"hello"}), zip_bytes({"Catalogs/Fault.xml": b"<bad"})],
                         ids=["invalid-zip", "unsupported-designer", "invalid-xml"])
def test_failed_replacement_preserves_accepted_pair_and_two_files(running, raw):
    app, server, _ = running
    job, before, comparison, result = ready_pair(app, server)
    old_archive = app.comparison_current.path
    replacement, outcome = submit(app, server, job, before, raw)
    assert outcome["status"] == "error" and "result" not in outcome
    assert not app.comparison_pending.path.exists()
    assert app.comparison_current.id == comparison and old_archive.exists()
    assert len(list(Path(app.temp.name).glob("*.zip"))) == 2
    assert source(server, result, page(server, result), "after", PATH)[0] == 200


def test_ordinary_import_failure_preserves_pair_success_clears_it(running):
    app, server, _ = running
    job, before, comparison, result = ready_pair(app, server)
    archive = app.comparison_current.path
    _, failed = upload(server, b"invalid")
    app.worker.join(timeout=5)
    assert failed["status"] == "error" and archive.exists()
    assert source(server, result, page(server, result), "before", PATH)[0] == 200
    job2, outcome = upload(server, fixture_zip()); app.worker.join(timeout=5)
    assert outcome["status"] == "ready" and not archive.exists()
    assert app.comparison_current is app.comparison_pending is None
    assert poll(server, comparison) == (400, {"error": "COMPARISON_NOT_AVAILABLE"})
    assert current(server, job, before)[0] == 400
    assert current(server, job2, outcome)[1]["current"] is None
    assert len(list(Path(app.temp.name).glob("*.zip"))) == 1


@pytest.mark.parametrize("data,error", [(b"\xff", "SOURCE_ENCODING_UNSUPPORTED"),
    (b"hello\x00", "SOURCE_ENCODING_UNSUPPORTED"), (b"a" * (gui.MAX_SOURCE + 1), "SOURCE_TOO_LARGE")],
                         ids=["non-utf8", "control-byte", "over-256k"])
def test_source_bounds_encoding_and_controls(running, data, error):
    app, server, _ = running
    job, before = upload(server, fixture_zip()); app.worker.join(timeout=5)
    _, outcome = submit(app, server, job, before, zip_bytes({PATH: xml(), "assets/binary.dat": data}))
    result = outcome["result"]
    assert source(server, result, page(server, result), "after", "assets/binary.dat") == (400, {"error": error})


def test_active_cancellation_reaps_child_preserves_pair_and_three_zip_bound(running, monkeypatch):
    app, server, _ = running
    job, before, comparison, result = ready_pair(app, server)
    entered, proceed, children = threading.Event(), threading.Event(), []
    original = submitted_export.RustInputSession.open_import
    def opened(session, *args):
        value = original(session, *args)
        children.append(session.process); entered.set()
        assert proceed.wait(5)
        return value
    monkeypatch.setattr(submitted_export.RustInputSession, "open_import", opened)
    replacement = start(server, job, before)
    assert request(server, "/api/comparison-upload?comparison=" + replacement, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
    assert entered.wait(5)
    worker = app.comparison_worker
    assert not worker.daemon and children[0].poll() is None
    assert len(list(Path(app.temp.name).glob("*.zip"))) == 3
    try:
        assert post(server, "/api/comparison-cancel", {"comparison": replacement})[1]["cancel_requested"]
        assert app.comparison_worker is worker
        assert post(server, "/api/comparison-start", {"job": job, "input_sha256": app.current.sha256, "filename": "again.zip"})[0] == 409
        assert post(server, "/api/import-start", {"filename": "again.zip"})[0] == 409
    finally:
        proceed.set()
    outcome = finish(app, server, replacement)
    assert outcome["status"] == "cancelled" and children[0].poll() is not None
    assert app.comparison_worker is worker and not worker.is_alive()
    assert app.comparison_current.id == comparison and len(list(Path(app.temp.name).glob("*.zip"))) == 2
    assert source(server, result, page(server, result), "after", PATH)[0] == 200


def test_waiting_cancel_does_not_start_child(running, monkeypatch):
    app, server, _ = running
    job, before = upload(server, fixture_zip()); app.worker.join(timeout=5)
    comparison = start(server, job, before)
    entered = []
    original = gui_comparison.RustInputSession.__enter__
    def opened(session):
        entered.append(session)
        return original(session)
    monkeypatch.setattr(gui_comparison.RustInputSession, "__enter__", opened)
    app.io_lock.acquire()
    try:
        assert request(server, "/api/comparison-upload?comparison=" + comparison, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
        assert post(server, "/api/comparison-cancel", {"comparison": comparison})[1]["cancel_requested"]
        assert app.comparison_worker.is_alive()
    finally:
        app.io_lock.release()
    assert finish(app, server, comparison)["status"] == "cancelled" and entered == []


def test_upload_disconnect_releases_staging(running):
    app, server, _ = running
    job, before = upload(server, fixture_zip()); app.worker.join(timeout=5)
    comparison = start(server, job, before)
    sock = socket.create_connection(("127.0.0.1", server.server_port))
    head = f"PUT /api/comparison-upload?comparison={comparison} HTTP/1.0\r\nHost: {server.host}\r\nOrigin: {server.origin}\r\nX-Rentgen-Session: {app.token}\r\nContent-Type: application/zip\r\nContent-Length: 1000\r\n\r\n"
    sock.sendall(head.encode() + b"partial"); sock.close()
    outcome = finish(app, server, comparison)
    assert outcome["status"] == "error" and not app.comparison_pending.path.exists()


@pytest.mark.parametrize("kind", ["status", "current", "page", "source"])
def test_release_reauthorizes_after_json_serialization(running, monkeypatch, kind):
    app, server, _ = running
    job, before, comparison, result = ready_pair(app, server)
    selected = page(server, result)
    original_dumps, original_authorize = gui.json.dumps, gui.Config.authorize
    revoked = threading.Event()
    def dumps(value, *args, **kwargs):
        raw = original_dumps(value, *args, **kwargs)
        if isinstance(value, dict) and ("result" in value or "current" in value or "rows" in value or "text" in value):
            revoked.set()
        return raw
    def authorize(config):
        if revoked.is_set():
            raise CoreError("ACCESS_DENIED", "denied")
        original_authorize(config)
    monkeypatch.setattr(gui.json, "dumps", dumps)
    monkeypatch.setattr(gui.Config, "authorize", authorize)
    if kind == "status":
        response = poll(server, comparison)
    elif kind == "current":
        response = current(server, job, before)
    elif kind == "page":
        response = post(server, "/api/comparison-page", {**binding(result), "offset": 0, "status": "all"})
    else:
        response = source(server, result, selected, "before", PATH)
    assert response == (403, {"error": "FORBIDDEN"})


@pytest.mark.parametrize("kind", ["page", "source"])
def test_release_revalidates_page_after_serialization(running, monkeypatch, kind):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    selected = page(server, result)
    original = gui.json.dumps
    def dumps(value, *args, **kwargs):
        raw = original(value, *args, **kwargs)
        if isinstance(value, dict) and ("rows" in value or "text" in value):
            app._invalidate_comparison_page()
        return raw
    monkeypatch.setattr(gui.json, "dumps", dumps)
    if kind == "page":
        response = post(server, "/api/comparison-page", {**binding(result), "offset": 0, "status": "all"})
    else:
        response = source(server, result, selected, "before", PATH)
    assert response == (400, {"error": "COMPARISON_NOT_AVAILABLE" if kind == "page" else "SOURCE_NOT_AVAILABLE"})


def test_session_gate_and_request_shapes(running):
    app, server, _ = running
    job, before, comparison, result = ready_pair(app, server)
    selected = page(server, result)
    for endpoint in ("/api/comparison?comparison=" + comparison,
                     "/api/comparison-current?job=" + job + "&input_sha256=" + app.current.sha256,
                     "/api/comparison-source?" + urlencode({**binding(result), "page": selected["page"]["id"], "side": "before", "path": PATH})):
        code, raw, _ = request(server, endpoint, token=False)
        assert code == 401 and json.loads(raw) == {"error": "UNAUTHORIZED"}
    assert post(server, "/api/comparison-start", {"job": job, "input_sha256": app.current.sha256, "filename": "../bad.zip"}) == (400, {"error": "INVALID_UPLOAD"})
    assert post(server, "/api/comparison-page", {**binding(result), "offset": 0, "status": "all", "path": "/etc/passwd"})[0] == 400
    assert request(server, "/api/comparison?comparison=" + comparison + "&comparison=" + comparison)[0] == 400


def test_max_union_is_8192_and_offset_8000(running):
    app, server, _ = running
    left = {"Catalogs/Before.xml": xml(name="Before"), **{f"before/{i:04}.txt": b"a" for i in range(4095)}}
    right = {"Catalogs/After.xml": xml(name="After"), **{f"after/{i:04}.txt": b"b" for i in range(4095)}}
    job, before = upload(server, zip_bytes(left)); app.worker.join(timeout=5)
    _, outcome = submit(app, server, job, before, zip_bytes(right))
    assert outcome["status"] == "ready", outcome
    result = outcome["result"]
    assert result["counts"]["total"] == 8192 and result["counts"]["added"] == result["counts"]["removed"] == 4096
    selected = page(server, result, 8000)
    assert len(selected["rows"]) == 192 and not selected["page"]["has_next"]
    assert source(server, result, selected, "before", selected["rows"][-1]["path"])[0] == 200


def test_changed_owned_archive_fails_closed(running):
    app, server, _ = running
    _, _, _, result = ready_pair(app, server)
    selected = page(server, result)
    app.comparison_current.path.write_bytes(fixture_zip())
    code, response = source(server, result, selected, "after", PATH)
    assert code == 400 and "text" not in response and response["error"].startswith("IMPORT_")


def test_all_rust_lifetimes_serialized_across_search_comparison_and_import(running, monkeypatch):
    app, server, _ = running
    job, before, _, result = ready_pair(app, server)
    active, maximum, processes = set(), [0], []
    entered, proceed = threading.Event(), threading.Event()
    original_enter = submitted_export.RustInputSession.__enter__
    original_exit = submitted_export.RustInputSession.__exit__
    original_open = submitted_export.RustInputSession.open_import
    def enter(session):
        value = original_enter(session)
        active.add(session.process.pid); processes.append(session.process)
        maximum[0] = max(maximum[0], len(active))
        return value
    def exit(session, *args):
        try:
            return original_exit(session, *args)
        finally:
            active.discard(session.process.pid)
    def opened(session, *args):
        value = original_open(session, *args)
        if not entered.is_set():
            entered.set()
            assert proceed.wait(5)
        return value
    monkeypatch.setattr(submitted_export.RustInputSession, "__enter__", enter)
    monkeypatch.setattr(submitted_export.RustInputSession, "__exit__", exit)
    monkeypatch.setattr(submitted_export.RustInputSession, "open_import", opened)
    selected = search_start(server, search_payload(job, before))
    assert entered.wait(5)
    comparison = start(server, job, before)
    try:
        assert request(server, "/api/comparison-upload?comparison=" + comparison, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
        assert app.comparison_worker.is_alive() and len(active) == maximum[0] == 1
    finally:
        proceed.set()
    assert search_wait(server, selected)["status"] == "ready"
    assert finish(app, server, comparison)["status"] == "ready"
    assert maximum[0] == 1 and not active and all(p.poll() is not None for p in processes)
    # A normal import waiting behind a search must not start a second child.
    entered.clear(); proceed.clear(); maximum[0] = 0; processes.clear()
    selected = search_start(server, search_payload(job, before))
    assert entered.wait(5)
    next_job = prepare(server)
    try:
        assert request(server, "/api/import?job=" + next_job, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
        assert len(active) == maximum[0] == 1
    finally:
        proceed.set()
    assert wait(server, next_job)["status"] == "ready"
    app.worker.join(timeout=5); app.search_worker.join(timeout=5)
    assert maximum[0] == 1 and not active and all(p.poll() is not None for p in processes)


@pytest.mark.parametrize("active", [False, True])
def test_close_retains_and_reaps_comparison_worker(running, monkeypatch, active):
    app, server, _ = running
    job, before = upload(server, fixture_zip()); app.worker.join(timeout=5)
    entered, proceed, processes = threading.Event(), threading.Event(), []
    original_open = submitted_export.RustInputSession.open_import
    def opened(session, *args):
        value = original_open(session, *args)
        processes.append(session.process); entered.set()
        assert proceed.wait(5)
        return value
    monkeypatch.setattr(submitted_export.RustInputSession, "open_import", opened)
    comparison = start(server, job, before)
    if not active:
        app.io_lock.acquire()
    assert request(server, "/api/comparison-upload?comparison=" + comparison, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
    if active:
        assert entered.wait(5)
    worker = app.comparison_worker
    close_thread = threading.Thread(target=app.close)
    close_thread.start()
    try:
        deadline = time.monotonic() + 2
        while not app.closed and time.monotonic() < deadline:
            time.sleep(.01)
        assert app.closed and app.comparison_worker is worker and close_thread.is_alive()
    finally:
        proceed.set()
        if not active:
            app.io_lock.release()
    close_thread.join(timeout=5)
    assert not close_thread.is_alive() and not worker.is_alive()
    assert all(p.poll() is not None for p in processes)
    assert not Path(app.temp.name).exists()


def test_staging_reservation_refused_during_normal_import(running):
    app, server, _ = running
    job, before, _, _ = ready_pair(app, server)
    prepare(server)
    assert post(server, "/api/comparison-start", {"job": job, "input_sha256": app.current.sha256,
                                                "filename": "after.zip"}) == (409, {"error": "BUSY"})


def test_late_cancel_cannot_erase_accepted_pair(running):
    app, server, _ = running
    _, _, comparison, result = ready_pair(app, server)
    assert post(server, "/api/comparison-cancel", {"comparison": comparison}) == (200, {"status": "ready", "cancel_requested": False})
    assert poll(server, comparison)[1]["result"] == result
    assert app.comparison_current.path.exists()


def test_revocation_during_active_comparison_reaps_without_result(running, monkeypatch):
    app, server, _ = running
    job, before = upload(server, fixture_zip()); app.worker.join(timeout=5)
    entered, proceed, processes = threading.Event(), threading.Event(), []
    original = submitted_export.RustInputSession.open_import
    def opened(session, *args):
        value = original(session, *args)
        processes.append(session.process); entered.set()
        assert proceed.wait(5)
        return value
    monkeypatch.setattr(submitted_export.RustInputSession, "open_import", opened)
    comparison = start(server, job, before)
    assert request(server, "/api/comparison-upload?comparison=" + comparison, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
    assert entered.wait(5)
    try:
        context = app.config.context()
        with context.state.transaction(context.principal, write=True) as tx:
            tx._connection.execute("DELETE FROM membership_permissions WHERE permission='project:read'")
        assert poll(server, comparison) == (403, {"error": "FORBIDDEN"})
    finally:
        proceed.set()
    app.comparison_worker.join(timeout=5)
    assert not app.comparison_worker.is_alive() and all(p.poll() is not None for p in processes)
    assert not app.comparison_pending.rows and app.comparison_current is None
    assert not app.comparison_pending.path.exists()


@pytest.mark.parametrize("ending", ["cancel", "close"])
def test_cancel_or_close_at_ready_commit_preserves_previous_pair(running, monkeypatch, ending):
    app, server, _ = running
    job, before, comparison, result = ready_pair(app, server)
    old_pair, old_archive = app.comparison_current, app.comparison_current.path
    entered, proceed, assembled = threading.Event(), threading.Event(), threading.Event()
    original_compare = gui_comparison.compare_entries
    original_authorize = app._comparison_authorize
    def compare(*args):
        value = original_compare(*args)
        assembled.set()
        return value
    def authorize(item):
        original_authorize(item)
        # Pause after the final out-of-lock authorization but before commit.
        # Cancellation can win here; the commit must recheck inside the lock.
        if assembled.is_set() and not entered.is_set():
            entered.set()
            assert proceed.wait(5)
    monkeypatch.setattr(gui_comparison, "compare_entries", compare)
    monkeypatch.setattr(app, "_comparison_authorize", authorize)
    replacement = start(server, job, before)
    assert request(server, "/api/comparison-upload?comparison=" + replacement, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
    assert entered.wait(5)
    try:
        if ending == "cancel":
            assert post(server, "/api/comparison-cancel", {"comparison": replacement})[1]["cancel_requested"]
        else:
            app.begin_close()
    finally:
        proceed.set()
    app.comparison_worker.join(timeout=5)
    assert not app.comparison_worker.is_alive()
    assert app.comparison_pending.status == "cancelled" and not app.comparison_pending.path.exists()
    assert app.comparison_current is old_pair and old_archive.exists()
    assert old_pair.id == comparison and old_pair.counts == result["counts"]
