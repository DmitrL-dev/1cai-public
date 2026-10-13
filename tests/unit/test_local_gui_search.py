"""Archive-wide GUI search against real owned Rust ZIPs and loopback HTTP."""
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from urllib.parse import quote, urlencode

import pytest

from rentgen_core import gui, submitted_export
from rentgen_core.errors import CoreError
from test_local_gui import fixture_zip, post, prepare, request, running, upload, wait
from test_metadata_three_way_materialize import xml
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Experimental GUI ZIP backend is Linux-only")

TARGET = "Documents/ПоследнийПуть.xml"
MODULE = "CommonModules/Shared/Ext/Module.bsl"


def archive_201():
    files = {f"Catalogs/A{index:03}.xml": xml(name=f"A{index:03}") for index in range(200)}
    files[TARGET] = xml(
        "<Synonym><item><lang>ru</lang><content>ОтдельныйСиноним</content></item></Synonym>",
        name="СверхЦель",
    ).replace(b"<Catalog ", b"<Document ").replace(b"</Catalog>", b"</Document>")
    files[MODULE] = "Процедура Модуль()\nКонецПроцедуры\n".encode()
    return zip_bytes(files), files


def payload(job, outcome, query="", *, kind=None):
    args = {"job": job, "input_sha256": outcome["result"]["input"]["input_sha256"], "query": query}
    if kind is not None:
        args["kind"] = kind
    return args


def start(server, args):
    status, result = post(server, "/api/search-start", args)
    assert status == 201, result
    assert set(result) == {"search", "job", "input_sha256", "kind", "object_path", "prefix"}
    assert result["kind"] == args.get("kind", "metadata")
    assert result["object_path"] == args.get("object_path")
    assert result["prefix"] == (args["object_path"][:-4] + "/" if args.get("object_path") else None)
    return {key: result[key] for key in ("search", "job", "input_sha256")}


def poll(server, selector):
    status, raw, _ = request(server, "/api/search?" + urlencode(selector))
    return status, json.loads(raw)


def search_wait(server, selector):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        status, result = poll(server, selector)
        assert status == 200, result
        if result["status"] != "searching":
            return result
        time.sleep(.01)
    pytest.fail("GUI search did not finish")


def source(server, job, path=TARGET, suffix=""):
    status, raw, _ = request(server, "/api/source?job=" + job + "&path=" + quote(path) + suffix)
    return status, json.loads(raw)


def block_search(monkeypatch):
    """Pause only after a real Rust search child owns accepted immutable bytes."""
    entered, proceed, children = threading.Event(), threading.Event(), []
    original = submitted_export.RustInputSession.open_import

    def opened(session, *args):
        result = original(session, *args)
        if threading.current_thread().name == "rentgen-gui-search":
            children.append(session.process)
            entered.set()
            assert proceed.wait(5)
        return result

    monkeypatch.setattr(submitted_export.RustInputSession, "open_import", opened)
    return entered, proceed, children


def test_archive_wide_unicode_search_and_verified_201st_source(running):
    app, server, root = running
    before = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    raw, files = archive_201()
    job, outcome = upload(server, raw)
    initial = outcome["result"]
    assert initial["counts"]["metadata_objects"] == 201
    assert len(initial["objects"]) == 200 and initial["objects_truncated"]
    assert source(server, job)[1] == {"error": "SOURCE_NOT_AVAILABLE"}
    for query in ("сВЕРХцЕЛЬ", "оТДЕЛЬНЫЙсИНОНИМ", "последнийпуть", "DOCUMENT"):
        selector = start(server, payload(job, outcome, query))
        found = search_wait(server, selector)
        assert found["status"] == "ready", found
        assert found["query"] == query
        assert found["job"] == job and found["input_sha256"] == hashlib.sha256(raw).hexdigest()
        result = found["result"]
        assert result["matching_objects"] == 1 and not result["objects_truncated"]
        assert result["objects"][0]["input_ref"]["relative_path"] == TARGET
        assert result["counts"] == initial["counts"] and result["by_type"] == initial["by_type"]
        assert result["modules"] == initial["modules"]
        status, preview = source(server, job)
        assert status == 200 and preview["text"].encode() == files[TARGET]
        assert preview["input_ref"] == {
            "relative_path": TARGET, "input_sha256": hashlib.sha256(raw).hexdigest(),
            "raw_sha256": hashlib.sha256(files[TARGET]).hexdigest(),
        }
    assert app.current.result == initial  # Searches do not replace the import result.
    assert before == {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_empty_missing_query_and_bounded_result_counts(running):
    _, server, _ = running
    job, outcome = upload(server, archive_201()[0])
    for query, expected, shown, truncated in [("", 201, 200, True), ("not-in-export", 0, 0, False), ("я" * 128, 0, 0, False)]:
        found = search_wait(server, start(server, payload(job, outcome, query)))
        result = found["result"]
        assert found["status"] == "ready"
        assert result["matching_objects"] == expected
        assert len(result["objects"]) == shown and result["objects_truncated"] is truncated
        assert result["counts"]["metadata_objects"] == 201 and result["counts"]["modules"] == 1
        assert len(result["modules"]) == 1  # Modules remain the original bounded inventory.
    assert source(server, job)[1] == {"error": "SOURCE_NOT_AVAILABLE"}


@pytest.mark.parametrize("query", [None, 12, {}, [], "x" * 257, "я" * 129, "😀" * 65, "\ud800"])
def test_invalid_or_utf8_overflow_query_never_starts_child(running, query):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    status, result = post(server, "/api/search-start", payload(job, outcome, query))
    assert status == 400 and result == {"error": "INVALID_QUERY_OPTIONS"}
    assert app.search is None and app.search_worker is None


@pytest.mark.parametrize("change", ["missing", "limit", "path", "raw_sha256"])
def test_search_accepts_no_client_limit_path_or_raw_hash(running, change):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    args = payload(job, outcome)
    if change == "missing":
        del args["query"]
    else:
        args[change] = 200 if change == "limit" else "forged"
    assert post(server, "/api/search-start", args) == (400, {"error": "INVALID_REQUEST"})
    assert app.search_worker is None


def test_search_and_source_disallow_forged_sha_path_old_search_and_job(running):
    _, server, _ = running
    job, outcome = upload(server, archive_201()[0])
    args = payload(job, outcome, "СверхЦель")
    assert post(server, "/api/search-start", {**args, "input_sha256": "0" * 64})[0] == 400
    selector = start(server, args)
    assert search_wait(server, selector)["status"] == "ready"
    assert poll(server, {**selector, "input_sha256": "0" * 64})[0] == 400
    assert poll(server, {**selector, "search": "0" * 32})[0] == 400
    assert source(server, job, "../../etc/passwd")[0] == 400
    assert source(server, job, suffix="&raw_sha256=" + "0" * 64) == (400, {"error": "INVALID_REQUEST"})
    later = start(server, {**args, "query": "A001"})
    assert search_wait(server, later)["status"] == "ready"
    assert poll(server, selector)[0] == 400
    assert source(server, job)[1] == {"error": "SOURCE_NOT_AVAILABLE"}
    new_job, _ = upload(server, fixture_zip())
    assert new_job != job
    assert poll(server, later)[0] == 400 and source(server, job)[0] == 400
    assert post(server, "/api/search-start", args)[0] == 400
    assert post(server, "/api/search-cancel", {**selector, "search": None})[0] == 400


def test_server_owned_search_reference_and_archive_hash_are_reverified(running):
    app, server, _ = running
    raw, _ = archive_201()
    job, outcome = upload(server, raw)
    selector = start(server, payload(job, outcome, "СверхЦель"))
    assert search_wait(server, selector)["status"] == "ready"
    row = app.search.result["objects"][0]["input_ref"]
    digest = row["raw_sha256"]
    row["raw_sha256"] = "0" * 64
    assert source(server, job) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    row["raw_sha256"] = digest
    app.current.path.write_bytes(fixture_zip())
    status, result = source(server, job)
    assert status == 400 and result == {"error": "IMPORT_HASH_MISMATCH"}


@pytest.mark.parametrize("endpoint", ["search", "source"])
def test_search_and_source_reauthorize_after_serialization(running, monkeypatch, endpoint):
    app, server, _ = running
    job, outcome = upload(server, archive_201()[0])
    selector = start(server, payload(job, outcome, "СверхЦель"))
    assert search_wait(server, selector)["status"] == "ready"
    revoked = threading.Event()
    original_dump, original_auth = gui.json.dumps, gui.Config.authorize

    def authorize(config):
        if revoked.is_set():
            raise CoreError("ACCESS_DENIED", "denied")
        return original_auth(config)

    def dumps(value, *args, **kwargs):
        result = original_dump(value, *args, **kwargs)
        if isinstance(value, dict) and ("result" in value if endpoint == "search" else "text" in value):
            revoked.set()
        return result

    monkeypatch.setattr(gui.Config, "authorize", authorize)
    monkeypatch.setattr(gui.json, "dumps", dumps)
    status, result = poll(server, selector) if endpoint == "search" else source(server, job)
    assert status == 403 and result == {"error": "FORBIDDEN"}


@pytest.mark.parametrize("endpoint", ["search", "source"])
def test_stale_search_or_source_is_checked_after_serialization(running, monkeypatch, endpoint):
    app, server, _ = running
    job, outcome = upload(server, archive_201()[0])
    selector = start(server, payload(job, outcome, "СверхЦель"))
    assert search_wait(server, selector)["status"] == "ready"
    original = gui.json.dumps

    def dumps(value, *args, **kwargs):
        result = original(value, *args, **kwargs)
        if isinstance(value, dict) and ("result" in value if endpoint == "search" else "text" in value):
            app._invalidate_search()
        return result

    monkeypatch.setattr(gui.json, "dumps", dumps)
    status, result = poll(server, selector) if endpoint == "search" else source(server, job)
    assert status == 400
    assert result == {"error": "SEARCH_NOT_AVAILABLE" if endpoint == "search" else "SOURCE_NOT_AVAILABLE"}


@pytest.mark.parametrize("unknown_id", [False, True])
@pytest.mark.parametrize("kind", ["metadata", "modules"])
def test_cancel_real_search_child_confirms_reap(running, monkeypatch, unknown_id, kind):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    entered, proceed, children = block_search(monkeypatch)
    selector = start(server, payload(job, outcome, "Products", kind=kind))
    assert entered.wait(5)
    try:
        assert poll(server, selector)[1]["status"] == "searching"
        status, result = post(server, "/api/search-cancel", {**selector, "search": None if unknown_id else selector["search"]})
        assert status == 200 and result == {"status": "searching", "cancel_requested": True}
        assert len(children) == 1 and children[0].poll() is None
    finally:
        proceed.set()
    found = search_wait(server, selector)
    assert found["status"] == "cancelled" and found["error"] == "CANCELLED"
    app.search_worker.join(timeout=5)
    assert not app.search_worker.is_alive() and children[0].poll() is not None
    assert app.current.id == job and app.current.path.exists()


@pytest.mark.parametrize("kind", ["metadata", "modules"])
def test_supersession_is_bounded_and_cancels_before_busy(running, monkeypatch, kind):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    entered, proceed, children = block_search(monkeypatch)
    selector = start(server, payload(job, outcome, "Products", kind=kind))
    assert entered.wait(5)
    old_search, old_worker = app.search, app.search_worker
    try:
        for _ in range(3):
            assert post(server, "/api/search-start", payload(job, outcome, "new")) == (409, {"error": "BUSY"})
            assert app.search is old_search and app.search_worker is old_worker
            assert old_search.cancel.is_set() and not old_search.valid
        assert len(children) == 1 and children[0].poll() is None
        assert poll(server, selector)[0] == 400
    finally:
        proceed.set()
    old_worker.join(timeout=5)
    assert not old_worker.is_alive() and children[0].poll() is not None
    assert search_wait(server, start(server, payload(job, outcome, "Products")))["status"] == "ready"
    assert len(children) == 2 and all(child.poll() is not None for child in children)


@pytest.mark.parametrize("kind", ["metadata", "modules"])
def test_new_import_cancels_search_and_keeps_archive_until_reaped(running, monkeypatch, kind):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    old_path = app.current.path
    entered, proceed, children = block_search(monkeypatch)
    selector = start(server, payload(job, outcome, "Products", kind=kind))
    assert entered.wait(5)
    old_search, old_worker = app.search, app.search_worker
    try:
        next_job = prepare(server)
        assert old_search.cancel.is_set() and not old_search.valid
        assert poll(server, selector)[0] == 400
        assert post(server, "/api/search-start", payload(job, outcome, ""))[0] == 409
        assert request(server, "/api/import?job=" + next_job, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
        assert old_path.exists() and app.current.id == job and children[0].poll() is None
    finally:
        proceed.set()
    assert wait(server, next_job)["status"] == "ready"
    old_worker.join(timeout=5)
    assert not old_worker.is_alive() and children[0].poll() is not None
    assert not old_path.exists() and app.current.id == next_job


@pytest.mark.parametrize("kind", ["metadata", "modules"])
def test_close_waits_for_search_reap_before_temp_cleanup(running, monkeypatch, kind):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    entered, proceed, children = block_search(monkeypatch)
    start(server, payload(job, outcome, "Products", kind=kind))
    assert entered.wait(5)
    closing = threading.Thread(target=app.close)
    closing.start()
    try:
        deadline = time.monotonic() + 5
        while not app.closed and time.monotonic() < deadline:
            time.sleep(.01)
        assert app.closed and app.search.cancel.is_set()
        assert closing.is_alive() and app.current.path.exists() and children[0].poll() is None
    finally:
        proceed.set()
        closing.join(timeout=5)
    assert not closing.is_alive() and not app.search_worker.is_alive()
    assert children[0].poll() is not None and not Path(app.temp.name).exists()


@pytest.mark.parametrize("headers,token", [({}, False), ({"Host": "evil.test"}, True), ({"Origin": "https://evil.test"}, True), ({"Sec-Fetch-Site": "cross-site"}, True)])
def test_search_transport_gates_match_existing_api(running, headers, token):
    _, server, _ = running
    job, outcome = upload(server, fixture_zip())
    status, raw, _ = request(server, "/api/search-start", "POST", json.dumps(payload(job, outcome)).encode(),
                             {"Content-Type": "application/json", **headers}, token=token)
    assert status == 401 and json.loads(raw) == {"error": "UNAUTHORIZED"}


@pytest.mark.parametrize("permission", ["project:read", "analysis:run"])
@pytest.mark.parametrize("kind", ["metadata", "modules"])
def test_actual_permission_revocation_cancels_disclosure_and_reaps_child(running, monkeypatch, permission, kind):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    context = app.config.context()
    entered, proceed, children = block_search(monkeypatch)
    selector = start(server, payload(job, outcome, "Products", kind=kind))
    assert entered.wait(5)
    try:
        with context.state.transaction(context.principal, write=True) as tx:
            tx._connection.execute("DELETE FROM membership_permissions WHERE permission=?", (permission,))
        assert poll(server, selector) == (403, {"error": "FORBIDDEN"})
    finally:
        proceed.set()
    app.search_worker.join(timeout=5)
    assert not app.search_worker.is_alive() and children[0].poll() is not None
    assert app.search.status == "error" and app.search.result is None
    assert app.current.id == job and app.current.path.exists()
    assert post(server, "/api/search-start", payload(job, outcome))[0] == 403
    assert source(server, job, MODULE) == (403, {"error": "FORBIDDEN"})


@pytest.mark.parametrize("permission", ["project:read", "analysis:run"])
def test_actual_permission_revocation_after_search_serialization(running, monkeypatch, permission):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    selector = start(server, payload(job, outcome, "Products"))
    assert search_wait(server, selector)["status"] == "ready"
    context = app.config.context()
    original = gui.json.dumps

    def dumps(value, *args, **kwargs):
        result = original(value, *args, **kwargs)
        if isinstance(value, dict) and "result" in value:
            with context.state.transaction(context.principal, write=True) as tx:
                tx._connection.execute("DELETE FROM membership_permissions WHERE permission=?", (permission,))
        return result

    monkeypatch.setattr(gui.json, "dumps", dumps)
    assert poll(server, selector) == (403, {"error": "FORBIDDEN"})


@pytest.mark.parametrize("mutation", ["job", "sha"])
def test_search_rechecks_current_job_and_sha_after_serialization(running, monkeypatch, mutation):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    selector = start(server, payload(job, outcome, "Products"))
    assert search_wait(server, selector)["status"] == "ready"
    original = gui.json.dumps

    def dumps(value, *args, **kwargs):
        result = original(value, *args, **kwargs)
        if isinstance(value, dict) and "result" in value:
            if mutation == "job":
                app.current = None
            else:
                app.current.sha256 = "0" * 64
        return result

    monkeypatch.setattr(gui.json, "dumps", dumps)
    assert poll(server, selector) == (400, {"error": "SEARCH_NOT_AVAILABLE"})


def test_late_search_cancel_keeps_completed_result_and_failed_import_can_search_again(running):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    selector = start(server, payload(job, outcome, "Products"))
    assert search_wait(server, selector)["status"] == "ready"
    assert post(server, "/api/search-cancel", selector) == (200, {"status": "ready", "cancel_requested": False})
    assert search_wait(server, selector)["status"] == "ready"
    _, failed = upload(server, b"not a zip")
    assert failed["status"] == "error" and app.current.id == job
    assert poll(server, selector)[0] == 400
    assert search_wait(server, start(server, payload(job, outcome, "Products")))["status"] == "ready"


def test_lost_import_reservation_expiry_does_not_block_search_forever(running):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    prepare(server)
    assert post(server, "/api/search-start", payload(job, outcome))[0] == 409
    app.pending.created_at -= 31
    assert search_wait(server, start(server, payload(job, outcome)))["status"] == "ready"
    assert app.pending.status == "error" and app.pending.error == "UPLOAD_TIMEOUT"
