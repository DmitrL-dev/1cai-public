"""Owned Rust source-search inputs; no customer code or backend success mocks."""
import hashlib
import json
import sys
import threading

import pytest

from rentgen_core import gui, source_search
from rentgen_core.errors import CoreError
from test_local_gui import post, prepare, request, running, upload
from test_local_gui_search import block_search, payload, poll, search_wait, source, start
from test_local_gui_modules import TARGET, PREFIX, COLLISION, module_archive, find_late_object
from test_metadata_three_way_materialize import xml
from test_rust_input_workflow import binary, zip_bytes

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Experimental GUI ZIP backend is Linux-only")


def files(count=201):
    result = {"Catalogs/Owner.xml": xml(name="Owner")}
    for index in range(count):
        result[f"Catalogs/Owner/Ext/M{index:03}.bsl"] = f"// first\r\nПривет😀 needle {index}\rneedle again\n".encode()
    return result


def args(job, outcome, query="needle", **options):
    return {**payload(job, outcome, query), "kind": "source", **options}


def finish(app, server, options):
    result = search_wait(server, start(server, options))
    app.search_worker.join(timeout=5)
    assert not app.search_worker.is_alive()
    return result


def test_first_match_per_file_paging_raw_source_and_original_bytes(running):
    app, server, root = running
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    entries = files()
    job, outcome = upload(server, zip_bytes(entries))
    first = finish(app, server, args(job, outcome))["result"]
    assert first["matching_modules"] == 201 and len(first["modules"]) == 200
    assert first["source_coverage"] == {"in_scope": 201, "searched": 201, "skipped_oversized": 0,
                                       "skipped_invalid_utf8": 0, "skipped_controls": 0, "complete": True}
    last = finish(app, server, args(job, outcome, offset=200))["result"]
    assert last["page"] == {"offset": 200, "limit": 200, "total": 201, "returned": 1, "has_previous": True, "has_next": False}
    hit = last["modules"][0]
    path = hit["input_ref"]["relative_path"]
    assert path == "Catalogs/Owner/Ext/M200.bsl"
    assert hit["first_match"] == {"line": 2, "excerpt": "Привет😀 needle 200", "truncated_before": False, "truncated_after": False}
    status, found = source(server, job, path)
    assert status == 200 and found["text"].encode() == entries[path]
    assert found["input_ref"]["raw_sha256"] == hashlib.sha256(entries[path]).hexdigest()
    assert found["input_ref"]["input_sha256"] == outcome["result"]["input"]["input_sha256"]
    finish(app, server, args(job, outcome, offset=0))
    assert source(server, job, path) == (400, {"error": "SOURCE_NOT_AVAILABLE"})
    assert {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("query", ["needle", "absent"], ids=["some-hits", "zero-hits"])
def test_skipped_files_make_partial_coverage_explicit(running, query):
    app, server, _ = running
    entries = files(1)
    entries.update({"Modules/large.bsl": b"x" * (source_search.SOURCE_FILE_LIMIT + 1),
                    "Modules/invalid.OS": b"\xffneedle", "Modules/control.bsp": b"needle\x00",
                    "Modules/not-source.txt": b"needle"})
    job, outcome = upload(server, zip_bytes(entries))
    result = finish(app, server, args(job, outcome, query))["result"]
    assert result["matching_modules"] == (query == "needle")
    assert result["source_coverage"] == {"in_scope": 4, "searched": 1, "skipped_oversized": 1,
                                       "skipped_invalid_utf8": 1, "skipped_controls": 1, "complete": False}
    assert result["scan"]["bytes_read"] == sum(len(v) for k, v in entries.items() if k.endswith((".OS", ".bsp"))) + len(entries["Catalogs/Owner/Ext/M000.bsl"])


@pytest.mark.parametrize("query", ["Needle", ".*", "absent"], ids=["case-sensitive", "literal-not-regex", "no-hit"])
def test_complete_zero_hits_are_distinct_from_partial(running, query):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(files(1)))
    result = finish(app, server, args(job, outcome, query))["result"]
    assert result["matching_modules"] == 0 and result["source_coverage"]["complete"] is True


@pytest.mark.parametrize("prefix,line", [("\ufeff", 1), ("first\r\nsecond\rthird\n", 4), ("😀" * 32767, 1)], ids=["bom", "mixed-newlines", "chunk-boundary"])
def test_unicode_bom_newlines_and_bounded_first_line(running, prefix, line):
    app, server, _ = running
    entries = {"Catalogs/Owner.xml": xml(name="Owner"), "Modules/code.os": (prefix + "Привет😀needle" + "x" * 1000 + "needle").encode()}
    job, outcome = upload(server, zip_bytes(entries))
    result = finish(app, server, args(job, outcome, "Привет😀needle"))["result"]
    hit = result["modules"][0]["first_match"]
    assert hit["line"] == line and len(hit["excerpt"]) <= 512
    assert "Привет😀needle" in hit["excerpt"] and hit["truncated_after"] is True
    assert len(hit["excerpt"].encode()) <= 2048


@pytest.mark.parametrize("query", ["", "x\ny", "x\ry", "x\x00y", "я" * 129, "\ud800", None, []], ids=["empty", "lf", "cr", "nul", "utf8-overflow", "surrogate", "null", "array"])
def test_invalid_literals_fail_before_worker_launch(running, query):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(files(1)))
    assert post(server, "/api/search-start", args(job, outcome, query)) == (400, {"error": "INVALID_QUERY_OPTIONS"})
    assert app.search_worker is None


def test_literal_spaces_tabs_and_max_byte_query_are_preserved(running):
    app, server, _ = running
    query = "я" * 128
    entries = {"Catalogs/Owner.xml": xml(name="Owner"), "Modules/code.bsp": ("\t needle \n" + query).encode()}
    job, outcome = upload(server, zip_bytes(entries))
    for literal in ("\t needle ", query):
        result = finish(app, server, args(job, outcome, literal))["result"]
        assert result["matching_modules"] == 1 and literal in result["modules"][0]["first_match"]["excerpt"]


def test_exact_late_object_scope_preserves_anchor_and_rejects_neighbor(running):
    app, server, _ = running
    raw, entries = module_archive()
    entries[PREFIX + "Ext/Модуль.bsl"] = b"needle"
    entries[COLLISION] = b"needle"
    job, outcome = upload(server, zip_bytes(entries))
    find_late_object(server, job, outcome); app.search_worker.join(timeout=5)
    result = finish(app, server, args(job, outcome, object_path=TARGET))["result"]
    assert result["matching_modules"] == 1 and result["source_coverage"]["in_scope"] == 3
    assert source(server, job, COLLISION)[0] == 400
    assert source(server, job, TARGET)[0] == 200
    assert post(server, "/api/search-start", args(job, outcome, object_path=COLLISION))[0] == 400


@pytest.mark.parametrize("ending", ["cancel", "supersede", "import", "revoke"], ids=["cancel", "supersede", "import", "revoke"])
def test_scan_cancellation_revocation_and_replacement_reap_child(running, monkeypatch, ending):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(files(1)))
    entered, proceed, children = block_search(monkeypatch)
    selector = start(server, args(job, outcome))
    assert entered.wait(5)
    try:
        if ending == "cancel":
            assert post(server, "/api/search-cancel", selector)[0] == 200
        elif ending == "supersede":
            assert post(server, "/api/search-start", args(job, outcome, "other")) == (409, {"error": "BUSY"})
        elif ending == "import":
            prepare(server)
        else:
            ctx = app.config.context()
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                tx._connection.execute("DELETE FROM membership_permissions WHERE permission='analysis:run'")
    finally:
        proceed.set()
    app.search_worker.join(timeout=5)
    assert not app.search_worker.is_alive() and all(child.poll() is not None for child in children)
    assert app.search.result is None


@pytest.mark.parametrize("endpoint", ["search", "source"])
@pytest.mark.parametrize("mutation", ["invalidate", "project:read", "analysis:run"])
def test_disclosure_rechecks_current_hits_and_permissions(running, monkeypatch, endpoint, mutation):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(files()))
    selector = start(server, args(job, outcome, offset=200))
    search_wait(server, selector); app.search_worker.join(timeout=5)
    original = gui.json.dumps
    def dumps(value, *a, **k):
        raw = original(value, *a, **k)
        if isinstance(value, dict) and ("result" in value if endpoint == "search" else "text" in value):
            if mutation == "invalidate":app._invalidate_search()
            else:
                ctx=app.config.context()
                with ctx.state.transaction(ctx.principal, write=True) as tx:
                    tx._connection.execute("DELETE FROM membership_permissions WHERE permission=?", (mutation,))
        return raw
    monkeypatch.setattr(gui.json, "dumps", dumps)
    status, result = poll(server, selector) if endpoint == "search" else source(server, job, "Catalogs/Owner/Ext/M200.bsl")
    assert status == (400 if mutation == "invalidate" else 403)
    assert "modules" not in result and "text" not in result


@pytest.mark.parametrize("budget", ["CPU_SECONDS", "WALL_SECONDS", "SCAN_BYTE_LIMIT"])
def test_budget_exhaustion_reaps_without_partial_success(running, monkeypatch, budget):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(files(1)))
    original = source_search.RustInputSession.open_import
    children = []
    def opened(session, *a):
        result = original(session, *a)
        if threading.current_thread().name == "rentgen-gui-search":
            children.append(session.process); monkeypatch.setattr(source_search, budget, 0)
        return result
    monkeypatch.setattr(source_search.RustInputSession, "open_import", opened)
    result = finish(app, server, args(job, outcome))
    assert result["status"] == "error" and result["error"] == "SOURCE_SEARCH_BUDGET_EXCEEDED"
    assert "result" not in result and children and all(child.poll() is not None for child in children)


def test_direct_helper_rejects_invalid_offset_and_scope(running):
    app, server, _ = running
    job, outcome = upload(server, zip_bytes(files(1)))
    options=dict(archive=app.current.path,archive_sha256=app.current.sha256,input_core=app.config.input_core,input_core_sha256=app.config.input_core_sha256,query="needle")
    for update in ({"offset":True},{"offset":4001},{"prefix":"../"},{"limit":201}):
        with pytest.raises(CoreError) as error:source_search.search_source_files(app.config.context(),**{**options,**update})
        assert error.value.code=="INVALID_QUERY_OPTIONS"
    result=finish(app,server,args(job,outcome,offset=200))
    assert result["status"]=="error" and result["error"]=="INVALID_QUERY_OPTIONS"

@pytest.mark.parametrize("ending", ["cancel", "revoke"])
def test_interrupted_real_source_read_reaps_before_any_result(running, monkeypatch, ending):
    app, server, _ = running
    entries=files(1);entries['Catalogs/Owner/Ext/M000.bsl']=b'a'*65536+b'needle'
    job,outcome=upload(server,zip_bytes(entries))
    entered,proceed=threading.Event(),threading.Event();children=[]
    original=source_search.RustInputSession.request
    def request_chunk(session,operation,**fields):
        result=original(session,operation,**fields)
        if operation=='read_entry' and threading.current_thread().name=='rentgen-gui-search' and not children:
            children.append(session.process);entered.set();assert proceed.wait(5)
        return result
    monkeypatch.setattr(source_search.RustInputSession,'request',request_chunk)
    selector=start(server,args(job,outcome));assert entered.wait(5)
    try:
        if ending=='cancel':assert post(server,'/api/search-cancel',selector)[0]==200
        else:
            ctx=app.config.context()
            with ctx.state.transaction(ctx.principal,write=True) as tx:
                tx._connection.execute("DELETE FROM membership_permissions WHERE permission='project:read'")
    finally:proceed.set()
    app.search_worker.join(timeout=5)
    assert not app.search_worker.is_alive() and all(child.poll() is not None for child in children)
    assert app.search.result is None


def test_no_source_files_is_complete_empty_scope(running):
    app,server,_=running
    job,outcome=upload(server,zip_bytes({'Catalogs/Owner.xml':xml(name='Owner')}))
    result=finish(app,server,args(job,outcome))['result']
    assert result['matching_modules']==0 and result['source_coverage']['in_scope']==0
    assert result['source_coverage']['complete'] is True and result['scan']['bytes_read']==0
