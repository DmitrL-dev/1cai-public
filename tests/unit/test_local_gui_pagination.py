"""Bounded GUI pages over owned archives, with no historical source authority."""
import hashlib
import sys

import pytest

from rentgen_core import gui, submitted_export
from rentgen_core.errors import CoreError
from test_local_gui import fixture_zip, post, prepare, request, running, upload, wait
from test_local_gui_search import block_search, payload, poll, search_wait, source, start
from test_metadata_three_way_materialize import xml
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Experimental GUI ZIP backend is Linux-only")

OWNER = "Catalogs/P400.xml"
PREFIX = OWNER[:-4] + "/"


def inventory(count=401):
    files = {f"Catalogs/P{index:03}.xml": xml(name=f"Straße{index:03}") for index in range(count)}
    files.update({PREFIX + f"Ext/Straße{index:03}.bsl": f"// own module {index}\n".encode() for index in range(count)})
    return files


def page(app, server, args, offset):
    selector = start(server, {**args, "offset": offset})
    result = search_wait(server, selector)
    app.search_worker.join(timeout=5)
    assert not app.search_worker.is_alive()
    assert result["offset"] == offset
    assert result["query"] == args["query"] and result["kind"] == args.get("kind", "metadata")
    assert result["object_path"] == args.get("object_path")
    assert result["prefix"] == (args["object_path"][:-4] + "/" if args.get("object_path") else None)
    return selector, result


def paths(result, kind):
    return [row["input_ref"]["relative_path"] for row in result["modules" if kind == "modules" else "objects"]]


@pytest.mark.parametrize("kind", ["metadata", "modules"])
@pytest.mark.parametrize("query", ["", "sTRASSE"], ids=["inventory", "casefold"])
def test_three_pages_reach_every_hit_and_expire_previous_source(running, kind, query):
    app, server, root = running
    before = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    files = inventory()
    raw = zip_bytes(files)
    job, outcome = upload(server, raw)
    initial = outcome["result"]
    assert "page" not in initial  # Import and CLI/MCP keep their existing schema.
    assert len(initial["objects"]) == len(initial["modules"]) == 200
    args = payload(job, outcome, query, kind=kind)
    expected = sorted((path for path in files if path.endswith(".bsl" if kind == "modules" else ".xml")), key=lambda value: value.encode())
    seen = []
    previous_selector = None
    for offset, count in [(0, 200), (200, 200), (400, 1)]:
        selector, found = page(app, server, args, offset)
        assert found["status"] == "ready", found
        result = found["result"]
        assert result["page"] == {"offset": offset, "limit": 200, "total": 401, "returned": count,
                                  "has_previous": offset > 0, "has_next": offset < 400}
        assert result["counts"] == initial["counts"] and result["by_type"] == initial["by_type"]
        current_paths = paths(result, kind)
        assert current_paths == expected[offset:offset + 200]
        seen.extend(current_paths)
        if previous_selector:
            assert poll(server, previous_selector) == (400, {"error": "SEARCH_NOT_AVAILABLE"})
        if offset == 400:
            assert source(server, job, expected[200]) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
        status, preview = source(server, job, current_paths[-1])
        assert status == 200 and preview["text"].encode() == files[current_paths[-1]]
        assert preview["input_ref"]["raw_sha256"] == hashlib.sha256(files[current_paths[-1]]).hexdigest()
        previous_selector = selector
    assert seen == expected and len(set(seen)) == 401
    _, found = page(app, server, args, 200)
    assert paths(found["result"], kind) == expected[200:400]
    assert source(server, job, expected[400])[0] == 400
    assert source(server, job, expected[0])[0] == 200  # Initial-owned inventory remains valid.
    _, found = page(app, server, args, 0)
    assert paths(found["result"], kind) == expected[:200]
    assert source(server, job, expected[200])[0] == 400
    assert app.current.result == initial
    assert before == {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("kind", ["metadata", "modules"])
def test_filter_precedes_offset_and_page_totals(running, kind):
    app, server, _ = running
    files = inventory()
    files.update({f"Catalogs/A{index:03}.xml": xml(name="unmatched") for index in range(201)})
    files.update({f"CommonModules/A{index:03}/Ext/Module.bsl": b"// unmatched\n" for index in range(201)})
    job, outcome = upload(server, zip_bytes(files))
    args = payload(job, outcome, "sTRASSE", kind=kind)
    _, found = page(app, server, args, 400)
    assert found["status"] == "ready", found
    result = found["result"]
    assert result["counts"]["metadata_objects"] == result["counts"]["modules"] == 602
    assert result["page"] == {"offset": 400, "limit": 200, "total": 401, "returned": 1,
                              "has_previous": True, "has_next": False}
    assert paths(result, kind) == ([OWNER] if kind == "metadata" else [PREFIX + "Ext/Straße400.bsl"])
    _, missing = page(app, server, {**args, "query": "no match"}, 0)
    assert missing["status"] == "ready" and paths(missing["result"], kind) == []
    assert missing["result"]["page"] == {"offset": 0, "limit": 200, "total": 0, "returned": 0,
                                        "has_previous": False, "has_next": False}


def test_related_pages_retain_one_late_anchor_and_exact_folder_scope(running):
    app, server, _ = running
    files = inventory()
    files[OWNER[:-4] + "Other/Ext/Module.bsl"] = b"// outside\n"
    job, outcome = upload(server, zip_bytes(files))
    args = {**payload(job, outcome, kind="modules"), "object_path": OWNER}
    # An offset and an existing archive path cannot manufacture anchor authority.
    assert post(server, "/api/search-start", {**args, "offset": 400}) == (400, {"error": "SEARCH_NOT_AVAILABLE"})
    _, metadata = page(app, server, payload(job, outcome), 400)
    assert paths(metadata["result"], "metadata") == [OWNER]
    selectors = []
    for offset in (0, 200, 400, 200, 0):
        selector, found = page(app, server, args, offset)
        selectors.append(selector)
        assert found["status"] == "ready", found
        assert found["result"]["page"]["total"] == 401
        assert len(found["result"]["modules"]) == (1 if offset == 400 else 200)
        assert app.search.object_row["input_ref"]["relative_path"] == OWNER
        assert source(server, job, OWNER)[0] == 200
        assert source(server, job, OWNER[:-4] + "Other/Ext/Module.bsl")[0] == 400
    assert all(poll(server, selector)[0] == 400 for selector in selectors[:-1])
    assert source(server, job, PREFIX + "Ext/Straße200.bsl")[0] == 400
    # Leaving the scope drops the one retained anchor; historical pages do not restore it.
    page(app, server, payload(job, outcome, "missing", kind="modules"), 0)
    assert source(server, job, OWNER)[0] == 400
    assert post(server, "/api/search-start", args)[0] == 400


BAD_OFFSETS = [None, True, False, "200", [], {}, 200.0, -200, 1, 199, 201, 4001, 4200, 10**200]
BAD_IDS = ["null", "true", "false", "string", "list", "object", "float", "negative", "one", "below-page", "above-page", "above-max", "next-page", "huge"]


@pytest.mark.parametrize("offset", BAD_OFFSETS, ids=BAD_IDS)
def test_malformed_offsets_do_not_replace_current_page_or_start_child(running, offset):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    selector, found = page(app, server, payload(job, outcome), 0)
    old_search, old_worker = app.search, app.search_worker
    assert found["status"] == "ready"
    assert post(server, "/api/search-start", {**payload(job, outcome), "offset": offset}) == (400, {"error": "INVALID_QUERY_OPTIONS"})
    assert app.search is old_search and app.search_worker is old_worker and old_search.valid
    assert poll(server, selector)[1]["status"] == "ready"


@pytest.mark.parametrize("kind", ["metadata", "modules"])
@pytest.mark.parametrize("offset", [200, 4000], ids=["after-end", "max-offset"])
def test_aligned_offsets_beyond_filtered_end_fail_after_reap(running, monkeypatch, kind, offset):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    entered, proceed, children = block_search(monkeypatch)
    proceed.set()
    _, found = page(app, server, payload(job, outcome, kind=kind), offset)
    assert entered.is_set() and len(children) == 1 and children[0].poll() is not None
    assert found["status"] == "error" and found["error"] == "INVALID_QUERY_OPTIONS" and "result" not in found
    assert app.search.result is None


@pytest.mark.parametrize("kind", ["metadata", "modules"])
def test_highest_valid_page_reaches_manifest_bound(running, kind):
    app, server, _ = running
    if kind == "metadata":
        files = {f"Catalogs/A{index:04}.xml": xml(name=f"A{index:04}") for index in range(4096)}
        total = 4096
    else:
        files = {"Catalogs/Owner.xml": xml(name="Owner")}
        files.update({f"CommonModules/A{index:04}/Ext/Module.bsl": b"// own\n" for index in range(4095)})
        total = 4095
    job, outcome = upload(server, zip_bytes(files))
    assert outcome["status"] == "ready", outcome
    _, found = page(app, server, payload(job, outcome, kind=kind), 4000)
    assert found["status"] == "ready", found
    assert found["result"]["page"] == {"offset": 4000, "limit": 200, "total": total,
                                       "returned": total - 4000, "has_previous": True, "has_next": False}
    assert source(server, job, paths(found["result"], kind)[-1])[0] == 200


@pytest.mark.parametrize("kind", ["metadata", "modules"])
@pytest.mark.parametrize("ending", ["supersede", "cancel", "import", "revoke"])
def test_noninitial_page_lifecycle_reaps_one_owned_child(running, monkeypatch, kind, ending):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(inventory()))
    args = payload(job, outcome, kind=kind)
    _, prior = page(app, server, args, 200)
    old_path = paths(prior["result"], kind)[0]
    assert source(server, job, old_path)[0] == 200
    entered, proceed, children = block_search(monkeypatch)
    selector = start(server, {**args, "offset": 400})
    assert entered.wait(5)
    search, worker, archive = app.search, app.search_worker, app.current.path
    try:
        assert search.offset == 400 and len(children) == 1 and children[0].poll() is None
        with app.lock:
            with pytest.raises(CoreError) as error:
                app._source_reference(job, old_path)
            assert error.value.code == "SOURCE_NOT_AVAILABLE"
        if ending == "supersede":
            assert post(server, "/api/search-start", {**args, "offset": 200}) == (409, {"error": "BUSY"})
            assert app.search is search and app.search_worker is worker and not search.valid
        elif ending == "cancel":
            assert post(server, "/api/search-cancel", selector) == (200, {"status": "searching", "cancel_requested": True})
        elif ending == "import":
            new_job = prepare(server)
            assert request(server, "/api/import?job=" + new_job, "PUT", fixture_zip(), {"Content-Type": "application/zip"})[0] == 202
            assert archive.exists() and app.current.id == job
        else:
            context = app.config.context()
            with context.state.transaction(context.principal, write=True) as tx:
                tx._connection.execute("DELETE FROM membership_permissions WHERE permission='project:read'")
            assert poll(server, selector) == (403, {"error": "FORBIDDEN"})
    finally:
        proceed.set()
    worker.join(timeout=5)
    assert not worker.is_alive() and children[0].poll() is not None and search.result is None
    if ending == "import":
        assert wait(server, new_job)["status"] == "ready" and not archive.exists()
    elif ending == "supersede":
        assert poll(server, selector)[0] == 400
        assert page(app, server, args, 200)[1]["status"] == "ready"
    elif ending == "cancel":
        assert poll(server, selector)[1]["status"] == "cancelled"
    else:
        assert source(server, job, old_path) == (403, {"error": "FORBIDDEN"})


@pytest.mark.parametrize("kind", ["metadata", "modules"])
@pytest.mark.parametrize("endpoint", ["search", "source"])
@pytest.mark.parametrize("mutation", ["invalidate", "revoke"])
def test_noninitial_page_and_read_revalidate_before_disclosure(running, monkeypatch, kind, endpoint, mutation):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(inventory()))
    selector, found = page(app, server, payload(job, outcome, kind=kind), 400)
    path = paths(found["result"], kind)[0]
    context = app.config.context()
    original = gui.json.dumps

    def dumps(value, *args, **kwargs):
        raw = original(value, *args, **kwargs)
        if isinstance(value, dict) and ("result" in value if endpoint == "search" else "text" in value):
            if mutation == "invalidate":
                app._invalidate_search()
            else:
                with context.state.transaction(context.principal, write=True) as tx:
                    tx._connection.execute("DELETE FROM membership_permissions WHERE permission='analysis:run'")
        return raw

    monkeypatch.setattr(gui.json, "dumps", dumps)
    result = poll(server, selector) if endpoint == "search" else source(server, job, path)
    expected = "SEARCH_NOT_AVAILABLE" if endpoint == "search" else "SOURCE_NOT_AVAILABLE"
    assert result == ((400, {"error": expected}) if mutation == "invalidate" else (403, {"error": "FORBIDDEN"}))


@pytest.mark.parametrize("function", [submitted_export.search_export_metadata, submitted_export.search_export_modules], ids=["metadata", "modules"])
def test_gui_only_page_wrappers_reject_null_without_opening_rust(running, monkeypatch, function):
    app, _, _ = running
    monkeypatch.setattr(submitted_export.RustInputSession, "__init__", lambda *args, **kwargs: pytest.fail("Invalid offset opened a Rust child"))
    with pytest.raises(CoreError) as error:
        function(app.config.context(), archive="missing", archive_sha256="0" * 64,
                 input_core="missing", input_core_sha256="0" * 64, offset=None)
    assert error.value.code == "INVALID_QUERY_OPTIONS"


@pytest.mark.parametrize("kind", ["metadata", "modules"])
@pytest.mark.parametrize("count", [0, 200, 400], ids=["zero-matches", "exact-first-end", "exact-second-end"])
def test_offset_equal_to_filtered_end_never_creates_empty_later_page(running, kind, count):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(inventory(count)) if count else fixture_zip())
    args = payload(job, outcome, "" if count else "absent", kind=kind)
    _, found = page(app, server, args, count or 200)
    assert found["status"] == "error" and found["error"] == "INVALID_QUERY_OPTIONS"
    assert "result" not in found and app.search.result is None


def test_scoped_page_cancel_and_busy_retry_retain_only_anchor(running, monkeypatch):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(inventory()))
    page(app, server, payload(job, outcome), 400)
    args = {**payload(job, outcome, kind="modules"), "object_path": OWNER}
    page(app, server, args, 200)
    entered, proceed, children = block_search(monkeypatch)
    selector = start(server, {**args, "offset": 400})
    assert entered.wait(5)
    worker = app.search_worker
    try:
        assert post(server, "/api/search-cancel", selector)[0] == 200
        assert post(server, "/api/search-start", {**args, "offset": 200}) == (409, {"error": "BUSY"})
        assert app.search_worker is worker and app.search.valid and app.search.result is None
        assert app.search.object_row["input_ref"]["relative_path"] == OWNER
        assert len(children) == 1 and children[0].poll() is None
    finally:
        proceed.set()
    worker.join(timeout=5)
    assert not worker.is_alive() and children[0].poll() is not None
    assert poll(server, selector)[1]["status"] == "cancelled"
    assert source(server, job, OWNER)[0] == 400
    assert source(server, job, PREFIX + "Ext/Straße200.bsl")[0] == 400
    _, found = page(app, server, args, 200)
    assert found["status"] == "ready" and found["result"]["page"]["offset"] == 200
    assert source(server, job, OWNER)[0] == 200
    assert source(server, job, PREFIX + "Ext/Straße200.bsl")[0] == 200
    assert all(child.poll() is not None for child in children)
