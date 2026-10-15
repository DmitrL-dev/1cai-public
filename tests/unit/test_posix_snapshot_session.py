"""Real private POSIX trees/SQLite; synthetic scanner records, no live capture."""
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest

from project_access_test_support import grant_membership, revoke_membership
from rentgen_core import _posix_snapshot_session as backend
from rentgen_core import _posix_source_tree as retained
from rentgen_core._verified_graph import VerifiedGraphLimits
from rentgen_core.context import Principal, SnapshotRef
from rentgen_core.errors import CoreError
from rentgen_core.graph import GraphBuildReceipt
from rentgen_core.manifests import CapturedInput, build_manifest, build_source_document, canonical_bytes, sha256
from rentgen_core.snapshots import SnapshotCatalogEntry, SnapshotLayer
from rentgen_core.source_configuration import SourceConfiguration, SourceLayerSpec
from rentgen_core.state import ProjectState
from rentgen_graph.build_store import BuildInputs, build_snapshot_graph
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory, SEMANTIC_SCOPE

pytestmark = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Actual POSIX copied generation session")
PROJECT = "11111111-1111-4111-8111-111111111111"
MODULE = "CommonModules/Caller/Ext/Module.bsl"


@pytest.fixture
def make_generation(tmp_path):
    def build(*, graph_damage=None):
        root = tmp_path.resolve() / str(uuid4())
        root.mkdir(mode=0o700)
        owner, principal = Principal("owner", "local_os"), Principal("reader", "local_os")
        state = ProjectState.create(root / "state.sqlite3", PROJECT, owner)
        with state.transaction(owner, write=True) as tx:
            grant_membership(tx, principal, {"project:read"})
        generations = root / "generations"; generations.mkdir(mode=0o700)
        path = generations / str(uuid4()); path.mkdir(mode=0o700)
        contents = {MODULE: b"Procedure Caller() Export\nCallee.Target();\nEndProcedure\n",
                    "CommonModules/Callee/Ext/Module.bsl": b"Procedure Target() Export\nEndProcedure\n",
                    "data.xml": "<data>fixture</data>\n".encode()}
        entries = tuple(CapturedInput("base", name, sha256(raw), len(raw), "utf-8")
                        for name, raw in sorted(contents.items()))
        source = build_source_document(PROJECT, SourceConfiguration(1, (SourceLayerSpec("base", 0, "base", ".", "unknown"),)), (), entries)
        bindings = sorted([dict(asdict(entry), graph_source_path="base/" + entry.relative_path)
                           for entry in entries if entry.relative_path.endswith(".bsl")], key=lambda row: row["graph_source_path"])
        receipt = GraphBuildReceipt("2", "source-path-v1", sha256(source), sha256(canonical_bytes(bindings)),
            "rentgen-captured-go-v1", "synthetic-scanner-fixture", "fixture-builder", "b" * 64, SEMANTIC_SCOPE)
        for name, raw in contents.items():
            leaf = path / "sources" / "base" / name
            leaf.parent.mkdir(parents=True, exist_ok=True)
            leaf.write_bytes(raw)
        (path / "inputs").mkdir(); (path / "build-work").mkdir()
        records = [dict(name="Caller", module="Caller", source_path="base/" + MODULE,
                        line=1, end_line=3, is_export=True, calls=["Callee.Target"]),
                   dict(name="Target", module="Callee", source_path="base/CommonModules/Callee/Ext/Module.bsl",
                        line=1, end_line=2, is_export=True, calls=[])]
        ndjson = path / "inputs/callgraph.ndjson"
        ndjson.write_bytes(b"\n".join(json.dumps(row).encode() for row in records))
        (path / "inputs/scanner-coverage.json").write_bytes(b'{"fixture":"synthetic scanner coverage"}')
        build_snapshot_graph(BuildInputs(ndjson, None), path / "graph.sqlite3", receipt,
                             source_paths=tuple(row["graph_source_path"] for row in bindings))
        if graph_damage == "schema":
            with sqlite3.connect(path / "graph.sqlite3") as db: db.execute("DROP TABLE quality")
        raw_graph = (path / "graph.sqlite3").read_bytes()
        derived = [dict(relative_path=name, raw_sha256=sha256((path / name).read_bytes()), size_bytes=(path / name).stat().st_size)
                   for name in ("inputs/callgraph.ndjson", "inputs/scanner-coverage.json")]
        manifest = build_manifest(source, dict(asdict(receipt), relative_path="graph.sqlite3", raw_sha256=sha256(raw_graph),
                                              sqlite_version=sqlite3.sqlite_version, quality="unavailable"), derived)
        (path / "manifest.json").write_bytes(manifest)
        # Owned fixture construction sets the private contract; production never repairs it.
        for child in path.rglob("*"): child.chmod(0o700 if child.is_dir() else 0o600)
        snapshot = SnapshotRef(PROJECT, sha256(manifest), sha256(manifest))
        catalog = SnapshotCatalogEntry(snapshot, sha256(source), sha256(raw_graph), "generations/" + path.name,
                                       1, datetime.now(timezone.utc).isoformat())
        with state.transaction(owner, write=True) as tx:
            tx.commit_publication(expected_head=tx.get_project_head(), catalog=catalog,
                layers=(SnapshotLayer("base", 0, "base", None, "unresolved", "unknown"),), operation_id=str(uuid4()))
        copied = len(manifest) + len(raw_graph) + sum(map(len, contents.values())) + sum(row["size_bytes"] for row in derived)
        resident = len(manifest) + sum(map(len, contents.values())) + 2 * len(raw_graph)
        options = dict(state=state, principal=principal, snapshot=snapshot, graph_reader_factory=RentgenGraphReaderFactory(),
            limits=backend.PosixSnapshotLimits(copied_byte_budget=copied, resident_byte_budget=resident),
            graph_limits=VerifiedGraphLimits(image_buffer_budget=2 * len(raw_graph)), authorize_read=lambda: None)
        return SimpleNamespace(root=root, path=path, state=state, owner=owner, principal=principal,
            snapshot=snapshot, catalog=catalog, contents=contents, manifest=manifest,
            copied=copied, resident=resident, options=options)
    return build


@pytest.fixture
def generation(make_generation):
    return make_generation()


def opened(generation, **changes):
    return backend.open_posix_snapshot_session(**(generation.options | changes))


def module_ref(session):
    return next(entry.ref for entry in session.entries() if entry.ref.relative_path == MODULE)


def closed(session, directories, db):
    assert session._phase == "closed" and not session._buffers and not session._directories
    assert session._manifest is session._document is session._authorize_read is None
    assert session._reader is session._graph_context is session._stack is None
    for cap in directories:
        assert cap._closed
        with pytest.raises(OSError) as error: os.fstat(cap._fd)
        assert error.value.errno == errno.EBADF
    if db is not None:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"): db.execute("SELECT 1")


def test_complete_internal_read_uses_copied_sources_manifest_and_one_sqlite_image(generation, monkeypatch):
    connect = sqlite3.connect; connections = []
    def traced(name, *args, **kwargs):
        connections.append(str(name))
        assert name == ":memory:" or str(name).startswith(generation.state.path.as_uri() + "?mode=rw")
        return connect(name, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", traced)
    with opened(generation) as session:
        directories = list(session._directories.values()); db = session._reader._owner._db
        assert session.manifest_bytes() == generation.manifest
        assert len(session.entries()) == 3
        ref = module_ref(session)
        assert session.read_source(ref) == generation.contents[MODULE]
        # After entry all retained content IO is finished; queries cannot reopen it.
        monkeypatch.setattr(retained.Directory, "file", lambda *a, **k: pytest.fail("Read reopened a retained pathname"))
        assert session.resolve_module(ref)["graph_modules"]
        assert session.module_impact(ref, max_depth=5, max_edges=600)
        with pytest.raises(CoreError): session.validation_summary
    closed(session, directories, db)
    summary = session.validation_summary
    assert summary["verified_source_files"] == 3 and summary["verified_derived_files"] == 2
    assert summary["verified_total_bytes"] == generation.copied
    assert summary["resident_image_accounting"] == generation.resident
    assert summary["expected_bytes_protected"] == "private_verified_copies"
    assert connections.count(":memory:") == 1
    with pytest.raises(CoreError): session.read_source(ref)
    with pytest.raises(CoreError): session.__enter__()


@pytest.mark.parametrize("artifact", ["manifest.json", "graph.sqlite3", "inputs/callgraph.ndjson", "sources/base/" + MODULE])
def test_every_artifact_hash_is_bound_to_catalog(generation, artifact):
    path = generation.path / artifact
    raw = path.read_bytes(); path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
    with pytest.raises(CoreError, match="match"):
        with opened(generation): pytest.fail("Corrupt artifact admitted")


def test_matching_catalog_hash_does_not_bypass_real_sqlite_schema_validation(make_generation):
    generation = make_generation(graph_damage="schema")
    session = opened(generation)
    with pytest.raises(CoreError, match="schema"):
        with session: pytest.fail("Damaged SQLite graph admitted")
    assert session._phase == "closed" and not session._buffers


@pytest.mark.parametrize("extra", ["graph.sqlite3-wal", "graph.sqlite3-shm", "graph.sqlite3-journal", "unknown", "build-work/secret"])
def test_inventory_rejects_unlisted_content_before_source_or_graph_io(generation, monkeypatch, extra):
    (generation.path / extra).write_bytes(b"unlisted")
    reads = []; original = retained.Directory.file
    @contextmanager
    def observed(cap, name):
        reads.append(name)
        with original(cap, name) as stream: yield stream
    monkeypatch.setattr(retained.Directory, "file", observed)
    with pytest.raises(CoreError):
        with opened(generation): pytest.fail("Unlisted generation content admitted")
    assert reads == ["manifest.json"]


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "directory", "mode"])
def test_source_leaf_aliases_special_objects_and_public_mode_are_rejected(generation, kind):
    leaf = generation.path / "sources/base" / MODULE
    leaf.unlink()
    target = generation.root / "foreign"; target.write_bytes(generation.contents[MODULE]); target.chmod(0o600)
    if kind == "symlink": leaf.symlink_to(target)
    elif kind == "hardlink": os.link(target, leaf)
    elif kind == "fifo": os.mkfifo(leaf)
    elif kind == "directory": leaf.mkdir(mode=0o700)
    else: leaf.write_bytes(generation.contents[MODULE]); leaf.chmod(0o644)
    with pytest.raises((CoreError, OSError)):
        with opened(generation): pytest.fail("Unsafe source leaf admitted")
    assert target.read_bytes() == generation.contents[MODULE]


@pytest.mark.parametrize("directory", ["root", "generations", "generation", "sources/base", "inputs"])
def test_every_private_directory_is_checked_without_permission_repair(generation, directory):
    path = {"root": generation.root, "generations": generation.path.parent, "generation": generation.path}.get(directory, generation.path / directory)
    path.chmod(0o755)
    with pytest.raises(CoreError, match="permissions"):
        with opened(generation): pytest.fail("Public retained directory admitted")
    assert path.stat().st_mode & 0o777 == 0o755


def test_copies_survive_original_replacement_but_exit_refuses_changed_namespace(generation):
    session = opened(generation)
    with pytest.raises(CoreError, match="changed"):
        with session:
            ref = module_ref(session); directories = list(session._directories.values()); db = session._reader._owner._db
            graph = session.resolve_module(ref)
            (generation.path / "sources/base" / MODULE).write_bytes(b"modified")
            (generation.path / "graph.sqlite3").write_bytes(b"foreign graph")
            assert session.read_source(ref) == generation.contents[MODULE]
            assert session.resolve_module(ref) == graph
    closed(session, directories, db)
    with pytest.raises(CoreError): session.validation_summary


def test_real_namespace_replacement_refuses_exit_and_preserves_body_cause(generation):
    failure = CoreError("PROJECT_FORBIDDEN", "Trusted body denial"); cause = ValueError("original cause")
    session = opened(generation)
    with pytest.raises(CoreError) as error:
        with session:
            directories = list(session._directories.values()); db = session._reader._owner._db
            generation.path.rename(generation.path.with_name("moved"))
            generation.path.mkdir(mode=0o700)
            raise failure from cause
    assert error.value is failure and error.value.__cause__ is cause
    closed(session, directories, db)


def test_real_source_change_during_descriptor_copy_is_rejected(generation, monkeypatch):
    original = retained.Directory.file
    @contextmanager
    def changed(cap, name):
        with original(cap, name) as stream:
            yield stream
            if name == "Module.bsl":
                leaf = generation.path / "sources/base" / MODULE
                leaf.write_bytes(b"x" * len(generation.contents[MODULE]))
    monkeypatch.setattr(retained.Directory, "file", changed)
    session = opened(generation)
    with pytest.raises(CoreError, match="changed"):
        with session: pytest.fail("Concurrent descriptor bytes admitted")
    assert session._phase == "closed" and not session._buffers


@pytest.mark.parametrize("budget", ["copied_byte_budget", "resident_byte_budget"])
def test_aggregate_budget_refuses_before_source_or_graph_copy(generation, monkeypatch, budget):
    limits = replace(generation.options["limits"], **{budget: getattr(generation.options["limits"], budget) - 1})
    copies = []; original = backend._PosixSnapshotSession._copy
    def observed(session, relative, *args, **kwargs):
        copies.append(relative)
        return original(session, relative, *args, **kwargs)
    monkeypatch.setattr(backend._PosixSnapshotSession, "_copy", observed)
    with pytest.raises(CoreError) as error:
        with opened(generation, limits=limits): pytest.fail("Over-budget allocation admitted")
    assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED" and copies == ["manifest.json"]


@pytest.mark.parametrize("field,value", [("max_retained_descriptors", 1), ("max_relative_components", 1), ("max_source_entries", 1), ("max_inventory_items", 1)])
def test_fd_depth_source_and_inventory_budgets_fail_closed(generation, field, value):
    session = opened(generation, limits=replace(generation.options["limits"], **{field: value}))
    with pytest.raises(CoreError):
        with session: pytest.fail("Resource budget ignored")
    assert session._phase == "closed" and not session._directories and not session._buffers


@pytest.mark.parametrize("field,value", [("copied_byte_budget", True), ("resident_byte_budget", 4*1024**3+1), ("deadline_seconds", 31)])
def test_limits_are_explicit_typed_and_bounded(field, value):
    options = dict(copied_byte_budget=1, resident_byte_budget=1, **{field: value}) if field == "deadline_seconds" else {"copied_byte_budget": 1, "resident_byte_budget": 1} | {field: value}
    with pytest.raises(CoreError): backend.PosixSnapshotLimits(**options)


@pytest.mark.parametrize("operation", ["entries", "manifest", "source", "graph"])
def test_current_membership_revocation_closes_before_disclosure(generation, operation):
    session = opened(generation)
    with session:
        ref = module_ref(session); directories = list(session._directories.values()); db = session._reader._owner._db
        with generation.state.transaction(generation.owner, write=True) as tx: revoke_membership(tx, generation.principal)
        call = {"entries": session.entries, "manifest": session.manifest_bytes,
                "source": lambda: session.read_source(ref), "graph": lambda: session.resolve_module(ref)}[operation]
        with pytest.raises(CoreError) as error: call()
        assert error.value.code == "PROJECT_FORBIDDEN"
        closed(session, directories, db)


def test_revocation_after_real_graph_query_prevents_outer_disclosure(generation, monkeypatch):
    with opened(generation) as session:
        ref = module_ref(session); original = session._reader.resolve_module
        def revoked(ref):
            result = original(ref)
            with generation.state.transaction(generation.owner, write=True) as tx: revoke_membership(tx, generation.principal)
            return result
        monkeypatch.setattr(session._reader, "resolve_module", revoked)
        with pytest.raises(CoreError) as error: session.resolve_module(ref)
        assert error.value.code == "PROJECT_FORBIDDEN" and session._phase == "closed"
        traceback = error.value.__traceback__
        while traceback:
            if traceback.tb_frame.f_code.co_name == "_call":
                assert traceback.tb_frame.f_locals["result"] is None
            traceback = traceback.tb_next


def test_retained_copy_denial_traceback_does_not_keep_undisclosed_byte_image(generation, monkeypatch):
    armed = [False]; denial = CoreError("PROJECT_FORBIDDEN", "Denied after real descriptor copy")
    def authorize():
        if armed[0]: raise denial
    original = retained.Directory.file
    @contextmanager
    def arm_after_copy(cap, name):
        with original(cap, name) as stream:
            yield stream
        if name == "Module.bsl": armed[0] = True
    monkeypatch.setattr(retained.Directory, "file", arm_after_copy)
    session = opened(generation, authorize_read=authorize)
    with pytest.raises(CoreError) as error:
        with session: pytest.fail("Denied byte image disclosed")
    assert error.value is denial and not session._buffers and session._manifest is None
    traceback = error.value.__traceback__; found = False
    while traceback:
        if traceback.tb_frame.f_code.co_name == "_copy":
            assert traceback.tb_frame.f_locals["raw"] is None
            found = True
        traceback = traceback.tb_next
    assert found


def test_catalog_change_is_detected_even_with_same_snapshot_identity(generation):
    with opened(generation) as session:
        # Deliberately corrupt fixture state; this is not a publication operation.
        with sqlite3.connect(generation.state.path) as db:
            db.execute("UPDATE snapshots SET graph_hash=?", ("f"*64,))
        with pytest.raises(CoreError, match="catalog binding changed"): session.entries()
        assert session._phase == "closed"


@pytest.mark.parametrize("column", ["source_digest", "graph_hash"])
def test_initial_catalog_content_binding_is_required_before_artifact_copy(generation, monkeypatch, column):
    # Deliberately corrupt fixture metadata before entry; no fake publication claim.
    with sqlite3.connect(generation.state.path) as db:
        db.execute("UPDATE snapshots SET " + column + "=?", ("f"*64,))
    copies = []; original = backend._PosixSnapshotSession._copy
    def observed(session, relative, *args, **kwargs):
        copies.append(relative)
        return original(session, relative, *args, **kwargs)
    monkeypatch.setattr(backend._PosixSnapshotSession, "_copy", observed)
    with pytest.raises(CoreError, match="Catalog content binding"):
        with opened(generation): pytest.fail("Unbound catalog admitted")
    assert copies == ["manifest.json"]


def test_legacy_graph_factory_cannot_fall_back_to_original_path(generation):
    class Legacy:
        def open(self, **options): pytest.fail("POSIX graph fell back to retained pathname")
    session = opened(generation, graph_reader_factory=Legacy())
    with pytest.raises(CoreError) as error:
        with session: pytest.fail("Path-only graph factory admitted")
    assert error.value.code == "GRAPH_ADAPTER_UNAVAILABLE"
    assert session._phase == "closed" and not session._buffers and not session._directories


def test_new_process_can_reopen_exact_catalog_generation_without_live_sources(generation):
    with opened(generation) as session:
        ref = module_ref(session)
        expected = sha256(session.read_source(ref))
    script = '''
import hashlib, json, pathlib, sys
from rentgen_core._posix_snapshot_session import open_posix_snapshot_session, PosixSnapshotLimits
from rentgen_core._verified_graph import VerifiedGraphLimits
from rentgen_core.context import Principal, SnapshotRef
from rentgen_core.state import ProjectState
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory
state_path, project, snapshot, copied, resident, image = sys.argv[1:]
with open_posix_snapshot_session(state=ProjectState(pathlib.Path(state_path), project),
    principal=Principal("reader", "local_os"), snapshot=SnapshotRef(project, snapshot, snapshot),
    graph_reader_factory=RentgenGraphReaderFactory(),
    limits=PosixSnapshotLimits(copied_byte_budget=int(copied), resident_byte_budget=int(resident)),
    graph_limits=VerifiedGraphLimits(image_buffer_budget=int(image)), authorize_read=lambda: None) as session:
    ref = next(entry.ref for entry in session.entries() if "/Caller/" in entry.ref.relative_path)
    result = {"sha256": hashlib.sha256(session.read_source(ref)).hexdigest(),
              "graph_modules": bool(session.resolve_module(ref)["graph_modules"])}
print(json.dumps(result))
'''
    result = subprocess.run([sys.executable, "-c", script, str(generation.state.path), PROJECT,
        generation.snapshot.snapshot_id, str(generation.copied), str(generation.resident),
        str(generation.options["graph_limits"].image_buffer_budget)], cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(result.stdout) == {"sha256": expected, "graph_modules": True}


@pytest.mark.parametrize("change", ["hash", "snapshot", "spelling"])
def test_source_ref_requires_exact_snapshot_spelling_and_hash(generation, change):
    with opened(generation) as session:
        ref = module_ref(session)
        if change == "hash": ref = replace(ref, raw_sha256="f"*64)
        elif change == "snapshot": ref = replace(ref, snapshot=SnapshotRef(PROJECT, "f"*64, "f"*64))
        else: ref = replace(ref, relative_path=ref.relative_path.lower())
        with pytest.raises(CoreError): session.read_source(ref)
        assert session._phase == "closed"


def test_foreign_public_thread_query_and_exit_leave_owner_final_close_available(generation):
    session = opened(generation)
    with session:
        directories = list(session._directories.values()); db = session._reader._owner._db; errors = []
        def foreign():
            for operation in (session.entries, lambda: session.__exit__(None, None, None)):
                try: operation()
                except CoreError as error: errors.append(error.code)
        thread = Thread(target=foreign); thread.start(); thread.join(timeout=5)
        assert not thread.is_alive() and errors == ["SNAPSHOT_READ_SESSION_INVALID"] * 2
        assert session.read_source(module_ref(session)) == generation.contents[MODULE]
    closed(session, directories, db)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="Actual POSIX fork ownership guard")
def test_forked_public_context_cannot_query_or_consume_parent_close(generation):
    session = opened(generation)
    with session:
        directories = list(session._directories.values()); db = session._reader._owner._db
        read_fd, write_fd = os.pipe(); pid = os.fork()
        if pid == 0:
            os.close(read_fd); results = []
            for operation in (session.entries, lambda: session.__exit__(None, None, None)):
                try: operation(); results.append("unexpected success")
                except CoreError as error: results.append(error.code)
            results.append(session._phase)
            os.write(write_fd, ",".join(results).encode()); os.close(write_fd); os._exit(0)
        os.close(write_fd)
        try: result = os.read(read_fd, 256)
        finally: os.close(read_fd); status = os.waitpid(pid, 0)[1]
        assert status == 0 and result == b"SNAPSHOT_READ_SESSION_INVALID,SNAPSHOT_READ_SESSION_INVALID,active"
        assert session.resolve_module(module_ref(session))["graph_modules"]
    closed(session, directories, db)


@pytest.mark.parametrize("phase", ["entry", "query", "exit"])
def test_reentrant_public_access_and_exit_never_consume_owner_context(generation, phase):
    armed = [phase == "entry"]; refusals = []
    def authorize():
        if armed[0]:
            for operation in (session.entries, lambda: session.__exit__(None, None, None)):
                with pytest.raises(CoreError) as error: operation()
                assert error.value.code == "SNAPSHOT_READ_SESSION_INVALID"
                refusals.append(error.value)
    session = opened(generation, authorize_read=authorize)
    with session:
        directories = list(session._directories.values()); db = session._reader._owner._db
        armed[0] = phase == "query"
        assert session.resolve_module(module_ref(session))["graph_modules"]
        armed[0] = phase == "exit"
    assert refusals
    closed(session, directories, db)


@pytest.mark.parametrize("phase", ["entry", "query", "exit"])
def test_cooperative_deadline_includes_entry_operation_and_exit(generation, monkeypatch, phase):
    now = [100]; monkeypatch.setattr(backend, "monotonic", lambda: now[0])
    def authorize():
        if phase == "entry": now[0] += 30
    session = opened(generation, authorize_read=authorize)
    with pytest.raises(CoreError) as error:
        with session:
            directories = list(session._directories.values()); db = session._reader._owner._db
            now[0] += 30
            if phase == "query": session.entries()
    assert error.value.code == "SNAPSHOT_READ_DEADLINE_EXCEEDED"
    assert session._phase == "closed" and not session._buffers
    if phase != "entry": closed(session, directories, db)


def test_callback_primary_exception_and_cause_survive_namespace_cleanup_failure(generation):
    armed = [False]; failure = ValueError("trusted callback denied"); cause = OSError("original cause")
    def authorize():
        if armed[0]:
            generation.path.rename(generation.path.with_name("moved"))
            raise failure from cause
    with opened(generation, authorize_read=authorize) as session:
        directories = list(session._directories.values()); db = session._reader._owner._db
        armed[0] = True
        with pytest.raises(ValueError) as error: session.entries()
        assert error.value is failure and error.value.__cause__ is cause
        closed(session, directories, db)


def test_success_cannot_hide_real_close_ack_failure(generation, monkeypatch):
    session = opened(generation); real_close = os.close; attempts = []
    with pytest.raises(OSError, match="close acknowledgement"):
        with session:
            target = session._directories[""]._fd
            directories = list(session._directories.values()); db = session._reader._owner._db
            def lost(fd):
                real_close(fd)
                if fd == target:
                    attempts.append(fd)
                    raise OSError(errno.EIO, "close acknowledgement lost")
            monkeypatch.setattr(os, "close", lost)
    assert attempts == [target]
    closed(session, directories, db)
    with pytest.raises(CoreError): session.validation_summary


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual Darwin retained-subtree ACL")
def test_nested_private_acl_is_not_inherited_as_an_unchecked_assumption(generation):
    import pwd
    account = pwd.getpwuid(os.geteuid()).pw_name
    subprocess.run(["/bin/chmod", "+a", f"user:{account} allow read", str(generation.path / "inputs")], check=True)
    with pytest.raises(CoreError, match="ACL"):
        with opened(generation): pytest.fail("Private subtree ACL admitted")


@pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux retained-subtree default ACL")
def test_linux_nested_default_acl_is_rejected_with_mode_0700(generation):
    import struct
    undefined = 0xFFFFFFFF
    entries = [(1, 7, undefined), (2, 4, os.geteuid()), (4, 0, undefined), (16, 0, undefined), (32, 0, undefined)]
    acl = struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *entry) for entry in entries)
    fd = os.open(generation.path / "inputs", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.setxattr(fd, "system.posix_acl_default", acl)
        assert os.fstat(fd).st_mode & 0o777 == 0o700
    finally: os.close(fd)
    with pytest.raises(CoreError, match="ACL"):
        with opened(generation): pytest.fail("Private default ACL admitted")
