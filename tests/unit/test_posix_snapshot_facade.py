"""Real retained trees/SQLite with constructed scanner records, not Linux capture."""

import base64
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from threading import Thread

import pytest

from project_access_test_support import revoke_membership
from test_posix_snapshot_session import make_generation, generation, MODULE
from rentgen_core import _posix_snapshot_facade as facade
from rentgen_core import _posix_snapshot_session as backend
from rentgen_core import _posix_source_tree as retained
from rentgen_core import _sqlite
from rentgen_core.context import Explicit, ProjectContext, SnapshotRef
from rentgen_core.errors import CoreError
from rentgen_core.manifests import canonical_bytes, parse_manifest, sha256
from rentgen_core.registry import ProjectRegistry
from rentgen_core.resolver import ContextResolver
from rentgen_core.sources import SourceRef
from rentgen_core.state import ProjectState
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

pytestmark = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Actual POSIX retained read facade")
linux = pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux resolver dispatch")


def sources_for(generation, **changes):
    values = dict(snapshot=generation.snapshot, _state=generation.state,
        _principal=generation.principal, _factory=generation.options["graph_reader_factory"],
        _limits=generation.options["limits"], _graph_limits=generation.options["graph_limits"],
        _authorize_read=lambda: None)
    return facade.PosixSnapshotSources(**(values | changes))


def operation(sources, graph, ref, name):
    return {"resolve": lambda: sources.resolve("base", MODULE),
        "list": sources.list_entries, "read": lambda: sources.read_source(ref),
        "graph": lambda: graph.resolve_module(ref), "impact": lambda: graph.impact(ref),
        "verify": sources._verify}[name]()


def test_all_operations_use_distinct_real_sessions_and_close_before_return(generation, monkeypatch):
    original_open = facade.open_posix_snapshot_session
    sessions, databases = [], []
    def opened(**options):
        session = original_open(**options)
        sessions.append(session)
        return session
    original_enter = backend._PosixSnapshotSession.__enter__
    def entered(session):
        result = original_enter(session)
        databases.append(session._reader._owner._db)
        return result
    monkeypatch.setattr(facade, "open_posix_snapshot_session", opened)
    monkeypatch.setattr(backend._PosixSnapshotSession, "__enter__", entered)
    sources = sources_for(generation)
    graph = facade.PosixSnapshotGraph(generation.snapshot, sources)
    ref = sources.resolve("base", MODULE)
    assert sources.read_source(ref) == generation.contents[MODULE]
    assert len(sources.list_entries().entries) == 3
    resolved = graph.resolve_module(ref)
    impacted = graph.impact(ref, depth=5)
    assert resolved["project_id"] == generation.snapshot.project_id
    assert resolved["snapshot_id"] == resolved["manifest_hash"] == generation.snapshot.snapshot_id
    assert resolved["capabilities"] == asdict(graph.capabilities)
    assert resolved["capabilities"]["quality"] == "unavailable"
    assert resolved["capabilities"]["temporal_atomicity"] == "not_proven"
    assert resolved["result"]["graph_modules"] and impacted["result"]
    sources._verify()
    assert len(sessions) == 6 and len({id(x) for x in sessions}) == 6
    for session, database in zip(sessions, databases):
        assert session._phase == "closed" and not session._buffers and not session._directories
        with pytest.raises(CoreError):
            session.entries()
        with pytest.raises(CoreError):
            session.read_source(ref)
        import sqlite3
        with pytest.raises(sqlite3.ProgrammingError):
            database.execute("SELECT 1")
    assert not hasattr(sources, "_path")


@pytest.mark.parametrize("consumer", ["direct", "other-purpose", "diff", "platform", "metadata-plan"])
def test_legacy_session_consumers_get_controlled_denial_without_retained_io(generation, monkeypatch, consumer):
    from rentgen_core.snapshot_diff import compare_snapshots
    from rentgen_core.platform_check import _materialize
    from rentgen_core.metadata_plans import _scan
    from rentgen_core.sources import SnapshotReadLimits

    sources = sources_for(generation, _principal=generation.owner)
    ref = sources.resolve("base", MODULE)
    graph = facade.PosixSnapshotGraph(generation.snapshot, sources)
    ctx = ProjectContext(generation.snapshot.project_id, generation.owner, "fixture-request",
                         generation.state, generation.root / "live", generation.snapshot, sources, graph)
    monkeypatch.setattr(facade, "open_posix_snapshot_session", lambda **k: pytest.fail("Unsupported consumer opened a POSIX session"))
    monkeypatch.setattr(retained.Directory, "file", lambda *a, **k: pytest.fail("Unsupported consumer read retained content"))
    calls = {
        "direct": lambda: sources.read_session(limits=SnapshotReadLimits()),
        "other-purpose": lambda: sources.read_session(limits=SnapshotReadLimits(), purpose="platform-materialization"),
        "diff": lambda: compare_snapshots(ctx, ctx),
        "platform": lambda: _materialize(ctx, None, generation.root / "before", generation.root / "after"),
        "metadata-plan": lambda: _scan(ctx, {"catalog": {"name": "Fixture"}}, lambda: None),
    }
    with pytest.raises(CoreError) as caught:
        calls[consumer]()
    assert caught.value.code == "CAPABILITY_UNAVAILABLE"
    assert "Windows retained session" in caught.value.message


@pytest.mark.parametrize("filters,version", [({}, 1), ({"kind": "module", "query": "COMMON"}, 2)])
def test_cursor_wire_version_exact_binding_and_source_page_roundtrip(generation, filters, version):
    sources = sources_for(generation)
    page = sources.list_entries(limit=1, **filters)
    ref = page.entries[0].ref
    expected = dict(version=version, project_id=ref.snapshot.project_id,
                    snapshot_id=ref.snapshot.snapshot_id, limit=1,
                    last=[0, ref.relative_path])
    if version == 2:
        expected.update(filters=dict(query="COMMON", kind="module", layer=None),
                        manifest_hash=ref.snapshot.manifest_hash)
    assert page.next_cursor == base64.urlsafe_b64encode(canonical_bytes(expected)).decode("ascii")
    found = list(page.entries)
    while page.next_cursor:
        page = sources.list_entries(limit=1, cursor=page.next_cursor, **filters)
        found.extend(page.entries)
    expected_paths = sorted(name for name in generation.contents
                            if version == 1 or name.endswith(".bsl"))
    assert [entry.ref.relative_path for entry in found] == expected_paths
    assert all(sources.read_source(entry.ref) == generation.contents[entry.ref.relative_path] for entry in found)


@pytest.mark.parametrize("changes", [{"limit": 2}, {"query": "common"}, {"kind": "all"}, {"layer": "base"}])
def test_cursor_cannot_cross_page_size_or_exact_filters(generation, changes):
    sources = sources_for(generation)
    options = dict(limit=1, query="COMMON", kind="module")
    cursor = sources.list_entries(**options).next_cursor
    with pytest.raises(CoreError) as caught:
        sources.list_entries(**(options | changes), cursor=cursor)
    assert caught.value.code == "INVALID_SOURCE_CURSOR"


@pytest.mark.parametrize("field,value", [("project_id", "other"), ("snapshot_id", "f" * 64),
    ("manifest_hash", "e" * 64), ("version", 1), ("extra", True), ("last", [True, "data.xml"])])
def test_cursor_cannot_cross_snapshot_manifest_or_version_binding(generation, field, value):
    sources = sources_for(generation)
    cursor = sources.list_entries(limit=1, kind="module").next_cursor
    record = json.loads(base64.urlsafe_b64decode(cursor))
    record[field] = value
    cursor = base64.urlsafe_b64encode(canonical_bytes(record)).decode("ascii")
    with pytest.raises(CoreError) as caught:
        sources.list_entries(limit=1, kind="module", cursor=cursor)
    assert caught.value.code == "INVALID_SOURCE_CURSOR"


@pytest.mark.parametrize("cursor", ["", "%%%", True, "x" * 8193,
    base64.urlsafe_b64encode(b'{"version":true,"limit":1}').decode("ascii")],
    ids=["empty", "invalid-base64", "boolean", "over-bound", "boolean-version"])
def test_malformed_cursor_is_explicitly_rejected(generation, cursor):
    with pytest.raises(CoreError) as caught:
        sources_for(generation).list_entries(limit=1, cursor=cursor)
    assert caught.value.code == "INVALID_SOURCE_CURSOR"


@pytest.mark.parametrize("options", [{"limit": True}, {"limit": 0}, {"limit": 201},
    {"query": None}, {"query": "x\x00"}, {"query": "\ud800"}, {"kind": "bsl"},
    {"layer": True}, {"layer": "missing"}])
def test_invalid_filters_keep_existing_error_contract(generation, options):
    with pytest.raises(CoreError) as caught:
        sources_for(generation).list_entries(**options)
    assert caught.value.code == "INVALID_QUERY_OPTIONS"


@pytest.mark.parametrize("change,code", [("snapshot", "SOURCE_REF_MISMATCH"),
    ("hash", "SOURCE_REF_MISMATCH"), ("missing", "SOURCE_NOT_FOUND"),
    ("subclass", "SOURCE_REF_MISMATCH"), ("object", "SOURCE_REF_MISMATCH")])
@pytest.mark.parametrize("name", ["read", "graph"])
def test_source_reference_must_match_exact_selected_snapshot_and_hash(generation, change, code, name):
    sources = sources_for(generation)
    ref = sources.resolve("base", MODULE)
    if change == "snapshot":
        ref = replace(ref, snapshot=SnapshotRef(ref.snapshot.project_id, "f" * 64, "f" * 64))
    elif change == "hash":
        ref = replace(ref, raw_sha256="e" * 64)
    elif change == "missing":
        ref = replace(ref, relative_path="missing.bsl")
    elif change == "subclass":
        class Derived(SourceRef):
            pass
        ref = Derived(ref.snapshot, ref.layer_id, ref.relative_path, ref.raw_sha256)
    else:
        ref = object()
    with pytest.raises(CoreError) as caught:
        operation(sources, facade.PosixSnapshotGraph(generation.snapshot, sources), ref, name)
    assert caught.value.code == code


@pytest.mark.parametrize("name", ["resolve", "list", "read", "graph", "impact", "verify"])
def test_membership_revocation_precedes_every_operation_and_retained_io(generation, monkeypatch, name):
    sources = sources_for(generation)
    ref = sources.resolve("base", MODULE)
    graph = facade.PosixSnapshotGraph(generation.snapshot, sources)
    with generation.state.transaction(generation.owner, write=True) as tx:
        revoke_membership(tx, generation.principal)
    monkeypatch.setattr(retained.Directory, "file", lambda *a, **k: pytest.fail("Revoked read reached retained content"))
    with pytest.raises(CoreError) as caught:
        operation(sources, graph, ref, name)
    assert caught.value.code == "PROJECT_FORBIDDEN"


@pytest.mark.parametrize("name", ["read", "graph"])
def test_exit_revocation_never_discloses_materialized_bytes_or_graph(generation, monkeypatch, name):
    sources = sources_for(generation)
    ref = sources.resolve("base", MODULE)
    graph = facade.PosixSnapshotGraph(generation.snapshot, sources)
    original_exit = backend._PosixSnapshotSession.__exit__
    def revoked(session, kind, value, traceback):
        if kind is None:
            with generation.state.transaction(generation.owner, write=True) as tx:
                revoke_membership(tx, generation.principal)
        return original_exit(session, kind, value, traceback)
    monkeypatch.setattr(backend._PosixSnapshotSession, "__exit__", revoked)
    with pytest.raises(CoreError) as caught:
        operation(sources, graph, ref, name)
    assert caught.value.code == "PROJECT_FORBIDDEN"
    traceback = caught.value.__traceback__
    checked = False
    while traceback:
        if traceback.tb_frame.f_code is facade.PosixSnapshotSources._run.__code__:
            assert traceback.tb_frame.f_locals["result"] is None
            checked = True
        traceback = traceback.tb_next
    assert checked


def test_request_authorization_denial_after_read_prevents_disclosure(generation, monkeypatch):
    denied = []
    failure = CoreError("TEST_REQUEST_EXPIRED", "Request permission expired")
    def authorize():
        if denied:
            raise failure
    sources = sources_for(generation, _authorize_read=authorize)
    ref = sources.resolve("base", MODULE)
    original_read = backend._PosixSnapshotSession.read_source
    def expired(session, selected):
        result = original_read(session, selected)
        denied.append(True)
        return result
    monkeypatch.setattr(backend._PosixSnapshotSession, "read_source", expired)
    with pytest.raises(CoreError) as caught:
        sources.read_source(ref)
    assert caught.value is failure
    with pytest.raises(CoreError) as caught:
        sources.list_entries()
    assert caught.value is failure


def test_retained_mutation_after_read_refuses_exit_and_live_source_changes_do_not(generation, monkeypatch):
    live = generation.root / "live.bsl"
    live.write_bytes(generation.contents[MODULE])
    sources = sources_for(generation)
    ref = sources.resolve("base", MODULE)
    live.write_bytes(b"changed live source")
    assert sources.read_source(ref) == generation.contents[MODULE]
    live.unlink()
    assert sources.read_source(ref) == generation.contents[MODULE]
    original_read = backend._PosixSnapshotSession.read_source
    def changed(session, selected):
        result = original_read(session, selected)
        (generation.path / "sources/base" / MODULE).write_bytes(b"changed retained source")
        return result
    monkeypatch.setattr(backend._PosixSnapshotSession, "read_source", changed)
    with pytest.raises(CoreError):
        sources.read_source(ref)


@pytest.mark.parametrize("depth", [0, 6, True, 1.0, "2", None])
def test_graph_impact_depth_contract_authorizes_before_invalid_options(generation, depth):
    sources = sources_for(generation)
    ref = sources.resolve("base", MODULE)
    graph = facade.PosixSnapshotGraph(generation.snapshot, sources)
    with pytest.raises(CoreError) as caught:
        graph.impact(ref, depth=depth)
    assert caught.value.code == "INVALID_QUERY_OPTIONS"
    with generation.state.transaction(generation.owner, write=True) as tx:
        revoke_membership(tx, generation.principal)
    with pytest.raises(CoreError) as caught:
        graph.impact(ref, depth=depth)
    assert caught.value.code == "PROJECT_FORBIDDEN"


def test_foreign_thread_and_reentrant_callback_cannot_open_a_session(generation):
    calls, errors, nested = [], [], []
    def authorize():
        calls.append(True)
        if not nested:
            with pytest.raises(CoreError) as caught:
                sources.list_entries()
            nested.append(caught.value.code)
    sources = sources_for(generation, _authorize_read=authorize)
    def foreign():
        try:
            sources.list_entries()
        except CoreError as exc:
            errors.append(exc.code)
    thread = Thread(target=foreign)
    thread.start(); thread.join(timeout=5)
    assert not thread.is_alive() and errors == ["SNAPSHOT_READ_SESSION_INVALID"] and not calls
    assert sources.list_entries().entries
    assert nested == ["SNAPSHOT_READ_SESSION_INVALID"] and calls


def test_forked_facade_refuses_before_callback_but_parent_still_reads(generation):
    sources = sources_for(generation, _authorize_read=lambda: None)
    read_fd, write_fd = os.pipe()
    child = os.fork()
    if child == 0:
        os.close(read_fd)
        signal.alarm(5)
        try:
            sources.list_entries()
            raw = b"unexpected success"
        except CoreError as exc:
            raw = exc.code.encode("ascii")
        except BaseException as exc:
            raw = ("unexpected " + type(exc).__name__).encode("ascii")
        os.write(write_fd, raw)
        os.close(write_fd)
        os._exit(0)
    os.close(write_fd)
    try:
        raw = os.read(read_fd, 100)
    finally:
        os.close(read_fd)
        waited, status = os.waitpid(child, 0)
    assert waited == child and status == 0 and raw == b"SNAPSHOT_READ_SESSION_INVALID"
    assert sources.list_entries().entries


def test_typed_budgets_are_per_operation_and_path_reader_never_falls_back(generation):
    small = replace(generation.options["limits"], copied_byte_budget=generation.copied - 1)
    with pytest.raises(CoreError) as caught:
        sources_for(generation, _limits=small).list_entries()
    assert caught.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
    assert sources_for(generation).list_entries().entries
    for options in ({"_limits": None}, {"_graph_limits": {}}, {"_authorize_read": None}):
        with pytest.raises(CoreError) as caught:
            sources_for(generation, **options)
        assert caught.value.code == "INVALID_QUERY_OPTIONS"
    class PathOnly:
        def open(self, **options):
            pytest.fail("Path-only graph reader was used")
    with pytest.raises(CoreError) as caught:
        sources_for(generation, _factory=PathOnly())
    assert caught.value.code == "GRAPH_ADAPTER_UNAVAILABLE"


def test_fresh_process_reopens_catalogued_generation_and_real_sqlite(generation):
    options = json.dumps({"state": str(generation.state.path), "snapshot": asdict(generation.snapshot),
        "principal": asdict(generation.principal), "limits": asdict(generation.options["limits"]),
        "graph_limits": asdict(generation.options["graph_limits"])})
    code = '''
import json,sys
from pathlib import Path
from rentgen_core._posix_snapshot_facade import PosixSnapshotSources,PosixSnapshotGraph
from rentgen_core._posix_snapshot_session import PosixSnapshotLimits
from rentgen_core._verified_graph import VerifiedGraphLimits
from rentgen_core.context import Principal,SnapshotRef
from rentgen_core.manifests import sha256
from rentgen_core.state import ProjectState
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
x=json.loads(sys.argv[1]); snapshot=SnapshotRef(**x['snapshot'])
s=PosixSnapshotSources(snapshot,ProjectState(Path(x['state']),snapshot.project_id),
    Principal(**x['principal']),RentgenGraphReaderFactory(),PosixSnapshotLimits(**x['limits']),
    VerifiedGraphLimits(**x['graph_limits']),lambda:None)
r=s.resolve('base',sys.argv[2]); g=PosixSnapshotGraph(snapshot,s)
assert g.resolve_module(r)['result']['graph_modules']
print(json.dumps({'snapshot':snapshot.snapshot_id,'sha256':sha256(s.read_source(r))}))
'''
    result = subprocess.run([sys.executable, "-c", code, options, MODULE],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"snapshot": generation.snapshot.snapshot_id,
                                        "sha256": sha256(generation.contents[MODULE])}


@linux
def test_actual_linux_resolver_eager_read_and_fresh_context(generation, monkeypatch):
    registry = ProjectRegistry.create(generation.root / "registry.sqlite3")
    source = generation.root / "live"
    source.mkdir()
    # Fixture registration of an already-owned catalogued tree, not a public
    # attach/migrate operation or a fake platform adapter.
    with _sqlite.transaction(registry.path, write=True) as db:
        db.execute("INSERT INTO projects VALUES (?,?,?,?)", (generation.snapshot.project_id,
            str(source), str(generation.root), "Constructed generation"))
    import rentgen_core.resolver as resolver_module
    monkeypatch.setattr(resolver_module, "verify_generation", lambda *a, **k: pytest.fail("Linux used Windows verifier"))
    calls = []
    for configured in (False, True):
        options = (dict(posix_snapshot_limits=generation.options["limits"],
                        posix_graph_limits=generation.options["graph_limits"]) if configured else {})
        resolver = ContextResolver(ProjectRegistry(registry.path), graph_reader_factory=RentgenGraphReaderFactory(), **options)
        ctx = resolver.resolve_context(generation.principal, Explicit(generation.snapshot.project_id),
            authorize_read=lambda: calls.append(True))
        assert type(ctx.sources) is facade.PosixSnapshotSources
        assert type(ctx.graph) is facade.PosixSnapshotGraph
        ref = ctx.sources.resolve("base", MODULE)
        assert ctx.sources.read_source(ref) == generation.contents[MODULE]
        assert ctx.graph.resolve_module(ref)["result"]["graph_modules"]
    assert calls


FIXTURE = Path(__file__).resolve().parents[2] / "packaging/fixtures/edt-metadata-v1/created"


def test_metadata_navigation_reads_one_verified_posix_session_per_operation(make_generation, monkeypatch):
    from rentgen_core import project_navigation as nav

    extra = {p.relative_to(FIXTURE).as_posix(): p.read_bytes() for p in sorted(FIXTURE.rglob("*")) if p.is_file()}
    generation = make_generation(extra=extra, source_format="designer_xml")
    sources = sources_for(generation)
    graph = facade.PosixSnapshotGraph(generation.snapshot, sources)
    ctx = ProjectContext(generation.snapshot.project_id, generation.principal, "fixture-request",
                         generation.state, generation.root / "live", generation.snapshot, sources, graph)
    opened, original = [], facade.open_posix_snapshot_session
    monkeypatch.setattr(facade, "open_posix_snapshot_session",
                        lambda **options: opened.append(1) or original(**options))
    summary = nav.summary(ctx)
    assert summary["schema"] == 1 and summary["snapshot"] == asdict(generation.snapshot)
    found = nav.search(ctx, query="Products", metadata_type="Catalog", layer_id="base")
    assert [o["source_ref"]["relative_path"] for o in found["objects"]] == ["Catalogs/Products.xml"]
    assert found["objects"][0]["uuid_status"] == "unverified"
    details = nav.object_details(ctx, layer_id="base", relative_path="Catalogs/Products.xml")
    assert "Article" in [item["name"] for item in details["object"]["attributes"]["items"]]
    assert len(opened) == 3
    # Every other POSIX session consumer stays refused, and a busy owner is exclusive.
    from rentgen_core.sources import SnapshotReadLimits
    with sources.read_session(limits=SnapshotReadLimits(), purpose="metadata-navigation") as session:
        assert len(session.entries()) == 3 + len(extra)
        with pytest.raises(CoreError) as error:
            with sources.read_session(limits=SnapshotReadLimits(), purpose="metadata-navigation"):
                pass
        assert error.value.code == "SNAPSHOT_READ_SESSION_INVALID"
    with pytest.raises(CoreError):
        sources.read_session(limits=object(), purpose="metadata-navigation")


def test_metadata_navigation_rechecks_current_permission_on_posix(make_generation):
    from rentgen_core import project_navigation as nav

    extra = {p.relative_to(FIXTURE).as_posix(): p.read_bytes() for p in sorted(FIXTURE.rglob("*")) if p.is_file()}
    generation = make_generation(extra=extra, source_format="designer_xml")
    sources = sources_for(generation)
    ctx = ProjectContext(generation.snapshot.project_id, generation.principal, "fixture-request",
                         generation.state, generation.root / "live", generation.snapshot, sources,
                         facade.PosixSnapshotGraph(generation.snapshot, sources))
    with generation.state.transaction(generation.owner, write=True) as tx:
        revoke_membership(tx, generation.principal)
    with pytest.raises(CoreError) as error:
        nav.summary(ctx)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_manual_draft_authoring_reads_exact_retained_source_on_posix(generation, monkeypatch):
    from uuid import uuid4
    from rentgen_core import draft_editing, drafts
    from rentgen_core.proposals import ProposalLimits, create_proposal

    sources = sources_for(generation, _principal=generation.owner)
    ctx = ProjectContext(generation.snapshot.project_id, generation.owner, "fixture-request",
                         generation.state, generation.root / "live", generation.snapshot, sources,
                         facade.PosixSnapshotGraph(generation.snapshot, sources))
    ref = sources.resolve("base", MODULE)
    opened, original = [], facade.open_posix_snapshot_session
    monkeypatch.setattr(facade, "open_posix_snapshot_session",
                        lambda **options: opened.append(1) or original(**options))
    replacement = generation.contents[MODULE].replace(b"Callee.Target();", b"Callee.Target(); // reviewed")
    proposal = create_proposal(ctx, ref, replacement,
                               limits=ProposalLimits(1024**2, 1024**2, 1536 * 1024, 256 * 1024))
    assert proposal.source_ref == ref and proposal.replacement_bytes == replacement
    draft = str(uuid4())
    first = draft_editing.start_draft(ctx, ref, draft_id=draft, title="Manual review",
                                      operation_id=str(uuid4()))
    assert first["revision"] == 1 and first["source_ref"]["relative_path"] == MODULE
    second = draft_editing.edit_draft(ctx, draft, expected_revision=1, operation_id=str(uuid4()),
                                      edits=[{"old_text": "Callee.Target();", "new_text": "Callee.Target(); // edited"}])
    assert second["revision"] == 2
    saved = drafts.get_draft(ctx, draft)
    assert saved["receipt"]["revision"] == 2
    assert [row["revision"] for row in drafts.draft_history(ctx, draft)["items"]] == [2, 1]
    # Each source read used one fresh verified POSIX session; nothing touched live files.
    assert len(opened) >= 2
    assert not (generation.root / "live").exists()
    with pytest.raises(CoreError) as error:
        draft_editing.edit_draft(ctx, draft, expected_revision=1, operation_id=str(uuid4()),
                                 edits=[{"old_text": "Callee.Target();", "new_text": "stale"}])
    assert error.value.code.startswith("DRAFT")


def test_proposal_diff_and_raw_draft_save_revalidate_retained_source_on_posix(generation):
    from uuid import uuid4
    from rentgen_core import drafts
    from rentgen_core.proposals import ProposalLimits, create_proposal_presentation, parse_proposal_presentation

    sources = sources_for(generation, _principal=generation.owner)
    ctx = ProjectContext(generation.snapshot.project_id, generation.owner, "fixture-request",
                         generation.state, generation.root / "live", generation.snapshot, sources,
                         facade.PosixSnapshotGraph(generation.snapshot, sources))
    ref = sources.resolve("base", MODULE)
    limits = ProposalLimits(1024**2, 1024**2, 1536 * 1024, 256 * 1024)
    replacement = generation.contents[MODULE].replace(b"Callee.Target();", b"Callee.Target(); // diff")
    created = create_proposal_presentation(ctx, ref, replacement, limits=limits)
    assert created.diff.status == "complete" and "// diff" in created.diff.text
    assert parse_proposal_presentation(ctx, created.canonical_json, limits=limits) == created
    draft = str(uuid4())
    saved = drafts.save_draft(ctx, created.canonical_json, draft_id=draft, title="Raw save",
                              expected_revision=0, operation_id=str(uuid4()))
    assert saved["revision"] == 1 and saved["source_ref"]["relative_path"] == MODULE
    # A proposal whose retained source no longer matches the snapshot is refused.
    forged = created.canonical_json.replace(ref.raw_sha256.encode(), b"0" * 64)
    assert forged != created.canonical_json
    with pytest.raises(CoreError):
        drafts.save_draft(ctx, forged, draft_id=draft, title="Raw save",
                          expected_revision=1, operation_id=str(uuid4()))
    assert [row["revision"] for row in drafts.draft_history(ctx, draft)["items"]] == [1]
    assert not (generation.root / "live").exists()
