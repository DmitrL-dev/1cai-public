"""Native Linux process route; separate actual POSIX storage/CAS controls on Mac."""
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from uuid import uuid4

import pytest

from project_access_test_support import revoke_membership
from rentgen_core import _linux_capture as subject
from rentgen_core import _posix_source_tree as retained
from rentgen_core.authorization import StateTransaction
from rentgen_core.context import ProjectContext
from rentgen_core.errors import CoreError
from rentgen_core.source_configuration import SourceLayerSpec
from rentgen_core.state import ProjectState
from test_posix_generation import BSL, PROJECT, project, capture, bundle, generation, seal

ROOT = Path(__file__).resolve().parents[2]
posix = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Actual POSIX generated proof and publication SQLite controls")
native = pytest.mark.skipif(sys.platform != "linux" or platform.machine() not in {"x86_64", "amd64"}, reason="Actual Linux/amd64 full owned-scanner capture")


def context(project):
    return ProjectContext(PROJECT, project.worker, str(uuid4()), project.state, project.source)


def proof(project, *, authorize=lambda: None, cancelled=lambda: False):
    """Real F2/generation/SQLite proof, constructed scanner bytes; not Linux process."""
    ctx = context(project)
    with ctx.state.transaction(ctx.principal) as tx: project.head = tx.get_project_head()
    limits = subject.LinuxCaptureLimits()
    gate = subject._CaptureGate(ctx, project.head, limits, authorize, cancelled)
    gate.check()
    with capture(project) as captured:
        configuration = captured._configuration
        graph = bundle(captured); owner = generation(project, captured)
        with owner: seal(owner, graph)
        complete = owner.result
    return ctx, complete, configuration, gate, limits


def commit(prepared, operation=None):
    ctx, complete, configuration, gate, limits = prepared
    return subject._commit_complete(ctx, complete, configuration=configuration,
        operation_id=str(uuid4()) if operation is None else operation, limits=limits, gate=gate)


def counts(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        return {table: tx._connection.execute("SELECT count(*) FROM " + table).fetchone()[0]
                for table in ("snapshots", "publication_receipts", "snapshot_events", "snapshot_outbox")}


@posix
def test_storage_only_actual_generated_proof_commits_atomic_catalog_head_receipt(project):
    prepared = proof(project); ctx, complete, configuration, gate, limits = prepared
    result = commit(prepared)
    assert result.snapshot == complete.snapshot and result.head.revision == complete.expected_head.revision + 1
    assert counts(ctx) == dict(snapshots=1, publication_receipts=1, snapshot_events=1, snapshot_outbox=1)
    with ctx.state.transaction(ctx.principal) as tx:
        assert tx.get_snapshot(result.snapshot.snapshot_id) == complete.catalog
        assert tx.get_snapshot_layers(result.snapshot.snapshot_id) == complete.layers
        assert tx.get_project_head() == result.head
        assert tx.get_publication(result.operation_id) == result


@posix
def test_receipt_replay_bypasses_source_scanner_and_old_head_configuration(project, monkeypatch):
    prepared = proof(project); first = commit(prepared)
    (project.source / BSL).write_bytes(b"Procedure Run() Export\nReturn 2;\nEndProcedure\n")
    later = commit(proof(project)); assert later.snapshot != first.snapshot
    ctx = prepared[0]
    with ctx.state.transaction(project.owner, write=True) as tx:
        tx.configure_source_layers((SourceLayerSpec("base",0,"base",".","unknown"),), expected_revision=1, source_root=project.source)
    replay_ctx = replace(ctx, source_root=project.source / "does-not-exist")
    monkeypatch.setattr(subject, "_capture_complete", lambda *a: pytest.fail("Replay recaptured source"))
    monkeypatch.setattr(subject, "open_linux_scanner", lambda **k: pytest.fail("Replay launched scanner"))
    result = subject.LinuxCaptureBackend().capture(replay_ctx,
        expected_head=prepared[1].expected_head, operation_id=first.operation_id,
        authorize_capture=lambda: pytest.fail("Replay rechecked stale operation"),
        cancelled=lambda: pytest.fail("Replay resumed cancelled operation"))
    assert result == first


@posix
def test_replay_requires_current_analysis_permission_and_exact_operation_inputs(project):
    prepared = proof(project); first = commit(prepared); ctx = prepared[0]
    backend = subject.LinuxCaptureBackend()
    with pytest.raises(CoreError) as mismatch:
        backend.capture(ctx, expected_head=replace(prepared[1].expected_head, revision=99), operation_id=first.operation_id)
    assert mismatch.value.code == "OPERATION_CONFLICT"
    with ctx.state.transaction(project.owner, write=True) as tx: revoke_membership(tx, project.worker)
    with pytest.raises(CoreError) as forbidden:
        backend.capture(ctx, expected_head=prepared[1].expected_head, operation_id=first.operation_id)
    assert forbidden.value.code == "PROJECT_FORBIDDEN"


@posix
@pytest.mark.parametrize("where", ["before_state_transaction", "before_commit"])
def test_storage_precommit_failure_leaves_whole_state_empty_and_complete_orphan(project, monkeypatch, where):
    prepared = proof(project); ctx, complete, *_ = prepared
    def fault(name, **values):
        if name == where: raise RuntimeError("precommit denial")
    monkeypatch.setattr(subject, "_boundary", fault)
    with pytest.raises(RuntimeError, match="precommit denial"): commit(prepared)
    assert counts(ctx) == dict(snapshots=0, publication_receipts=0, snapshot_events=0, snapshot_outbox=0)
    with ctx.state.transaction(ctx.principal) as tx: assert tx.get_project_head() == complete.expected_head
    assert (project.state_root / complete.catalog.generation_relpath / "manifest.json").is_file()


@posix
def test_storage_lost_ack_reconciles_exact_receipt_after_later_commit_and_expiry(project, monkeypatch):
    prepared = proof(project); first_operation = str(uuid4()); completed = []
    def fault(name, **values):
        if name == "after_commit" and not completed:
            completed.append(True)
            (project.source / BSL).write_bytes(b"Procedure Run() Export\nReturn 2;\nEndProcedure\n")
            later = commit(proof(project)); completed.append(later)
            prepared[3].deadline = -1
            raise RuntimeError("ack lost")
    monkeypatch.setattr(subject, "_boundary", fault)
    result = commit(prepared, first_operation)
    assert result.operation_id == first_operation and result.snapshot == prepared[1].snapshot
    assert result.snapshot != completed[1].snapshot
    with prepared[0].state.transaction(prepared[0].principal) as tx:
        assert tx.get_project_head() == completed[1].head and tx.get_publication(first_operation) == result


@posix
def test_storage_ack_failure_with_unreadable_receipt_reports_unknown(project, monkeypatch):
    prepared = proof(project); original = StateTransaction._find_publication; committed = []
    def read(self, operation):
        if committed: raise OSError("receipt unreadable")
        return original(self, operation)
    def fault(name, **values):
        if name == "after_commit": committed.append(True); raise RuntimeError("ack lost")
    monkeypatch.setattr(StateTransaction, "_find_publication", read)
    monkeypatch.setattr(subject, "_boundary", fault)
    with pytest.raises(CoreError) as caught: commit(prepared)
    assert caught.value.code == "PUBLICATION_OUTCOME_UNKNOWN"
    assert counts(prepared[0])["snapshots"] == 1


@posix
def test_storage_same_content_dedup_verifies_existing_locator_outside_write_tx(project, monkeypatch):
    first = proof(project); published = commit(first)
    second = proof(project); seen = []; writes = []; transaction = ProjectState.transaction; opener = retained.Directory.file
    @contextmanager
    def tracked(state, principal, *, write=False):
        with transaction(state, principal, write=write) as tx:
            if write: writes.append(True)
            try: yield tx
            finally:
                if write: writes.pop()
    def read(directory, name):
        assert not writes, "Generation reads happened under state write transaction"
        seen.append((directory._chain[-1][2],name))
        return opener(directory,name)
    monkeypatch.setattr(ProjectState,"transaction",tracked)
    monkeypatch.setattr(retained.Directory,"file",read)
    again = commit(second)
    assert again.snapshot == published.snapshot and again.head.revision == published.head.revision + 1
    with second[0].state.transaction(second[0].principal) as tx:
        catalog = tx.get_snapshot(again.snapshot.snapshot_id)
    assert catalog.generation_relpath == first[1].catalog.generation_relpath
    assert catalog.generation_relpath != second[1].catalog.generation_relpath
    assert any(name == "manifest.json" for _, name in seen)
    assert counts(second[0]) == dict(snapshots=1, publication_receipts=2, snapshot_events=2, snapshot_outbox=2)


@posix
def test_storage_corrupt_existing_locator_refuses_dedup_reuse(project):
    first = proof(project); commit(first); second = proof(project)
    leaf = project.state_root / first[1].catalog.generation_relpath / "sources/base" / BSL
    leaf.write_bytes(b"X"*leaf.stat().st_size)
    with pytest.raises(CoreError): commit(second)
    assert counts(second[0])["publication_receipts"] == 1


@posix
def test_storage_changed_verified_catalog_row_is_rejected_in_short_cas(project, monkeypatch):
    first = proof(project); commit(first); second = proof(project)
    get_snapshot = StateTransaction.get_snapshot; armed = []
    def hidden(self, snapshot_id):
        if armed and self._write: raise CoreError("SNAPSHOT_NOT_FOUND", "injected missing row")
        return get_snapshot(self,snapshot_id)
    def fault(name, **values):
        if name == "before_state_transaction": armed.append(True)
    monkeypatch.setattr(StateTransaction,"get_snapshot",hidden)
    monkeypatch.setattr(subject,"_boundary",fault)
    with pytest.raises(CoreError) as caught: commit(second)
    assert caught.value.code == "STATE_CORRUPT"
    assert counts(second[0])["publication_receipts"] == 1


@posix
def test_storage_actual_dedup_session_must_verify_the_selected_catalog_locator(project, monkeypatch):
    first = proof(project); commit(first); second = proof(project)
    opener = subject.open_posix_snapshot_session; lookup = StateTransaction.get_snapshot
    alternate = second[1].catalog; reading = []
    def substituted(self,snapshot_id):
        if reading and not self._write: return alternate
        return lookup(self,snapshot_id)
    @contextmanager
    def read_alternate(**options):
        reading.append(True)
        try:
            with opener(**options) as session: yield session
        finally: reading.pop()
    monkeypatch.setattr(StateTransaction,"get_snapshot",substituted)
    monkeypatch.setattr(subject,"open_posix_snapshot_session",read_alternate)
    with pytest.raises(CoreError) as caught: commit(second)
    assert caught.value.code == "STATE_CORRUPT"
    assert counts(second[0])["publication_receipts"] == 1


@posix
@pytest.mark.parametrize("same_operation",[False,True])
def test_storage_racing_publication_replays_exact_operation_or_refuses_old_head(project,monkeypatch,same_operation):
    prepared = proof(project); operation = str(uuid4()); entered=[]; raced=[]
    def fault(name,**values):
        if name == "before_state_transaction" and not entered:
            entered.append(True)
            raced.append(commit(proof(project), operation if same_operation else None))
    monkeypatch.setattr(subject,"_boundary",fault)
    if same_operation:
        result=commit(prepared,operation); assert result == raced[0]
    else:
        with pytest.raises(CoreError) as caught: commit(prepared,operation)
        assert caught.value.code == "HEAD_CONFLICT"
    assert counts(prepared[0])["publication_receipts"] == 1


@posix
def test_storage_callbacks_and_generation_reads_stay_outside_short_write_uow(project,monkeypatch):
    writes=[]; transaction=ProjectState.transaction
    def no_write(): assert not writes,"Arbitrary capture callback ran under write transaction"
    prepared=proof(project,authorize=no_write,cancelled=lambda:(no_write() or False))
    @contextmanager
    def tracked(state,principal,*,write=False):
        with transaction(state,principal,write=write) as tx:
            if write: writes.append(True)
            try: yield tx
            finally:
                if write:writes.pop()
    monkeypatch.setattr(ProjectState,"transaction",tracked)
    result=commit(prepared)
    assert result.snapshot == prepared[1].snapshot


@posix
def test_storage_insert_catalog_content_mismatch_guard_is_preserved(project):
    first = proof(project); commit(first); second = proof(project)
    forged = replace(second[1], catalog=replace(second[1].catalog,graph_hash="f"*64))
    with pytest.raises(CoreError) as caught: commit((second[0],forged,*second[2:]))
    assert caught.value.code == "SNAPSHOT_CORRUPT"


@posix
@pytest.mark.parametrize("change,code", [("permission","PROJECT_FORBIDDEN"), ("configuration","SOURCE_CONFIGURATION_CONFLICT"), ("head","HEAD_CONFLICT")])
def test_storage_current_cas_authority_head_and_entire_configuration_required(project, monkeypatch, change, code):
    prepared = proof(project)
    def fault(name, **values):
        if name != "before_state_transaction": return
        with project.state.transaction(project.owner,write=True) as tx:
            if change == "permission": revoke_membership(tx,project.worker)
            elif change == "configuration":
                # Deliberate same-revision corruption fixture checks root paths,
                # beyond the ordinal/id/kind/format subset in commit_publication.
                tx._connection.execute("UPDATE source_layers SET root_relative_path='other' WHERE project_id=?",(PROJECT,))
            else: tx._connection.execute("UPDATE project_head SET revision=revision+1 WHERE project_id=?",(PROJECT,))
    monkeypatch.setattr(subject,"_boundary",fault)
    with pytest.raises(CoreError) as caught: commit(prepared)
    assert caught.value.code == code
    with project.state.transaction(project.owner) as tx:
        assert tx._connection.execute("SELECT count(*) FROM publication_receipts").fetchone()[0] == 0


@posix
def test_storage_cancel_and_deadline_before_commit_roll_back_without_receipt(project, monkeypatch):
    prepared = proof(project)
    def fault(name, **values):
        if name == "before_commit": prepared[3].deadline = -1
    monkeypatch.setattr(subject,"_boundary",fault)
    with pytest.raises(CoreError) as caught: commit(prepared)
    assert caught.value.code == "SOURCE_READ_DEADLINE_EXCEEDED" and counts(prepared[0])["snapshots"] == 0


@posix
def test_orchestration_uses_entered_scanner_and_preserves_denial_cleanup(project, monkeypatch):
    """Real POSIX owners plus a constructed scanner denial; no Linux execution."""
    denied = CoreError("GRAPH_SCANNER_CANCELLED", "Controlled entered-owner denial")
    lifecycle = []

    class EnteredScanner:
        def scan(self):
            lifecycle.append("scan")
            raise denied

    @contextmanager
    def observing_scanner(**options):
        options["scan_directory"].verify()
        lifecycle.append("enter")
        try:
            yield EnteredScanner()
        finally:
            lifecycle.append("exit")

    monkeypatch.setattr(subject, "open_linux_scanner", observing_scanner)
    ctx = context(project)
    backend = subject.LinuxCaptureBackend(project.source / "unused-scanner", "0" * 64)
    gate = subject._CaptureGate(ctx, project.head, backend.limits, lambda: None, lambda: False)
    with pytest.raises(CoreError) as caught:
        subject._capture_complete(backend, ctx, project.head, gate)
    assert caught.value is denied
    assert lifecycle == ["enter", "scan", "exit"]
    assert counts(ctx) == dict(snapshots=0, publication_receipts=0, snapshot_events=0, snapshot_outbox=0)
    assert list((project.state_root / "staging").iterdir())
    assert list((project.state_root / "generations").iterdir())


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual Mac full Linux capture refusal")
def test_actual_mac_full_capture_refuses_without_source_or_executable_io(project, monkeypatch):
    backend = subject.LinuxCaptureBackend(project.source / "absent-scanner", "0"*64)
    monkeypatch.setattr(subject,"_capture_complete",lambda *a: pytest.fail("Unsupported Mac attempted native capture"))
    with pytest.raises(CoreError) as caught:
        backend.capture(context(project),expected_head=project.head,operation_id=str(uuid4()))
    assert caught.value.code == "CAPTURE_PLATFORM_UNSUPPORTED"


@pytest.mark.parametrize("field,value", [("resident_byte_budget",True), ("max_source_entries",20_001), ("operation_deadline_seconds",121), ("phase_deadline_seconds",31), ("max_vm_steps",1.5)])
def test_limits_are_typed_and_bounded(field,value):
    with pytest.raises(CoreError): replace(subject.LinuxCaptureLimits(),**{field:value})


@pytest.mark.parametrize("executable,digest", [(Path("relative"),"0"*64), (Path("/tmp/tool"),None), (None,"0"*64), ("/tmp/tool","0"*64), (Path("/tmp/../tool"),"0"*64), (Path("/tmp/tool"),"G"*64)])
def test_backend_rejects_unbound_scanner_without_io(executable,digest):
    with pytest.raises(CoreError): subject.LinuxCaptureBackend(executable,digest)


def test_backend_is_immutable_and_replay_can_omit_scanner():
    backend = subject.LinuxCaptureBackend()
    assert backend.scanner_executable is backend.scanner_sha256 is None
    with pytest.raises(FrozenInstanceError): backend.scanner_sha256 = "0"*64


@pytest.fixture(scope="module")
def scanner(tmp_path_factory):
    if sys.platform != "linux" or platform.machine() not in {"x86_64","amd64"}:
        pytest.skip("Actual Linux/amd64 full capture scanner")
    configured = os.environ.get("RENTGEN_TEST_LINUX_SCANNER")
    if configured:
        executable = Path(configured)
        assert executable.is_absolute() and executable.is_file(), "RENTGEN_TEST_LINUX_SCANNER must be an absolute actual executable"
    else:
        go = shutil.which("go"); assert go, "Actual Linux capture qualification requires the pinned Go toolchain"
        executable = tmp_path_factory.mktemp("linux-capture-bin") / "bsl-scan"
        subprocess.run([go,"build","-trimpath","-o",str(executable),"./cmd/bsl-scan"],
            cwd=ROOT/"go",env={**os.environ,"CGO_ENABLED":"0"},check=True,timeout=120)
        executable.chmod(0o700)
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    expected = os.environ.get("RENTGEN_TEST_LINUX_SCANNER_SHA256")
    if expected: assert digest == expected
    return subject.LinuxCaptureBackend(executable,digest)


@native
def test_native_linux_actual_owned_go_full_capture_and_exact_receipt_replay(project, scanner):
    ctx = context(project); operation = str(uuid4())
    result = scanner.capture(ctx,expected_head=project.head,operation_id=operation)
    assert result.head.revision == project.head.revision + 1
    assert counts(ctx) == dict(snapshots=1,publication_receipts=1,snapshot_events=1,snapshot_outbox=1)
    with ctx.state.transaction(ctx.principal) as tx:
        catalog = tx.get_snapshot(result.snapshot.snapshot_id)
        assert tx.get_publication(operation) == result
    root = project.state_root / catalog.generation_relpath
    assert (root/"sources/base"/BSL).read_bytes() == project.images[BSL]
    assert (root/"sources/base/binary.bin").read_bytes() == project.images["binary.bin"]
    assert not (root/"source-manifest.json").exists() and not (root/"build-work").exists()
    assert subject.LinuxCaptureBackend().capture(replace(ctx,source_root=project.source/"absent"),
        expected_head=project.head,operation_id=operation) == result


@native
def test_native_linux_wrong_scanner_hash_and_cancel_never_commit(project, scanner):
    ctx = context(project)
    wrong = replace(scanner,scanner_sha256="0"*64)
    with pytest.raises(CoreError) as caught: wrong.capture(ctx,expected_head=project.head,operation_id=str(uuid4()))
    assert caught.value.code == "GRAPH_SCANNER_EXECUTABLE_INVALID"
    with pytest.raises(CoreError) as cancelled:
        scanner.capture(ctx,expected_head=project.head,operation_id=str(uuid4()),cancelled=lambda:True)
    assert cancelled.value.code == "GRAPH_SCANNER_CANCELLED" and counts(ctx)["snapshots"] == 0


@native
def test_native_linux_cancellation_after_real_hello_reaps_process_without_publication(project,scanner,monkeypatch):
    opened=subject.open_linux_scanner; running=[]; cancellation=[False]
    @contextmanager
    def observe_real_scanner(**options):
        with opened(**options) as owner:
            running.append(owner)
            cancellation[0]=True
            yield owner
    monkeypatch.setattr(subject,"open_linux_scanner",observe_real_scanner)
    ctx=context(project)
    with pytest.raises(CoreError) as caught:
        scanner.capture(ctx,expected_head=project.head,operation_id=str(uuid4()),cancelled=lambda:cancellation[0])
    assert caught.value.code == "GRAPH_SCANNER_CANCELLED" and len(running)==1
    owner=running[0]
    assert owner._process.poll() is not None and owner._phase == "closed"
    assert not owner._streams and owner._selector is None
    assert counts(ctx) == dict(snapshots=0,publication_receipts=0,snapshot_events=0,snapshot_outbox=0)
    assert list((project.state_root/"staging").iterdir()) and list((project.state_root/"generations").iterdir())


@native
def test_native_linux_new_capture_requires_owned_scanner_after_receipt_lookup(project):
    with pytest.raises(CoreError) as caught:
        subject.LinuxCaptureBackend().capture(context(project),expected_head=project.head,operation_id=str(uuid4()))
    assert caught.value.code == "GRAPH_ADAPTER_UNAVAILABLE" and not (project.state_root/"staging").exists()
