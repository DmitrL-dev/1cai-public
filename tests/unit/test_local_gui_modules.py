"""Bounded archive-wide module discovery and exact related-path scope over Rust."""
import hashlib
import sys

import pytest

from rentgen_core import gui, submitted_export
from test_local_gui import fixture_zip, post, prepare, request, running, upload, wait
from test_local_gui_search import TARGET, block_search, payload, poll, search_wait, source, start
from test_metadata_three_way_materialize import xml
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Experimental GUI ZIP backend is Linux-only")


PREFIX = TARGET[:-4] + "/"
LATE_MODULES = [PREFIX + "Ext/Модуль.bsl", PREFIX + "Ext/Straße.OS", PREFIX + "Ext/Третий.bsp"]
COLLISION = TARGET[:-4] + "Collision/Ext/Module.bsl"


def module_archive():
    files = {f"Catalogs/A{index:03}.xml": xml(name=f"A{index:03}") for index in range(200)}
    files.update({f"CommonModules/A{index:03}/Ext/Module.bsl": b"// initial inventory\n" for index in range(200)})
    files[TARGET] = xml(name="СверхЦель").replace(b"<Catalog ", b"<Document ").replace(b"</Catalog>", b"</Document>")
    for index, path in enumerate(LATE_MODULES):
        files[path] = f"// late module {index}: Привет\n".encode()
    files[COLLISION] = b"// similar sibling, outside the exact directory\n"
    files[PREFIX + "Ext/not-a-module.txt"] = b"not in the module inventory\n"
    return zip_bytes(files), files


def module_payload(job, outcome, query="", object_path=None):
    return {**payload(job, outcome, query), "kind": "modules", "object_path": object_path}


def find_late_object(server, job, outcome):
    selector = start(server, payload(job, outcome, "СверхЦель"))
    found = search_wait(server, selector)
    assert found["result"]["objects"][0]["input_ref"]["relative_path"] == TARGET
    return selector


def test_module_query_scans_whole_manifest_before_cap_and_casefolds(running):
    app, server, root = running
    before = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    raw, files = module_archive()
    job, outcome = upload(server, raw)
    initial = outcome["result"]
    assert initial["counts"]["modules"] == 204 and len(initial["modules"]) == 200
    assert initial["modules_truncated"] and initial["objects_truncated"]
    assert source(server, job, LATE_MODULES[0]) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    for query, expected in [("", 204), ("пОСЛЕДНИЙпУТЬ/", 3), ("мОДУЛЬ.BSL", 1), ("STRASSE.os", 1), ("ТРЕТИЙ.BSP", 1), ("no-match", 0)]:
        found = search_wait(server, start(server, module_payload(job, outcome, query)))
        assert found["status"] == "ready", found
        assert found["kind"] == "modules" and found["object_path"] is None and found["prefix"] is None
        assert found["query"] == query and found["input_sha256"] == hashlib.sha256(raw).hexdigest()
        result = found["result"]
        assert result["matching_modules"] == expected
        assert len(result["modules"]) == min(expected, 200)
        assert result["modules_truncated"] is (expected > 200)
        assert result["counts"] == initial["counts"] and result["by_type"] == initial["by_type"]
        for row in result["modules"]:
            path = row["input_ref"]["relative_path"]
            assert row["analysis"] == "inventory_only"
            if expected < 200:
                status, preview = source(server, job, path)
                assert status == 200 and preview["text"].encode() == files[path]
                assert preview["input_ref"] == row["input_ref"]
                assert preview["input_ref"]["raw_sha256"] == hashlib.sha256(files[path]).hexdigest()
    assert app.current.result == initial
    assert before == {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_related_late_object_resolves_exact_prefix_and_retains_only_one_anchor(running):
    _, server, _ = running
    job, outcome = upload(server, module_archive()[0])
    args = module_payload(job, outcome, object_path=TARGET)
    # A real archive path is insufficient until it is an accepted metadata hit.
    assert post(server, "/api/search-start", args) == (400, {"error": "SEARCH_NOT_AVAILABLE"})
    metadata_selector = find_late_object(server, job, outcome)
    selector = start(server, args)
    found = search_wait(server, selector)
    assert found["object_path"] == TARGET and found["prefix"] == PREFIX and found["kind"] == "modules"
    assert found["result"]["matching_modules"] == 3 and not found["result"]["modules_truncated"]
    assert {row["input_ref"]["relative_path"] for row in found["result"]["modules"]} == set(LATE_MODULES)
    assert poll(server, metadata_selector)[0] == 400
    assert source(server, job, COLLISION) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    assert source(server, job, TARGET)[0] == 200  # The bounded server-owned anchor.
    refined = search_wait(server, start(server, {**args, "query": "STRASSE"}))
    assert refined["result"]["matching_modules"] == 1
    assert refined["result"]["modules"][0]["input_ref"]["relative_path"] == LATE_MODULES[1]
    assert source(server, job, LATE_MODULES[0])[0] == 400  # Old module hits are gone.
    search_wait(server, start(server, module_payload(job, outcome, "no-match")))
    assert source(server, job, TARGET)[0] == 400
    assert post(server, "/api/search-start", args)[0] == 400  # No stale anchor reuse.
    assert source(server, job, initial_module(outcome))[0] == 200


def initial_module(outcome):
    return outcome["result"]["modules"][0]["input_ref"]["relative_path"]


def test_related_module_count_is_filtered_before_truncation(running):
    _, server, _ = running
    files = {"Catalogs/Owner.xml": xml(name="Owner")}
    files.update({f"Catalogs/Owner/Ext/M{index:03}.bsl": b"// synthetic\n" for index in range(205)})
    files["Catalogs/OwnerOther/Ext/Module.bsl"] = b"// unrelated\n"
    job, outcome = upload(server, zip_bytes(files))
    args = module_payload(job, outcome, object_path="Catalogs/Owner.xml")
    found = search_wait(server, start(server, args))["result"]
    assert found["counts"]["modules"] == 206 and found["matching_modules"] == 205
    assert len(found["modules"]) == 200 and found["modules_truncated"]
    path = "Catalogs/Owner/Ext/M204.bsl"
    assert source(server, job, path)[0] == 400
    found = search_wait(server, start(server, {**args, "query": "M204"}))["result"]
    assert found["matching_modules"] == 1 and not found["modules_truncated"]
    assert source(server, job, path)[0] == 200


@pytest.mark.parametrize("options", [
    {"kind": None}, {"kind": []}, {"kind": {}}, {"kind": "module"}, {"kind": "MODULES"},
    {"kind": "metadata", "object_path": TARGET}, {"kind": "modules", "object_path": 1},
    {"kind": "modules", "object_path": []}, {"kind": "modules", "object_path": ""},
])
def test_invalid_kind_and_related_selector_do_not_start_or_replace_worker(running, options):
    app, server, _ = running
    job, outcome = upload(server, fixture_zip())
    assert post(server, "/api/search-start", {**payload(job, outcome), **options}) == (400, {"error": "INVALID_QUERY_OPTIONS"})
    assert app.search is None and app.search_worker is None


@pytest.mark.parametrize("path", ["Documents/Unknown.xml", "../../etc/passwd", PREFIX, LATE_MODULES[0], "documents/последнийпуть.xml", "\ud800"])
def test_unknown_forged_or_nonexact_related_path_is_not_a_capability(running, path):
    app, server, _ = running
    job, outcome = upload(server, module_archive()[0])
    selector = find_late_object(server, job, outcome)
    old_search = app.search
    assert post(server, "/api/search-start", module_payload(job, outcome, object_path=path)) == (400, {"error": "SEARCH_NOT_AVAILABLE"})
    assert app.search is old_search and old_search.valid
    assert poll(server, selector)[1]["status"] == "ready"


def test_client_prefix_hash_or_limit_cannot_override_resolved_related_scope(running):
    _, server, _ = running
    job, outcome = upload(server, fixture_zip())
    for key, value in [("prefix", ""), ("raw_sha256", "0" * 64), ("limit", 4096)]:
        assert post(server, "/api/search-start", {**module_payload(job, outcome), key: value}) == (400, {"error": "INVALID_REQUEST"})


def test_module_sources_are_current_bounded_hits_plus_initial_rows(running):
    app, server, _ = running
    job, outcome = upload(server, module_archive()[0])
    selector = start(server, module_payload(job, outcome, "STRASSE"))
    search_wait(server, selector)
    assert source(server, job, LATE_MODULES[1])[0] == 200
    assert source(server, job, LATE_MODULES[0])[0] == 400
    assert source(server, job, initial_module(outcome))[0] == 200
    assert poll(server, {**selector, "input_sha256": "0" * 64})[0] == 400
    assert poll(server, {**selector, "search": "0" * 32})[0] == 400
    search_wait(server, start(server, payload(job, outcome, "A001")))
    assert source(server, job, LATE_MODULES[1])[0] == 400 and poll(server, selector)[0] == 400
    search_wait(server, start(server, module_payload(job, outcome, "STRASSE")))
    prepare(server)  # Reservation alone invalidates late source capabilities.
    assert source(server, job, LATE_MODULES[1])[0] == 400
    assert source(server, job, initial_module(outcome))[0] == 200
    assert app.current.id == job


def test_module_source_rechecks_server_owned_raw_and_archive_hash(running):
    app, server, _ = running
    job, outcome = upload(server, module_archive()[0])
    search_wait(server, start(server, module_payload(job, outcome, "STRASSE")))
    ref = app.search.result["modules"][0]["input_ref"]
    digest = ref["raw_sha256"]
    ref["raw_sha256"] = "0" * 64
    assert source(server, job, LATE_MODULES[1]) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    ref["raw_sha256"] = digest
    app.current.path.write_bytes(fixture_zip())
    assert source(server, job, LATE_MODULES[1]) == (400, {"error": "IMPORT_HASH_MISMATCH"})


@pytest.mark.parametrize("raw,error", [(b"x" * (gui.MAX_SOURCE + 1), "SOURCE_TOO_LARGE"), (b"\xff", "SOURCE_ENCODING_UNSUPPORTED"), (b"hidden\x00", "SOURCE_ENCODING_UNSUPPORTED")])
def test_discovered_module_keeps_strict_preview_limits(running, raw, error):
    _, server, _ = running
    _, files = module_archive()
    files[LATE_MODULES[1]] = raw
    job, outcome = upload(server, zip_bytes(files))
    search_wait(server, start(server, module_payload(job, outcome, "STRASSE")))
    assert source(server, job, LATE_MODULES[1]) == (400, {"error": error})


@pytest.mark.parametrize("endpoint", ["search", "source"])
@pytest.mark.parametrize("mutation", ["invalidate", "project:read", "analysis:run"])
def test_module_result_and_source_revalidate_after_serialization(running, monkeypatch, endpoint, mutation):
    app, server, _ = running
    job, outcome = upload(server, module_archive()[0])
    selector = start(server, module_payload(job, outcome, "STRASSE"))
    search_wait(server, selector)
    context = app.config.context()
    original = gui.json.dumps

    def dumps(value, *args, **kwargs):
        raw = original(value, *args, **kwargs)
        if isinstance(value, dict) and ("result" in value if endpoint == "search" else "text" in value):
            if mutation == "invalidate":
                app._invalidate_search()
            else:
                with context.state.transaction(context.principal, write=True) as tx:
                    tx._connection.execute("DELETE FROM membership_permissions WHERE permission=?", (mutation,))
        return raw

    monkeypatch.setattr(gui.json, "dumps", dumps)
    status, result = poll(server, selector) if endpoint == "search" else source(server, job, LATE_MODULES[1])
    expected = "SEARCH_NOT_AVAILABLE" if endpoint == "search" else "SOURCE_NOT_AVAILABLE"
    assert (status, result) == ((400, {"error": expected}) if mutation == "invalidate" else (403, {"error": "FORBIDDEN"}))


def test_cancelled_scoped_refinement_retains_anchor_without_stale_source(running, monkeypatch):
    app, server, _ = running
    job, outcome = upload(server, module_archive()[0])
    find_late_object(server, job, outcome)
    app.search_worker.join(timeout=5)
    entered, proceed, children = block_search(monkeypatch)
    args = module_payload(job, outcome, object_path=TARGET)
    selector = start(server, args)
    assert entered.wait(5)
    old_worker = app.search_worker
    try:
        assert post(server, "/api/search-cancel", selector)[0] == 200
        for query in ("s", "st", "STRASSE"):
            assert post(server, "/api/search-start", {**args, "query": query}) == (409, {"error": "BUSY"})
            assert app.search_worker is old_worker and len(children) == 1
            assert app.search.cancel.is_set() and app.search.valid and app.search.result is None
        assert children[0].poll() is None
    finally:
        proceed.set()
    old_worker.join(timeout=5)
    assert not old_worker.is_alive() and children[0].poll() is not None
    assert search_wait(server, selector)["status"] == "cancelled"
    assert source(server, job, LATE_MODULES[0])[0] == 400
    found = search_wait(server, start(server, {**args, "query": "STRASSE"}))
    assert found["status"] == "ready" and found["prefix"] == PREFIX
    assert found["result"]["matching_modules"] == 1
    assert source(server, job, LATE_MODULES[1])[0] == 200
    assert all(child.poll() is not None for child in children)
    prepare(server)
    assert not app.search.valid and source(server, job, LATE_MODULES[1])[0] == 400


def test_related_start_busy_after_metadata_completion_preserves_resolved_anchor(running, monkeypatch):
    app, server, _ = running
    job, outcome = upload(server, module_archive()[0])
    selector = find_late_object(server, job, outcome)
    worker = app.search_worker
    worker.join(timeout=5)
    # Deterministically model the ready-before-thread-exit window. The real
    # Rust child is already reaped, but its Python worker still reports alive.
    monkeypatch.setattr(worker, "is_alive", lambda: True)
    args = module_payload(job, outcome, object_path=TARGET)
    assert post(server, "/api/search-start", args) == (409, {"error": "BUSY"})
    assert poll(server, selector)[1]["status"] == "cancelled"
    assert app.search.valid and app.search.object_row["input_ref"]["relative_path"] == TARGET
    assert app.search.result is None and source(server, job, TARGET)[0] == 400
    monkeypatch.setattr(worker, "is_alive", lambda: False)
    found = search_wait(server, start(server, args))
    assert found["status"] == "ready" and found["result"]["matching_modules"] == 3


def test_module_query_does_not_change_cli_mcp_analyze_export_contract(running):
    app, server, _ = running
    _, outcome = upload(server, module_archive()[0])
    options = {"archive": app.current.path, "archive_sha256": app.current.sha256,
               "input_core": app.config.input_core, "input_core_sha256": app.config.input_core_sha256,
               "query": "STRASSE", "limit": 1}
    result = submitted_export.analyze_export(app.config.context(), **options)
    assert result["objects"] == [] and result["matching_objects"] == 0
    assert result["modules"] == outcome["result"]["modules"][:1] and result["modules_truncated"]
    assert "matching_modules" not in result
    discovered = submitted_export.search_export_modules(app.config.context(), **options)
    assert discovered["matching_modules"] == 1 and not discovered["modules_truncated"]
    assert discovered["modules"][0]["input_ref"]["relative_path"] == LATE_MODULES[1]
