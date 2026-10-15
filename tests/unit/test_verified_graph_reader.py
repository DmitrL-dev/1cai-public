"""Real SQLite/immutable bytes; this does not qualify POSIX capture or file leases."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import sqlite3
from threading import Thread

import pytest

from rentgen_core import _verified_graph as backend
from rentgen_core.context import SnapshotRef
from rentgen_core.errors import CoreError
from rentgen_core.graph import GraphBuildReceipt, open_verified_graph
from rentgen_core.manifests import (
    CapturedInput, build_manifest, build_source_document, canonical_bytes, sha256,
)
from rentgen_core.source_configuration import SourceConfiguration, SourceLayerSpec
from rentgen_graph.build_store import BuildInputs, build_snapshot_graph
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory, SEMANTIC_SCOPE

PATH = "base/CommonModules/Caller/Ext/Module.bsl"
PROJECT = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def graph(tmp_path):
    paths = (PATH, "base/CommonModules/Callee/Ext/Module.bsl")
    entries = tuple(CapturedInput("base", path.removeprefix("base/"), "a" * 64, 0, "utf-8") for path in paths)
    source = build_source_document(PROJECT, SourceConfiguration(1, (SourceLayerSpec("base", 0, "base", ".", "unknown"),)), (), entries)
    bindings = sorted([dict(asdict(entry), graph_source_path=path) for entry, path in zip(entries, paths)], key=lambda e: e["graph_source_path"])
    receipt = GraphBuildReceipt("2", "source-path-v1", sha256(source), sha256(canonical_bytes(bindings)),
                                "rentgen-captured-go-v1", "synthetic-scanner-fixture", "fixture-builder", "b" * 64, SEMANTIC_SCOPE)
    ndjson = tmp_path / "calls.ndjson"
    records = [
        dict(name="Caller", module="Caller", source_path=paths[0], line=1, end_line=3,
             is_export=True, calls=["Callee.Target"]),
        dict(name="Target", module="Callee", source_path=paths[1], line=1, end_line=3,
             is_export=True, calls=[]),
    ]
    ndjson.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
    path = tmp_path / "graph.sqlite3"
    build_snapshot_graph(BuildInputs(ndjson, None), path, receipt, source_paths=paths)

    def bundle(raw=None):
        raw = path.read_bytes() if raw is None else raw
        manifest = build_manifest(source, dict(asdict(receipt), relative_path="graph.sqlite3",
            raw_sha256=sha256(raw), sqlite_version=sqlite3.sqlite_version, quality="unavailable"), [
                dict(relative_path=name, raw_sha256="c" * 64, size_bytes=0)
                for name in ("inputs/callgraph.ndjson", "inputs/scanner-coverage.json")
            ])
        snapshot = SnapshotRef(PROJECT, sha256(manifest), sha256(manifest))
        return dict(graph_bytes=raw, manifest_bytes=manifest, snapshot=snapshot,
                    authorize_read=lambda: None,
                    limits=backend.VerifiedGraphLimits(image_buffer_budget=2 * len(raw)))
    return path, bundle


def opened(options):
    return open_verified_graph(RentgenGraphReaderFactory(), **options)


def direct_opened(options):
    return RentgenGraphReaderFactory().open_verified(**options)


@pytest.fixture(params=[opened, direct_opened], ids=["core-seam", "adapter-factory"])
def public_context(request):
    return request.param


def assert_native_closed(reader, db):
    assert reader._owner._phase == "closed" and reader._owner._db is None
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        db.execute("SELECT 1")


def test_one_connection_uses_verified_bytes_after_original_path_is_replaced(graph, monkeypatch):
    path, bundle = graph
    options = bundle()
    expected = RentgenGraphReaderFactory().open(graph_path=path, snapshot=options["snapshot"])
    resolution = expected.resolve_module(PATH)
    impact = expected.module_impact(PATH, max_depth=5, max_edges=600)
    calls = []
    connect = sqlite3.connect
    def only_memory(name, *args, **kwargs):
        calls.append(name)
        assert name == ":memory:", "Verified graph reopened a pathname"
        return connect(name, *args, **kwargs)
    monkeypatch.setattr(backend.sqlite3, "connect", only_memory)
    with opened(options) as reader:
        path.unlink()
        path.write_bytes(b"foreign replacement")
        assert reader.resolve_module(PATH) == resolution
        assert reader.module_impact(PATH, max_depth=5, max_edges=600) == impact
        assert not hasattr(reader, "execute") and not hasattr(reader, "cursor")
    assert calls == [":memory:"]
    assert reader._owner._db is reader._owner._authorize is None
    assert reader._owner._raw is reader._owner._manifest is None
    with pytest.raises(CoreError, match="not active"):
        reader.resolve_module(PATH)
    with pytest.raises(CoreError, match="not active"):
        reader._owner.__enter__()


def test_legacy_factory_never_falls_back_to_path_open(graph):
    class Legacy:
        def open(self, **kwargs):
            pytest.fail("Path fallback bypassed byte verification")
    with pytest.raises(CoreError) as error:
        with open_verified_graph(Legacy(), **graph[1]()):
            pytest.fail("Path-only reader was admitted")
    assert error.value.code == "GRAPH_ADAPTER_UNAVAILABLE"


@pytest.mark.parametrize("change", ["graph", "manifest", "snapshot", "mutable"])
def test_digest_snapshot_and_immutable_input_binding_fail_closed(graph, change):
    options = graph[1]()
    if change == "graph": options["graph_bytes"] += b"changed"
    elif change == "manifest": options["manifest_bytes"] += b" "
    elif change == "snapshot": options["snapshot"] = SnapshotRef(PROJECT, "d" * 64, "d" * 64)
    else: options["graph_bytes"] = bytearray(options["graph_bytes"])
    with pytest.raises(CoreError):
        with opened(options):
            pytest.fail("Unbound input admitted")


@pytest.mark.parametrize("damage", ["invalid", "wal", "schema", "counts"])
def test_actual_sqlite_damage_cannot_be_accepted_with_matching_digest(graph, damage):
    path, bundle = graph
    if damage in {"schema", "counts"}:
        with sqlite3.connect(path) as db:
            if damage == "schema": db.execute("DROP TABLE quality")
            else: db.execute("UPDATE meta SET value='9999' WHERE key='n_modules'")
        raw = path.read_bytes()
    else:
        raw = bytearray(path.read_bytes())
        if damage == "wal": raw[18:20] = b"\2\2"
        else: raw[100:200] = b"x" * 100
        raw = bytes(raw)
    with pytest.raises(CoreError) as error:
        with opened(bundle(raw)):
            pytest.fail("Damaged graph admitted")
    assert error.value.code == "SNAPSHOT_CORRUPT"


def test_authorization_denial_precedes_connection_and_preserves_original(graph, monkeypatch):
    options = graph[1]()
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked")
    def deny(): raise denial
    options["authorize_read"] = deny
    monkeypatch.setattr(backend.sqlite3, "connect", lambda *a, **k: pytest.fail("Denied graph reached SQLite"))
    with pytest.raises(CoreError) as error:
        with opened(options): pass
    assert error.value is denial


def test_revocation_after_actual_query_closes_before_disclosure(graph, monkeypatch):
    options = graph[1](); state = {"revoked": False}
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked")
    def authorize():
        if state["revoked"]: raise denial
    options["authorize_read"] = authorize
    with opened(options) as reader:
        original = reader._store.resolve_module
        def revoke(path):
            result = original(path)
            state["revoked"] = True
            return result
        monkeypatch.setattr(reader._store, "resolve_module", revoke)
        with pytest.raises(CoreError) as error: reader.resolve_module(PATH)
        assert error.value is denial
        assert reader._owner._db is None


@pytest.mark.parametrize("statement", [
    "ATTACH DATABASE ? AS external", "PRAGMA query_only=OFF", "PRAGMA writable_schema=ON",
    "DELETE FROM module", "SELECT sqlite_version()", "SELECT load_extension(?)",
])
def test_real_sqlite_authorizer_denies_external_paths_mutation_and_unknown_functions(graph, tmp_path, statement):
    foreign = tmp_path / "external.sqlite3"
    with sqlite3.connect(foreign) as db: db.execute("CREATE TABLE secret(value)")
    before = foreign.read_bytes()
    with opened(graph[1]()) as reader:
        owner = reader._owner
        parameters = (str(foreign),) if "?" in statement else ()
        with pytest.raises(CoreError) as error:
            owner.run(lambda: owner._queries.execute(statement, parameters).fetchall(), PATH)
        assert error.value.code == "SNAPSHOT_CORRUPT"
        assert "not authorized" in str(error.value.__cause__)
        assert owner._db is None
    assert foreign.read_bytes() == before


def test_foreign_thread_cannot_query_and_does_not_break_owner(graph):
    with opened(graph[1]()) as reader:
        errors = []
        def foreign():
            try: reader.resolve_module(PATH)
            except BaseException as error: errors.append(error)
        thread = Thread(target=foreign); thread.start(); thread.join(timeout=5)
        assert not thread.is_alive()
        assert len(errors) == 1 and errors[0].code == "SNAPSHOT_READ_SESSION_INVALID"
        assert reader.resolve_module(PATH)["graph_modules"]


@pytest.mark.skipif(not hasattr(os, "fork"), reason="Actual POSIX fork ownership guard")
def test_forked_child_cannot_inherit_live_graph_capability(graph, public_context):
    context = public_context(graph[1]())
    with context as reader:
        db = reader._owner._db
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            results = []
            for operation in (lambda: reader.resolve_module(PATH),
                              lambda: context.__exit__(None, None, None)):
                try:
                    operation()
                    results.append("unexpected success")
                except CoreError as error:
                    results.append(error.code)
            results.append("held" if reader._owner._db is not None else "closed")
            os.write(write_fd, ",".join(results).encode())
            os.close(write_fd)
            os._exit(0)
        os.close(write_fd)
        try:
            result = os.read(read_fd, 128)
        finally:
            os.close(read_fd)
            status = os.waitpid(pid, 0)[1]
        assert result == b"SNAPSHOT_READ_SESSION_INVALID,SNAPSHOT_READ_SESSION_INVALID,held"
        assert status == 0
        assert reader.resolve_module(PATH)["graph_modules"]
    assert_native_closed(reader, db)


@pytest.mark.parametrize("field", ["max_graph_bytes", "image_buffer_budget"])
def test_image_bounds_refuse_before_sqlite_without_reducing_one_gib_contract(graph, monkeypatch, field):
    options = graph[1](); size = len(options["graph_bytes"])
    assert options["limits"].max_graph_bytes == 1024**3
    options["limits"] = replace(options["limits"], **{field: size - 1 if field == "max_graph_bytes" else 2 * size - 1})
    monkeypatch.setattr(backend.sqlite3, "connect", lambda *a, **k: pytest.fail("Over-budget image allocated"))
    with pytest.raises(CoreError) as error:
        with opened(options): pass
    assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"


@pytest.mark.parametrize("kind", ["rows", "result", "steps"])
def test_real_row_result_and_vm_work_budgets_refuse_without_partial_success(graph, kind):
    options = graph[1]()
    if kind == "result": options["limits"] = replace(options["limits"], max_result_bytes=1)
    with opened(options) as reader:
        if kind == "rows":
            reader._owner._limits = replace(options["limits"], max_row_bytes=1)
        elif kind == "steps":
            reader._owner._limits = replace(options["limits"], max_vm_steps=1000)
        with pytest.raises(CoreError) as error:
            if kind == "steps":
                owner = reader._owner
                owner.run(lambda: owner._queries.execute("WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000) SELECT count(*) FROM n").fetchall(), PATH)
            else: reader.resolve_module(PATH)
        assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
        assert reader._owner._db is None


def test_deadline_before_query_refuses_and_closes(graph, monkeypatch):
    now = [100]
    monkeypatch.setattr(backend, "monotonic", lambda: now[0])
    with opened(graph[1]()) as reader:
        now[0] += 30
        with pytest.raises(CoreError) as error: reader.resolve_module(PATH)
        assert error.value.code == "SNAPSHOT_READ_DEADLINE_EXCEEDED"
        assert reader._owner._db is None


def test_progress_revocation_preserves_exact_denial_and_closes(graph):
    options = graph[1](); armed = [False]
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked during SQL")
    def authorize():
        if armed[0] and reader._owner._steps: raise denial
    options["authorize_read"] = authorize
    with opened(options) as reader:
        armed[0] = True
        owner = reader._owner
        with pytest.raises(CoreError) as error:
            owner.run(lambda: owner._queries.execute("WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000) SELECT count(*) FROM n").fetchall(), PATH)
        assert error.value is denial and owner._db is None


def test_serialization_reauthorizes_before_return(graph, monkeypatch):
    options = graph[1](); revoked = [False]
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked during serialization")
    def authorize():
        if revoked[0]: raise denial
    options["authorize_read"] = authorize
    encoder = backend.json.JSONEncoder
    class RevokeAfterEncoding(encoder):
        def iterencode(self, value):
            yield from super().iterencode(value)
            revoked[0] = True
    with opened(options) as reader:
        monkeypatch.setattr(backend.json, "JSONEncoder", RevokeAfterEncoding)
        with pytest.raises(CoreError) as error: reader.resolve_module(PATH)
        assert error.value is denial and reader._owner._db is None


def test_close_once_clears_buffers_and_preserves_body_failure(graph, monkeypatch):
    connect = sqlite3.connect; closes = []
    class Connection(sqlite3.Connection):
        def close(self):
            closes.append(self)
            super().close()
            raise OSError("lost close acknowledgement")
    monkeypatch.setattr(backend.sqlite3, "connect", lambda *a, **k: connect(*a, factory=Connection, **k))
    failure = ValueError("operation failed")
    with pytest.raises(ValueError) as error:
        with opened(graph[1]()) as reader:
            raise failure
    assert error.value is failure and len(closes) == 1
    assert reader._owner._db is reader._owner._authorize is None
    assert reader._owner._raw is reader._owner._manifest is None


@pytest.mark.parametrize("options", [dict(image_buffer_budget=True), dict(image_buffer_budget=2*1024**3+1)])
def test_invalid_typed_budget_is_not_a_capacity_claim(options):
    with pytest.raises(CoreError): backend.VerifiedGraphLimits(**options)


def test_foreign_thread_public_exit_refuses_and_owner_final_exit_closes(graph, public_context):
    context = public_context(graph[1]())
    with context as reader:
        owner = reader._owner; db = owner._db; errors = []
        def foreign():
            try: context.__exit__(None, None, None)
            except CoreError as error: errors.append(error)
        thread = Thread(target=foreign); thread.start(); thread.join(timeout=5)
        assert not thread.is_alive()
        assert len(errors) == 1 and errors[0].code == "SNAPSHOT_READ_SESSION_INVALID"
        assert owner._phase == "active" and owner._db is db
        assert reader.resolve_module(PATH)["graph_modules"]
    assert_native_closed(reader, db)


def test_reentrant_public_exit_during_query_cannot_consume_owner_close(graph, public_context):
    options = graph[1](); armed = [False]; refusals = []
    def authorize():
        if armed[0]:
            owner = reader._owner; db = owner._db
            with pytest.raises(CoreError) as error: context.__exit__(None, None, None)
            assert error.value.code == "SNAPSHOT_READ_SESSION_INVALID"
            assert owner._phase == "active" and owner._db is db
            refusals.append(error.value)
    options["authorize_read"] = authorize
    context = public_context(options)
    with context as reader:
        db = reader._owner._db
        armed[0] = True
        assert reader.resolve_module(PATH)["graph_modules"]
        armed[0] = False
        assert refusals
    assert_native_closed(reader, db)


def test_retained_error_and_cursor_do_not_keep_statement_live_after_budget_failure(graph):
    with opened(graph[1]()) as reader:
        owner = reader._owner; retained = []; failure = []
        def over_budget():
            rows = owner._queries.execute("SELECT * FROM module")
            retained.extend([rows, rows._cursor])
            return rows.fetchall()
        owner._limits = replace(owner._limits, max_row_bytes=1)
        try: owner.run(over_budget, PATH)
        except CoreError as error: failure.append(error)
        assert failure[0].code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
        assert failure[0].__traceback__ is not None
        assert not owner._rows and retained[0]._cursor is None and owner._db is None
        with pytest.raises(sqlite3.ProgrammingError, match="closed cursor"):
            retained[1].fetchone()


def test_all_statement_owners_are_released_at_eof_and_context_exit(graph):
    retained = []
    with opened(graph[1]()) as reader:
        owner = reader._owner
        for _ in range(100):
            assert reader.resolve_module(PATH)["graph_modules"]
            assert not owner._rows
        def hold():
            rows = owner._queries.execute("SELECT * FROM module")
            retained.extend([rows, rows._cursor])
            return {}
        owner.run(hold, PATH)
        assert len(owner._rows) == 1
    assert not owner._rows and retained[0]._cursor is None
    with pytest.raises(sqlite3.ProgrammingError, match="closed cursor"): retained[1].fetchone()


def test_one_gib_image_limit_does_not_hide_unbounded_impact_seed_fetch(graph):
    path, bundle = graph
    with sqlite3.connect(path) as db:
        row = list(db.execute("SELECT * FROM subroutine WHERE source_path=? LIMIT 1", (PATH,)).fetchone())
        placeholders = ",".join("?" for _ in row)
        for index in range(5000):
            row[0] = "seed:" + str(index)
            db.execute("INSERT INTO subroutine VALUES (" + placeholders + ")", row)
        db.execute("UPDATE meta SET value=(SELECT count(*) FROM subroutine) WHERE key='n_subroutines'")
    options = bundle()
    options["limits"] = replace(options["limits"], max_row_bytes=250000)
    with opened(options) as reader:
        with pytest.raises(CoreError) as error:
            reader.module_impact(PATH, max_depth=5, max_edges=600)
        assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
        assert not reader._owner._rows and reader._owner._db is None


def test_sqlite_value_limit_refuses_large_cell_before_python_materialization(graph):
    path, bundle = graph
    with sqlite3.connect(path) as db:
        db.execute("UPDATE module SET display_name=?", ("x" * 100000,))
    options = bundle()
    options["limits"] = replace(options["limits"], max_value_bytes=65536)
    with opened(options) as reader:
        with pytest.raises(CoreError) as error: reader.resolve_module(PATH)
        assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
        assert reader._owner._db is None


def test_successful_body_cannot_mask_connection_close_failure(graph, monkeypatch):
    connect = sqlite3.connect; closes = []
    class Connection(sqlite3.Connection):
        def close(self):
            closes.append(self)
            super().close()
            raise OSError("lost close acknowledgement")
    monkeypatch.setattr(backend.sqlite3, "connect", lambda *a, **k: connect(*a, factory=Connection, **k))
    with pytest.raises(CoreError, match="cleanup failed"):
        with opened(graph[1]()) as reader:
            assert reader.resolve_module(PATH)["graph_modules"]
    assert len(closes) == 1 and reader._owner._db is None


def test_unavailable_deserialize_has_no_path_fallback(graph, monkeypatch):
    options = graph[1]()
    monkeypatch.setattr(backend.sqlite3, "Connection", object)
    monkeypatch.setattr(backend.sqlite3, "connect", lambda *a, **k: pytest.fail("Missing primitive reached SQLite"))
    with pytest.raises(CoreError) as error:
        with opened(options): pass
    assert error.value.code == "GRAPH_ADAPTER_UNAVAILABLE"


def test_reentrant_public_exit_during_final_authorization_still_closes(graph, public_context):
    options = graph[1](); armed = [False]; refusals = []
    def authorize():
        if armed[0]:
            with pytest.raises(CoreError) as error:
                context.__exit__(None, None, None)
            assert error.value.code == "SNAPSHOT_READ_SESSION_INVALID"
            assert reader._owner._db is not None
            refusals.append(error.value)
    options["authorize_read"] = authorize
    context = public_context(options)
    with context as reader:
        db = reader._owner._db
        armed[0] = True
    assert refusals
    assert_native_closed(reader, db)


def test_abandoned_statement_close_failure_cannot_return_success(graph, monkeypatch):
    connect = sqlite3.connect; armed = [False]
    class Cursor(sqlite3.Cursor):
        def close(self):
            super().close()
            if armed[0]: raise OSError("statement close acknowledgement lost")
    class Connection(sqlite3.Connection):
        def execute(self, *args, **kwargs):
            return self.cursor(factory=Cursor).execute(*args, **kwargs)
    monkeypatch.setattr(backend.sqlite3, "connect", lambda *a, **k: connect(*a, factory=Connection, **k))
    with opened(graph[1]()) as reader:
        armed[0] = True
        with pytest.raises(CoreError, match="statement cleanup failed"):
            reader.resolve_module(PATH)
        assert reader._owner._db is None and not reader._owner._rows


@pytest.mark.parametrize("depth,edges", [(None, 1), (True, 1), (0, 1), (6, 1), (1, True), (1, 601)])
def test_traversal_bounds_fail_closed_before_fixed_query(graph, depth, edges):
    with opened(graph[1]()) as reader:
        with pytest.raises(CoreError) as error:
            reader.module_impact(PATH, max_depth=depth, max_edges=edges)
        assert error.value.code == "INVALID_QUERY_OPTIONS"
        assert reader._owner._db is None


def test_deadline_interrupts_real_sql_progress_without_disclosing_result(graph, monkeypatch):
    now = [100]; armed = [False]; options = graph[1]()
    monkeypatch.setattr(backend, "monotonic", lambda: now[0])
    def authorize():
        if armed[0] and reader._owner._steps:
            now[0] += 30
    options["authorize_read"] = authorize
    with opened(options) as reader:
        armed[0] = True; owner = reader._owner
        with pytest.raises(CoreError) as error:
            owner.run(lambda: owner._queries.execute("WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000) SELECT count(*) FROM n").fetchall(), PATH)
        assert error.value.code == "SNAPSHOT_READ_DEADLINE_EXCEEDED"
        assert owner._db is None and not owner._rows


@pytest.mark.parametrize("steps", [1, 7])
def test_small_progress_budget_has_no_hidden_thousand_step_floor(graph, steps):
    options = graph[1]()
    limits = replace(options["limits"], max_vm_steps=steps)
    owner = backend._VerifiedGraph(options["graph_bytes"], options["manifest_bytes"],
        snapshot=options["snapshot"], authorize_read=options["authorize_read"], limits=limits)
    with pytest.raises(CoreError) as error:
        with owner:
            pytest.fail("Tiny budget admitted integrity/schema validation")
    assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
    assert owner._steps == owner._quantum == steps
    assert owner._db is None and not owner._rows
