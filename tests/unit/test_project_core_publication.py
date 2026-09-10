import shutil
"""Publication protocol uses only owned public fixtures and real SQLite state."""
from project_access_test_support import grant_membership
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

import rentgen_core as api

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows capture contract")


@pytest.fixture(scope="session")
def scanner(tmp_path_factory):
    executable = tmp_path_factory.mktemp("publication-scanner") / "bsl-scan.exe"
    subprocess.run(
        [
            shutil.which("go") or "go",
            "build",
            "-buildvcs=false",
            "-o",
            str(executable),
            "./cmd/bsl-scan",
        ],
        cwd=ROOT / "go",
        check=True,
        capture_output=True,
    )
    return executable


@pytest.fixture
def project(tmp_path, scanner):
    from rentgen_graph.snapshot_adapter import (
        RentgenCapturedGoBuilder,
        RentgenGraphReaderFactory,
    )

    owner = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    module = source / "CommonModules" / "ОбщийМодуль" / "Ext" / "Module.bsl"
    module.parent.mkdir(parents=True)
    module.write_bytes(
        "Функция Значение() Экспорт\r\nВозврат 1;\r\nКонецФункции\r\n".encode()
    )
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    registered = registry.register(
        owner, source_root=source, state_root=tmp_path / "state", display_name="A"
    )
    assert hasattr(api, "capture_and_publish"), "Publication API is missing"
    resolver = api.ContextResolver(
        registry, graph_reader_factory=RentgenGraphReaderFactory()
    )
    ctx = resolver.resolve_context(owner, api.Explicit(registered.project_id))
    return ctx, resolver, module, RentgenCapturedGoBuilder(scanner)


def publish(project, **kwargs):
    ctx, _, _, builder = project
    return api.capture_and_publish(
        ctx,
        expected_head=api.get_project_head(ctx),
        builder=builder,
        operation_id=str(uuid4()),
        **kwargs
    )


def test_real_publication_pins_sources_graph_and_receipt(project):
    ctx, resolver, module, _ = project
    raw = module.read_bytes()
    result = publish(project)
    selected = resolver.resolve_context(ctx.principal, api.Explicit(ctx.project_id))
    assert selected.snapshot == result.snapshot
    ref = selected.sources.resolve("base", "CommonModules/ОбщийМодуль/Ext/Module.bsl")
    assert selected.sources.read_source(ref) == raw
    envelope = selected.graph.resolve_module(ref)
    assert envelope["snapshot_id"] == result.snapshot.snapshot_id
    assert envelope["capabilities"]["quality"] == "unavailable"
    assert envelope["result"]
    assert selected.graph.impact(ref)["snapshot_id"] == result.snapshot.snapshot_id
    assert api.get_publication(ctx, result.operation_id) == result
    module.unlink()
    assert selected.sources.read_source(ref) == raw
    assert selected.graph.resolve_module(ref) == envelope


def test_exact_operation_replay_after_later_head_and_changed_configuration(project):
    ctx, _, module, builder = project
    before = api.get_project_head(ctx)
    first = publish(project)
    module.write_bytes(module.read_bytes().replace(b"1", b"3"))
    second = publish(project)
    assert second.snapshot != first.snapshot
    api.configure_source_layers(
        ctx, api.get_source_configuration(ctx).layers, expected_revision=1
    )
    assert (
        api.capture_and_publish(
            ctx, expected_head=before, builder=None, operation_id=first.operation_id
        )
        == first
    )
    with pytest.raises(api.CoreError) as error:
        api.capture_and_publish(
            ctx,
            expected_head=second.head,
            builder=builder,
            operation_id=first.operation_id,
        )
    assert error.value.code == "OPERATION_CONFLICT"


@pytest.mark.parametrize(
    "point", ["before_complete", "after_complete", "before_commit"]
)
def test_failure_boundaries_never_publish_or_promote_orphans(
    project, monkeypatch, point
):
    import rentgen_core.publication as publication

    ctx, resolver, _, _ = project
    before = api.get_project_head(ctx)
    operation = str(uuid4())
    seen = []

    def fault(name, **values):
        if name == point:
            seen.append(values["catalog"].snapshot)
            raise RuntimeError("injected boundary")

    monkeypatch.setattr(publication, "_boundary", fault)
    with pytest.raises(RuntimeError, match="injected"):
        api.capture_and_publish(
            ctx, expected_head=before, builder=project[3], operation_id=operation
        )
    assert api.get_project_head(ctx) == before
    with pytest.raises(api.CoreError) as error:
        api.get_publication(ctx, operation)
    assert error.value.code == "PUBLICATION_NOT_FOUND"
    with pytest.raises(api.CoreError) as error:
        resolver.resolve_context(
            ctx.principal, api.Explicit(ctx.project_id), seen[0].snapshot_id
        )
    assert error.value.code == "SNAPSHOT_NOT_FOUND"
    with ctx.state.transaction(ctx.principal) as tx:
        for table in (
            "snapshots",
            "publication_receipts",
            "snapshot_events",
            "snapshot_outbox",
        ):
            assert (
                tx._connection.execute("SELECT count(*) FROM " + table).fetchone()[0]
                == 0
            )


def test_lost_ack_after_later_publication_returns_exact_original_receipt(
    project, monkeypatch
):
    import rentgen_core.publication as publication

    ctx, _, module, _ = project
    operation = str(uuid4())
    seen = []

    def fault(name, **values):
        if name == "after_commit" and not seen:
            seen.append(values["catalog"].snapshot)
            module.write_bytes(module.read_bytes().replace(b"1", b"9"))
            publish(project)
            raise RuntimeError("ack lost")

    monkeypatch.setattr(publication, "_boundary", fault)
    result = api.capture_and_publish(
        ctx,
        expected_head=api.get_project_head(ctx),
        builder=project[3],
        operation_id=operation,
    )
    assert result.snapshot == seen[0]
    assert api.get_project_head(ctx).snapshot != result.snapshot
    assert api.get_publication(ctx, operation) == result


@pytest.mark.parametrize(
    "change,code",
    [
        ("permission", "PROJECT_FORBIDDEN"),
        ("configuration", "SOURCE_CONFIGURATION_CONFLICT"),
        ("head", "HEAD_CONFLICT"),
    ],
)
def test_changes_during_build_rechecked_in_publication_transaction(
    project, monkeypatch, change, code
):
    import rentgen_core.publication as publication

    ctx = project[0]
    operation = str(uuid4())
    entered = []

    def fault(name, **values):
        if name != "after_capture" or entered:
            return
        entered.append(True)
        if change == "permission":
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                grant_membership(tx, ctx.principal, {"project:read", "project:admin"})
        elif change == "configuration":
            api.configure_source_layers(
                ctx, api.get_source_configuration(ctx).layers, expected_revision=1
            )
        else:
            publish(project)

    monkeypatch.setattr(publication, "_boundary", fault)
    with pytest.raises(api.CoreError) as error:
        api.capture_and_publish(
            ctx,
            expected_head=api.get_project_head(ctx),
            builder=project[3],
            operation_id=operation,
        )
    assert error.value.code == code
    with pytest.raises(api.CoreError) as error:
        api.get_publication(ctx, operation)
    assert error.value.code == "PUBLICATION_NOT_FOUND"


def test_graph_build_uses_sealed_bytes_after_live_mutation(project, monkeypatch):
    import rentgen_core.publication as publication

    ctx, resolver, module, _ = project
    raw = module.read_bytes()

    def fault(name, **values):
        if name == "after_capture":
            module.write_bytes(b"live tree changed completely")

    monkeypatch.setattr(publication, "_boundary", fault)
    result = publish(project)
    pinned = resolver.resolve_context(
        ctx.principal, api.Explicit(ctx.project_id), result.snapshot.snapshot_id
    )
    ref = pinned.sources.list_entries().entries[0].ref
    assert pinned.sources.read_source(ref) == raw
    assert (
        pinned.graph.resolve_module(ref)["capabilities"]["temporal_atomicity"]
        == "not_proven"
    )


def test_aba_expected_revision_rejected_even_when_content_returns(project):
    ctx, _, module, builder = project
    first = publish(project)
    original = module.read_bytes()
    module.write_bytes(original.replace(b"1", b"2"))
    publish(project)
    module.write_bytes(original)
    again = publish(project)
    assert first.snapshot == again.snapshot
    with pytest.raises(api.CoreError) as error:
        api.capture_and_publish(
            ctx, expected_head=first.head, builder=builder, operation_id=str(uuid4())
        )
    assert error.value.code == "HEAD_CONFLICT"
    assert again.head.revision == 3


def test_unreadable_receipt_after_commit_reports_unknown_without_false_success(
    project, monkeypatch
):
    import rentgen_core.publication as publication
    from rentgen_core.authorization import StateTransaction

    ctx = project[0]
    operation = str(uuid4())
    original = StateTransaction._find_publication
    failed = []

    def lookup(self, value):
        if failed:
            raise api.CoreError("STATE_BUSY", "injected unreadable state")
        return original(self, value)

    def fault(name, **values):
        if name == "after_commit":
            failed.append(True)
            raise RuntimeError("ack lost")

    monkeypatch.setattr(StateTransaction, "_find_publication", lookup)
    monkeypatch.setattr(publication, "_boundary", fault)
    with pytest.raises(api.CoreError) as error:
        api.capture_and_publish(
            ctx,
            expected_head=api.get_project_head(ctx),
            builder=project[3],
            operation_id=operation,
        )
    assert error.value.code == "PUBLICATION_OUTCOME_UNKNOWN"
    assert error.value.details == {"operation_id": operation}
    failed.clear()
    assert api.get_publication(ctx, operation).head.revision == 1


def test_precommit_retry_uses_new_attempt_and_identical_content_reuses_catalog(
    project, monkeypatch
):
    import rentgen_core.publication as publication

    ctx = project[0]
    operation = str(uuid4())
    head = api.get_project_head(ctx)
    attempts = []

    def fault(name, **values):
        if name == "after_capture":
            attempts.append(values["captured"].staging_path)
        if name == "before_complete":
            raise RuntimeError("failed first attempt")

    with monkeypatch.context() as patch:
        patch.setattr(publication, "_boundary", fault)
        with pytest.raises(RuntimeError):
            api.capture_and_publish(
                ctx, expected_head=head, builder=project[3], operation_id=operation
            )
    result = api.capture_and_publish(
        ctx, expected_head=head, builder=project[3], operation_id=operation
    )
    with ctx.state.transaction(ctx.principal) as tx:
        catalog = tx.get_snapshot(result.snapshot.snapshot_id)
    actual = ctx.state.path.parent / catalog.generation_relpath
    assert actual != attempts[0]
    assert actual.name != result.snapshot.snapshot_id and actual.name != operation
    assert attempts[0].exists()
    again = publish(project)
    assert again.snapshot == result.snapshot and again.head.revision == 2
    with ctx.state.transaction(ctx.principal) as tx:
        assert tx.get_snapshot(result.snapshot.snapshot_id) == catalog
        assert (
            tx._connection.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 1
        )
        assert (
            tx._connection.execute(
                "SELECT count(*) FROM publication_receipts"
            ).fetchone()[0]
            == 2
        )


def test_candidate_pin_cleanup_error_after_commit_reconciles_receipt(
    project, monkeypatch
):
    from contextlib import contextmanager
    import rentgen_core.capture as capture

    original = capture._capture_generation

    @contextmanager
    def fail_close(*args, **kwargs):
        with original(*args, **kwargs) as captured:
            yield captured
        raise OSError("injected pin close acknowledgment error")

    monkeypatch.setattr(capture, "_capture_generation", fail_close)
    result = publish(project)
    assert api.get_publication(project[0], result.operation_id) == result


@pytest.mark.parametrize(
    "damage",
    [
        "meta_only",
        "missing_module_column",
        "wrong_count",
        "wrong_module_path",
        "missing_constraints",
    ],
)
def test_invalid_graph_schema_or_counts_cannot_be_published(project, damage):
    import sqlite3
    from contextlib import closing

    ctx, _, _, real = project

    class DamagedBuilder:
        def build(self, captured, *, output_path, work_dir):
            receipt = real.build(captured, output_path=output_path, work_dir=work_dir)
            with closing(sqlite3.connect(output_path)) as db:
                if damage == "meta_only":
                    tables = db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name<>'meta'"
                    ).fetchall()
                    for (name,) in tables:
                        db.execute('DROP TABLE "' + name + '"')
                elif damage == "missing_module_column":
                    db.execute(
                        "ALTER TABLE module RENAME COLUMN source_path TO broken_path"
                    )
                elif damage == "wrong_module_path":
                    db.execute("UPDATE module SET source_path='base/Foreign.bsl'")
                elif damage == "missing_constraints":
                    db.execute("CREATE TABLE invalid_edges AS SELECT * FROM call_edge")
                    db.execute("DROP TABLE call_edge")
                    db.execute("ALTER TABLE invalid_edges RENAME TO call_edge")
                else:
                    db.execute("UPDATE meta SET value='999999' WHERE key='n_modules'")
                db.commit()
            return receipt

    before = api.get_project_head(ctx)
    with pytest.raises(api.CoreError) as error:
        api.capture_and_publish(
            ctx,
            expected_head=before,
            builder=DamagedBuilder(),
            operation_id=str(uuid4()),
        )
    assert error.value.code == "SNAPSHOT_CORRUPT"
    assert api.get_project_head(ctx) == before


def test_unlisted_builder_output_cannot_be_published(project):
    ctx, _, _, real = project

    class ExtraOutputBuilder:
        def build(self, captured, *, output_path, work_dir):
            receipt = real.build(captured, output_path=output_path, work_dir=work_dir)
            (work_dir / "mutable-builder-status.json").write_bytes(
                b'{"state":"inprogress"}'
            )
            return receipt

    before = api.get_project_head(ctx)
    with pytest.raises(api.CoreError) as error:
        api.capture_and_publish(
            ctx,
            expected_head=before,
            builder=ExtraOutputBuilder(),
            operation_id=str(uuid4()),
        )
    assert error.value.code == "SNAPSHOT_CORRUPT"
    assert api.get_project_head(ctx) == before


def test_same_content_catalog_insert_race_fails_head_without_hashing_under_write(
    project, monkeypatch
):
    from contextlib import contextmanager
    import rentgen_core.publication as publication

    ctx = project[0]
    original_transaction = api.ProjectState.transaction
    original_verify = publication.verify_generation
    writes, entered = [], []

    @contextmanager
    def tracked_transaction(self, principal, *, write=False):
        with original_transaction(self, principal, write=write) as tx:
            if write:
                writes.append(True)
            try:
                yield tx
            finally:
                if write:
                    writes.pop()

    def verify(*args, **kwargs):
        assert not writes, "Filesystem verification must stay outside state write UOW"
        return original_verify(*args, **kwargs)

    def fault(name, **values):
        if name == "before_state_transaction" and not entered:
            entered.append(True)
            publish(project)

    monkeypatch.setattr(api.ProjectState, "transaction", tracked_transaction)
    monkeypatch.setattr(publication, "verify_generation", verify)
    monkeypatch.setattr(publication, "_boundary", fault)
    with pytest.raises(api.CoreError) as error:
        publish(project)
    assert error.value.code == "HEAD_CONFLICT"
    assert api.get_project_head(ctx).revision == 1


def test_catalog_disappearing_without_head_change_is_state_corrupt(
    project, monkeypatch
):
    import rentgen_core.publication as publication
    from rentgen_core.authorization import StateTransaction

    first = publish(project)
    original = StateTransaction.get_snapshot
    entered = []

    def hidden_catalog(self, snapshot_id):
        if entered and self._write:
            raise api.CoreError(
                "SNAPSHOT_NOT_FOUND", "injected missing authoritative row"
            )
        return original(self, snapshot_id)

    def fault(name, **values):
        if name == "before_state_transaction":
            entered.append(True)

    monkeypatch.setattr(StateTransaction, "get_snapshot", hidden_catalog)
    monkeypatch.setattr(publication, "_boundary", fault)
    with pytest.raises(api.CoreError) as error:
        publish(project)
    assert error.value.code == "STATE_CORRUPT"
    assert api.get_project_head(project[0]) == first.head
