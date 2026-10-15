"""Constructed scanner buffers + real SQLite; not real Linux process acceptance."""
from dataclasses import asdict, FrozenInstanceError, replace
import builtins
import json
import sqlite3
from threading import Thread

import pytest

from rentgen_core._linux_scanner import LinuxScannerOutput
from rentgen_core._verified_graph import VerifiedGraphLimits
from rentgen_core.context import SnapshotRef
from rentgen_core.errors import CoreError
from rentgen_core.graph import open_verified_graph
from rentgen_core.manifests import CapturedInput, build_manifest, build_source_document, canonical_bytes, sha256
from rentgen_core.source_configuration import SourceConfiguration, SourceLayerSpec
from rentgen_graph import posix_snapshot_adapter as subject
from rentgen_graph import build_store
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

PROJECT = "11111111-1111-4111-8111-111111111111"
CALLER = "base/CommonModules/Caller/Ext/Module.bsl"
CALLEE = "base/CommonModules/Callee/Ext/Module.bsl"


class CopiedInputs:
    """Immutable test images; this fixture does not claim capture provenance."""
    project_id = PROJECT

    def __init__(self, images):
        self.images = dict(images)
        self.entries = tuple(CapturedInput("base", path.removeprefix("base/"),
            sha256(raw), len(raw), "utf-8" if path.endswith(".bsl") else None)
            for path, raw in sorted(images.items()))
        self.source_document = build_source_document(PROJECT,
            SourceConfiguration(1, (SourceLayerSpec("base", 0, "base", ".", "unknown"),)), (), self.entries)
        self.source_digest = sha256(self.source_document)
        self.reads = []

    def read_bytes(self, entry):
        assert entry in self.entries
        path = entry.layer_id + "/" + entry.relative_path
        self.reads.append(path)
        return self.images[path]


@pytest.fixture
def inputs():
    captured = CopiedInputs({
        CALLER: b"Procedure Caller() Export\nCallee.Target();\nEndProcedure\n",
        CALLEE: b"Procedure Target() Export\nReturn;\nEndProcedure\n",
        "base/readme.bin": b"\xff\0",
    })
    records = [dict(name="Caller", module="Caller", source_path=CALLER,
        line=1, end_line=3, is_export=True, is_function=False, complexity=1,
        calls=["Callee.Target"], call_sites=[dict(target="Callee.Target", kind="qualified",
            line=2, column=1, end_line=2, end_column=14)]),
        dict(name="Target", module="Callee", source_path=CALLEE, line=1, end_line=3,
            is_export=True, is_function=False, complexity=1, calls=[], call_sites=[])]
    coverage = dict(format_version=1, files=[dict(source_path=path,
        raw_sha256=sha256(captured.images[path]), status="parsed", routine_count=1)
        for path in (CALLER, CALLEE)])
    output = LinuxScannerOutput(b"\n".join(canonical_bytes(record) for record in records) + b"\n",
        canonical_bytes(coverage), "a" * 64)
    limits = subject.PosixGraphLimits(image_buffer_budget=256 * 1024**2)
    return captured, output, limits


def build(inputs, *, authorize=lambda: None, limits=None, output=None):
    captured, original, defaults = inputs
    return subject.build_posix_graph_bundle(captured, original if output is None else output,
        limits=defaults if limits is None else limits, authorize=authorize)


def manifest(captured, bundle):
    document = build_manifest(captured.source_document,
        dict(asdict(bundle.receipt), relative_path="graph.sqlite3", raw_sha256=sha256(bundle.graph_bytes),
            sqlite_version=bundle.sqlite_version, quality="unavailable"),
        [dict(relative_path=name, raw_sha256=sha256(raw), size_bytes=len(raw)) for name, raw in
            (("inputs/callgraph.ndjson", bundle.ndjson), ("inputs/scanner-coverage.json", bundle.coverage))])
    return document, SnapshotRef(PROJECT, sha256(document), sha256(document))


def test_actual_serialized_graph_supports_verified_reader_without_path_or_process(inputs, monkeypatch):
    connections = []
    connect = sqlite3.connect
    def memory_only(name, *args, **kwargs):
        assert name == ":memory:", "Owned graph reopened a filesystem path"
        db = connect(name, *args, **kwargs)
        connections.append(db)
        return db
    monkeypatch.setattr(subject.sqlite3, "connect", memory_only)
    monkeypatch.setattr(builtins, "open", lambda *a, **k: pytest.fail("Graph opened a filesystem path"))
    bundle = build(inputs)
    assert type(bundle.graph_bytes) is type(bundle.ndjson) is type(bundle.coverage) is bytes
    assert len(connections) == 2
    assert set(inputs[0].reads) == {CALLER, CALLEE}
    for db in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            db.execute("SELECT 1")
    document, snapshot = manifest(inputs[0], bundle)
    with open_verified_graph(RentgenGraphReaderFactory(), graph_bytes=bundle.graph_bytes,
            manifest_bytes=document, snapshot=snapshot, authorize_read=lambda: None,
            limits=VerifiedGraphLimits(image_buffer_budget=2 * len(bundle.graph_bytes))) as reader:
        resolution = reader.resolve_module(CALLER)
        assert [row["source_path"] for row in resolution["graph_modules"]] == [CALLER]
        impact = reader.module_impact(CALLEE, max_depth=5, max_edges=600)
        assert impact["entry_subroutines"] == 1 and impact["total"] == 1
        assert impact["complete"] is True
    assert len(connections) == 3
    with pytest.raises(FrozenInstanceError):
        bundle.graph_bytes = b"changed"


def test_output_is_deterministic_and_bound_to_exact_scanner_and_sources(inputs):
    first, second = build(inputs), build(inputs)
    assert first == second
    assert first.receipt.source_digest == inputs[0].source_digest
    assert first.receipt.adapter_version == "rentgen-captured-owned-go-v1"
    assert first.receipt.scanner_version == inputs[1].protocol + ";sha256=" + inputs[1].executable_sha256
    assert first.graph_bytes[18:20] == b"\1\1"
    assert first.resident_image_accounting <= inputs[2].image_buffer_budget


def test_manifest_rejects_unknown_adapter_without_rejecting_old_adapter_contract(inputs):
    bundle = build(inputs)
    document, _ = manifest(inputs[0], bundle)
    from rentgen_core.manifests import parse_manifest
    assert parse_manifest(document)["graph"]["adapter_version"] == subject.ADAPTER_VERSION
    old = replace(bundle, receipt=replace(bundle.receipt, adapter_version="rentgen-captured-go-v1"))
    assert parse_manifest(manifest(inputs[0], old)[0])["graph"]["adapter_version"] == "rentgen-captured-go-v1"
    unknown = replace(bundle, receipt=replace(bundle.receipt, adapter_version="unknown-adapter"))
    with pytest.raises(CoreError, match="Unsupported captured graph adapter"):
        manifest(inputs[0], unknown)


@pytest.mark.parametrize("field,value", [
    ("image_buffer_budget", True), ("max_graph_bytes", 0), ("max_vm_steps", 1.5),
    ("deadline_seconds", 31), ("max_files", 20_001), ("max_records", -1),
])
def test_typed_limits_reject_bool_fraction_and_out_of_contract_values(inputs, field, value):
    with pytest.raises(CoreError) as error:
        replace(inputs[2], **{field: value})
    assert error.value.code == "INVALID_QUERY_OPTIONS"


@pytest.mark.parametrize("change", ["type", "mutable", "protocol", "hash", "source_hash", "encoding", "coverage", "span", "duplicate"])
def test_unbound_or_invalid_input_is_rejected_before_any_graph_connection(inputs, monkeypatch, change):
    captured, output, _ = inputs
    if change == "type": output = asdict(output)
    elif change == "mutable": output = replace(output, ndjson=bytearray(output.ndjson))
    elif change == "protocol": output = replace(output, protocol="other")
    elif change == "hash": output = replace(output, executable_sha256="A" * 64)
    elif change == "source_hash": captured.images[CALLER] = b"different"
    elif change == "encoding": captured.entries = tuple(replace(e, encoding=None) if e.relative_path.endswith(".bsl") else e for e in captured.entries)
    elif change == "coverage": output = replace(output, coverage=b'{"format_version":1,"files":[]}')
    elif change == "span":
        records = [json.loads(line) for line in output.ndjson.splitlines()]
        records[0]["end_line"] = 999
        output = replace(output, ndjson=b"\n".join(canonical_bytes(r) for r in records) + b"\n")
    else: captured.entries += (captured.entries[0],)
    monkeypatch.setattr(subject.sqlite3, "connect", lambda *a, **k: pytest.fail("Invalid input reached SQLite"))
    with pytest.raises(CoreError):
        build(inputs, output=output)


@pytest.mark.parametrize("field,value", [
    ("max_source_bytes", 1), ("max_scanner_output_bytes", 1),
    ("image_buffer_budget", 1), ("max_files", 1), ("max_records", 1),
    ("max_record_bytes", 1),
])
def test_large_image_and_input_budgets_fail_before_connection(inputs, monkeypatch, field, value):
    monkeypatch.setattr(subject.sqlite3, "connect", lambda *a, **k: pytest.fail("Budget denial reached SQLite"))
    with pytest.raises(CoreError) as error:
        build(inputs, limits=replace(inputs[2], **{field: value}))
    assert error.value.code == "GRAPH_BUILD_LIMIT_EXCEEDED"


def test_actual_sqlite_page_limit_prevents_unbounded_database(inputs):
    with pytest.raises(CoreError) as error:
        build(inputs, limits=replace(inputs[2], max_graph_bytes=4096))
    assert error.value.code == "GRAPH_BUILD_LIMIT_EXCEEDED"


def test_vm_step_limit_interrupts_actual_sqlite_and_closes_its_connection(inputs, monkeypatch):
    connections = []
    connect = sqlite3.connect
    def tracked(*args, **kwargs):
        db = connect(*args, **kwargs); connections.append(db); return db
    monkeypatch.setattr(subject.sqlite3, "connect", tracked)
    with pytest.raises(CoreError) as error:
        build(inputs, limits=replace(inputs[2], max_vm_steps=1))
    assert error.value.code == "GRAPH_BUILD_LIMIT_EXCEEDED"
    assert connections
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connections[0].execute("SELECT 1")


def test_cumulative_vm_budget_covers_many_individually_short_native_statements(inputs, monkeypatch):
    populate = subject._populate_store
    def many_short(db, *args, **kwargs):
        for _ in range(2000):
            db.execute("SELECT 1").fetchone()
        return populate(db, *args, **kwargs)
    monkeypatch.setattr(subject, "_populate_store", many_short)
    with pytest.raises(CoreError) as error:
        build(inputs, limits=replace(inputs[2], max_vm_steps=2000))
    assert error.value.code == "GRAPH_BUILD_LIMIT_EXCEEDED"


def test_initial_authorization_denial_precedes_source_disclosure_and_sqlite(inputs, monkeypatch):
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked")
    def deny(): raise denial
    monkeypatch.setattr(subject.sqlite3, "connect", lambda *a, **k: pytest.fail("Denied build opened SQLite"))
    with pytest.raises(CoreError) as error: build(inputs, authorize=deny)
    assert error.value is denial and inputs[0].reads == []


def test_authorization_denial_inside_actual_sqlite_progress_preserves_original(inputs, monkeypatch):
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked during native SQL")
    original = subject._Build._progress
    def denied_progress(owner):
        owner._authorize = lambda: (_ for _ in ()).throw(denial)
        return original(owner)
    connection = subject._Build._connection
    def frequent_progress(owner, **kwargs):
        owner._quantum = 1
        return connection(owner, **kwargs)
    monkeypatch.setattr(subject._Build, "_connection", frequent_progress)
    monkeypatch.setattr(subject._Build, "_progress", denied_progress)
    with pytest.raises(CoreError) as error: build(inputs)
    assert error.value is denial


def test_revocation_after_serialized_validation_prevents_bundle_disclosure(inputs, monkeypatch):
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked before disclosure")
    original = subject._verify_graph_digest
    revoked = False
    def validate(*args):
        nonlocal revoked
        original(*args); revoked = True
    def authorize():
        if revoked: raise denial
    monkeypatch.setattr(subject, "_verify_graph_digest", validate)
    with pytest.raises(CoreError) as error: build(inputs, authorize=authorize)
    assert error.value is denial


def test_deadline_denial_before_source_disclosure_and_sqlite(inputs, monkeypatch):
    clock = iter((0, 31))
    monkeypatch.setattr(subject, "monotonic", lambda: next(clock))
    with pytest.raises(CoreError) as error: build(inputs)
    assert error.value.code == "GRAPH_BUILD_DEADLINE_EXCEEDED" and inputs[0].reads == []


def test_foreign_thread_cannot_advance_build_or_disclose_sources(inputs):
    owner = subject._Build(inputs[0], inputs[1], inputs[2], lambda: None)
    errors = []
    def foreign():
        try: owner.run()
        except BaseException as exc: errors.append(exc)
    thread = Thread(target=foreign); thread.start(); thread.join()
    assert len(errors) == 1 and errors[0].code == "GRAPH_BUILD_SESSION_INVALID"
    assert inputs[0].reads == []
    assert owner._phase == "active" and owner.run().graph_bytes


def test_independent_serialized_validator_is_required_before_bundle_disclosure(inputs, monkeypatch):
    # The separate validator must run, rather than trusting successful population.
    monkeypatch.setattr(subject, "_validate_graph_structure", lambda *a: (_ for _ in ()).throw(
        CoreError("SNAPSHOT_CORRUPT", "Independent validator rejected graph")))
    with pytest.raises(CoreError) as error: build(inputs)
    assert error.value.code == "SNAPSHOT_CORRUPT"


def test_actual_serialized_schema_damage_is_rejected_even_with_intact_header(inputs, monkeypatch):
    connect = sqlite3.connect
    class Damaged(sqlite3.Connection):
        def serialize(self, *args, **kwargs):
            # A valid but wrong schema image cannot qualify as a graph.
            self.execute("DROP TABLE quality")
            self.commit()
            return super().serialize(*args, **kwargs)
    def tracked(name, *args, **kwargs):
        return connect(name, *args, factory=Damaged, **kwargs)
    monkeypatch.setattr(subject.sqlite3, "connect", tracked)
    with pytest.raises(CoreError) as error: build(inputs)
    assert error.value.code in {"SNAPSHOT_CORRUPT", "GRAPH_INPUT_MISMATCH"}


def test_reentrant_authorization_callback_cannot_advance_or_close_outer_build(inputs):
    errors = []
    owner = None
    def authorize():
        try: owner.run()
        except CoreError as exc: errors.append(exc.code)
    owner = subject._Build(inputs[0], inputs[1], inputs[2], authorize)
    assert owner.run().graph_bytes and errors
    assert set(errors) == {"GRAPH_BUILD_SESSION_INVALID"}


def test_owned_records_seam_refuses_legacy_and_path_input_combinations():
    with sqlite3.connect(":memory:") as db:
        with pytest.raises(ValueError, match="Owned records"):
            build_store._populate_store(db, 0, 0, _records=iter(()))
        with pytest.raises(ValueError, match="Owned records"):
            build_store._populate_store(db, 0, 0, mode=build_store.BuildMode.SNAPSHOT,
                inputs=build_store.BuildInputs(build_store.NDJSON, None), _records=iter(()))


def test_successful_connection_close_failure_prevents_bundle_disclosure(inputs, monkeypatch):
    failure = OSError("Owned connection close failed")
    connect = sqlite3.connect
    class RefuseClose(sqlite3.Connection):
        def close(self):
            super().close()
            raise failure
    monkeypatch.setattr(subject.sqlite3, "connect", lambda *a, **k: connect(*a, factory=RefuseClose, **k))
    with pytest.raises(OSError) as error: build(inputs)
    assert error.value is failure


def test_primary_sqlite_budget_failure_survives_cleanup_failure(inputs, monkeypatch):
    connect = sqlite3.connect
    class RefuseClose(sqlite3.Connection):
        def close(self):
            super().close()
            raise OSError("Secondary close failure")
    monkeypatch.setattr(subject.sqlite3, "connect", lambda *a, **k: connect(*a, factory=RefuseClose, **k))
    with pytest.raises(CoreError) as error:
        build(inputs, limits=replace(inputs[2], max_vm_steps=1))
    assert error.value.code == "GRAPH_BUILD_LIMIT_EXCEEDED"


def test_existing_legacy_path_builder_keeps_default_input_metadata_and_graph(tmp_path):
    path = tmp_path / "legacy.ndjson"
    path.write_bytes(canonical_bytes(dict(name="Run", module="Caller", line=1,
        complexity=1, calls=[])) + b"\n")
    database = tmp_path / "legacy.sqlite3"
    db = build_store._connect_fresh(database)
    try:
        meta, _ = build_store._populate_store(db, 0, 0,
            inputs=build_store.BuildInputs(path, None))
        assert meta["source_ndjson"] == str(path)
        assert meta["built_at_unix"] == "0" and meta["n_subroutines"] == "1"
        assert db.execute("SELECT name FROM module").fetchall() == [("legacy:caller",)]
        assert db.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    finally:
        db.close()


def owned_failure_frames(exception):
    pending, seen, frames = [exception], set(), []
    while pending:
        failure = pending.pop()
        if failure is None or id(failure) in seen:
            continue
        seen.add(id(failure))
        current = failure.__traceback__
        while current is not None:
            frame = current.tb_frame
            if frame.f_code.co_filename in {subject.__file__, build_store.__file__}:
                frames.append(frame)
            current = current.tb_next
        pending.extend((failure.__cause__, failure.__context__))
    return frames


def assert_denied_frame_images_released(exception):
    frames = owned_failure_frames(exception)
    assert frames
    for frame in frames:
        values = frame.f_locals
        for name in ("raw", "line", "lines", "output", "ndjson", "coverage", "graph", "result", "texts"):
            if name in values:
                assert values[name] is None, (frame.f_code.co_name, name)
        if frame.f_code.co_name == "build_posix_graph_bundle":
            assert values["captured"] is values["scanner_output"] is values["authorize"] is None
        if frame.f_code.co_name == "_populate_store":
            assert values == {}, "Failed private builder retained its input locals"


@pytest.mark.parametrize("after_reads", [1, 2])
def test_denial_after_actual_source_read_releases_raw_decoded_text_and_wrapper_inputs(inputs, monkeypatch, after_reads):
    captured = inputs[0]
    read = captured.read_bytes
    count = 0
    cause = OSError("Original authorization cause")
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked after source read")
    def read_then_revoke(entry):
        nonlocal count
        raw = read(entry)
        count += 1
        return raw
    def authorize():
        if count >= after_reads:
            raise denial from cause
    monkeypatch.setattr(captured, "read_bytes", read_then_revoke)
    with pytest.raises(CoreError) as error:
        build(inputs, authorize=authorize)
    assert error.value is denial and error.value.__cause__ is cause
    assert count == after_reads
    frames = owned_failure_frames(error.value)
    source_frame = next(frame for frame in frames if frame.f_code.co_name == "_inputs")
    assert "raw" in source_frame.f_locals and source_frame.f_locals["raw"] is None
    assert_denied_frame_images_released(error.value)


def test_denial_after_normalization_releases_undisclosed_derived_images(inputs, monkeypatch):
    validate = subject._validate_outputs
    revoked = False
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked after normalization")
    def normalize_then_revoke(*args):
        nonlocal revoked
        result = validate(*args)
        revoked = True
        return result
    def authorize():
        if revoked: raise denial
    monkeypatch.setattr(subject, "_validate_outputs", normalize_then_revoke)
    with pytest.raises(CoreError) as error: build(inputs, authorize=authorize)
    assert error.value is denial and revoked
    assert_denied_frame_images_released(error.value)


def test_denial_after_serialized_validation_releases_undisclosed_graph_image(inputs, monkeypatch):
    validate = subject._verify_graph_digest
    revoked = False
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked after graph validation")
    def validate_then_revoke(*args):
        nonlocal revoked
        validate(*args)
        revoked = True
    def authorize():
        if revoked: raise denial
    monkeypatch.setattr(subject, "_verify_graph_digest", validate_then_revoke)
    with pytest.raises(CoreError) as error: build(inputs, authorize=authorize)
    assert error.value is denial and revoked
    assert_denied_frame_images_released(error.value)


def test_native_sql_denial_releases_completed_builder_input_frame_and_record_generator(inputs, monkeypatch):
    revoked = False
    denial = CoreError("PROJECT_FORBIDDEN", "Revoked during staged input SQL")
    connect = sqlite3.connect
    def tracked(*args, **kwargs):
        db = connect(*args, **kwargs)
        def trace(statement):
            nonlocal revoked
            if "CREATE INDEX ix_sub_name_key" in statement:
                revoked = True
        db.set_trace_callback(trace)
        return db
    connection = subject._Build._connection
    def frequent(owner):
        owner._quantum = 1
        return connection(owner)
    def authorize():
        if revoked: raise denial
    monkeypatch.setattr(subject.sqlite3, "connect", tracked)
    monkeypatch.setattr(subject._Build, "_connection", frequent)
    with pytest.raises(CoreError) as error: build(inputs, authorize=authorize)
    assert error.value is denial and revoked
    frames = owned_failure_frames(error.value)
    assert any(frame.f_code.co_name == "_populate_store" for frame in frames)
    assert_denied_frame_images_released(error.value)
