"""Real POSIX files + F2 + owned SQLite; constructed scanner bytes, no OS admission."""
from dataclasses import FrozenInstanceError, replace
import errno
import os
from pathlib import Path
import stat
import subprocess
import sys
from threading import Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest

from project_access_test_support import grant_membership, revoke_membership
from rentgen_core import _posix_captured_sources as copied
from rentgen_core import _posix_generation as subject
from rentgen_core import _posix_source_tree as retained
from rentgen_core._linux_scanner import LinuxScannerOutput
from rentgen_core._posix_capture_candidate import PosixCandidateLimits, _PosixCaptureCandidate
from rentgen_core._posix_live_tree import PosixLiveLimits
from rentgen_core._verified_graph import VerifiedGraphLimits
from rentgen_core.context import Principal
from rentgen_core.errors import CoreError
from rentgen_core.manifests import canonical_bytes, parse_manifest, sha256
from rentgen_core.state import ProjectState
from rentgen_core.source_configuration import SourceLayerSpec
from rentgen_graph.posix_snapshot_adapter import PosixGraphLimits, build_posix_graph_bundle
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory

pytestmark = pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="Actual POSIX F2 and generation owner")
PROJECT = "11111111-1111-4111-8111-111111111111"
BSL = "CommonModules/Example/Ext/Module.bsl"


@pytest.fixture
def project(tmp_path):
    root = tmp_path.resolve(); source = root / "source"; source.mkdir()
    state_root = root / "state"; state_root.mkdir(mode=0o700)
    images = {BSL: b"Procedure Run() Export\nReturn;\nEndProcedure\n",
              "Configuration.xml": b"<Configuration/>", "binary.bin": b"\xff\0", "empty": b""}
    for name, raw in images.items():
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    owner, worker = Principal("owner", "local_os"), Principal("worker", "local_os")
    state = ProjectState.create(state_root / "state.sqlite3", PROJECT, owner)
    with state.transaction(owner, write=True) as tx:
        grant_membership(tx, worker, {"analysis:run", "project:read"})
    with state.transaction(worker) as tx: head = tx.get_project_head()
    return SimpleNamespace(source=source, state_root=state_root, state=state, owner=owner,
        worker=worker, head=head, images=images)


def capture(project, **changes):
    options = dict(state=project.state, principal=project.worker, source_root=project.source,
        expected_head=project.head, candidate_limits=PosixCandidateLimits(resident_byte_budget=4*1024**2),
        live_limits=PosixLiveLimits(), limits=copied.PosixCapturedLimits(resident_byte_budget=4*1024**2),
        authorize_capture=lambda: None)
    return copied.capture_posix_sources(**(options | changes))


def generation(project, captured, **changes):
    options = dict(state=project.state, principal=project.worker, expected_head=project.head,
        captured=captured, limits=subject.PosixGenerationLimits(resident_byte_budget=256*1024**2),
        authorize_capture=lambda: None)
    return subject.open_posix_generation(**(options | changes))


def bundle(captured):
    path = "base/" + BSL
    record = dict(name="Run", module="Example", source_path=path, line=1, end_line=3,
        is_export=True, is_function=False, complexity=1, calls=[], call_sites=[])
    entry = next(entry for entry in captured.entries if entry.relative_path == BSL)
    output = LinuxScannerOutput(canonical_bytes(record) + b"\n", canonical_bytes(dict(format_version=1,
        files=[dict(source_path=path, raw_sha256=entry.raw_sha256, status="parsed", routine_count=1)])), "a"*64)
    return build_posix_graph_bundle(captured, output,
        limits=PosixGraphLimits(image_buffer_budget=256*1024**2), authorize=captured.checkpoint)


def seal(owner, graph):
    owner.seal(graph, graph_reader_factory=RentgenGraphReaderFactory(),
        graph_limits=VerifiedGraphLimits(image_buffer_budget=2*len(graph.graph_bytes)))


def path(project, owner):
    return project.state_root / "generations" / owner.generation_id


def unchanged(project):
    with project.state.transaction(project.owner) as tx:
        assert tx.get_project_head() == project.head
        assert tx._connection.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 0


def test_real_f2_success_and_generation_final_manifest_last_without_catalog_write(project, monkeypatch):
    captured = capture(project)
    assert len(list((project.state_root / "staging").iterdir())) == 1
    with pytest.raises(CoreError): _ = captured.entries
    writes = []; create = retained.Directory.create_file
    def observed(directory, name): writes.append(name); return create(directory, name)
    monkeypatch.setattr(retained.Directory, "create_file", observed)
    with captured:
        graph = bundle(captured); owner = generation(project, captured)
        with owner:
            borrowed = owner.scan_directory
            assert borrowed._private is True
            assert set(borrowed.names()) == {"base"}
            with pytest.raises(CoreError): _ = owner.result
            seal(owner, graph)
            assert writes[-1] == "manifest.json"
            assert not (path(project, owner) / "source-manifest.json").exists()
            assert not (path(project, owner) / "build-work").exists()
        result = owner.result
        assert result.published is False and result.status == "complete_unpublished_generation"
        assert result.expected_head == project.head and result.source_revision == 1
        manifest = (path(project, owner) / "manifest.json").read_bytes()
        assert result.snapshot.manifest_hash == sha256(manifest)
        document = parse_manifest(manifest)
        assert document["source_digest"] == captured.source_digest
        assert result.verified_total_bytes == sum(p.stat().st_size for p in path(project, owner).rglob("*") if p.is_file())
        assert result.catalog.generation_relpath == "generations/" + owner.generation_id
        for name, raw in project.images.items():
            assert (path(project, owner) / "sources/base" / name).read_bytes() == raw
        for child in path(project, owner).rglob("*"):
            assert stat.S_IMODE(child.stat().st_mode) == (0o700 if child.is_dir() else 0o600)
        with pytest.raises(FrozenInstanceError): result.published = True
    assert borrowed._closed
    assert owner._phase == "closed" and owner._stack is None and not owner._directories
    unchanged(project)


def test_copied_images_survive_f2_close_and_live_source_removal_without_path_fallback(project, monkeypatch):
    captured = capture(project)
    for file in project.source.rglob("*"):
        if file.is_file(): file.unlink()
    monkeypatch.setattr(retained.Directory, "file", lambda *a, **kw: pytest.fail("Copied owner reopened path"))
    with captured:
        entries = captured.entries
        aliases = [captured.read_bytes(entry) for entry in entries]
        assert aliases == [project.images[entry.relative_path] for entry in entries]
    assert aliases == [project.images[entry.relative_path] for entry in entries]
    assert captured._phase == "closed" and not captured._buffers
    with pytest.raises(CoreError): captured.read_bytes(entries[0])


def test_failed_f2_exit_never_returns_copied_owner(project, monkeypatch):
    original = _PosixCaptureCandidate._sync; calls = []
    def fail_exit(candidate):
        calls.append(1)
        if len(calls) == 2: raise OSError("terminal fsync failure")
        return original(candidate)
    monkeypatch.setattr(_PosixCaptureCandidate, "_sync", fail_exit)
    with pytest.raises(OSError, match="terminal fsync"):
        capture(project)
    assert len(list((project.state_root / "staging").iterdir())) == 1
    assert not (project.state_root / "generations").exists()
    unchanged(project)


@pytest.mark.parametrize("field,value", [("resident_byte_budget", 1), ("max_source_bytes", 1),
    ("max_source_entries", 1), ("max_manifest_bytes", 1)])
def test_copied_limit_is_enforced_inside_f2_before_admission(project, field, value):
    limits = replace(copied.PosixCapturedLimits(resident_byte_budget=4*1024**2), **{field: value})
    with pytest.raises(CoreError): capture(project, limits=limits)
    assert not (project.state_root / "generations").exists()


def test_copied_auth_revocation_closes_and_clears_post_read_result(project):
    captured = capture(project)
    with captured:
        entry = captured.entries[0]; authorize = captured._authorize; calls = []
        def revoke():
            authorize(); calls.append(1)
            if len(calls) == 2:
                with project.state.transaction(project.owner, write=True) as tx: revoke_membership(tx, project.worker)
        captured._authorize = revoke
        with pytest.raises(CoreError) as error: captured.read_bytes(entry)
        tb = error.value.__traceback__
        while tb:
            if tb.tb_frame.f_code.co_name == "_call": assert tb.tb_frame.f_locals["result"] is None
            tb = tb.tb_next
    assert not captured._buffers


def test_shared_deadline_is_not_reset_after_f2_or_generation_entry(project, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(copied, "monotonic", lambda: clock[0])
    monkeypatch.setattr(subject, "monotonic", lambda: clock[0])
    captured = capture(project, limits=copied.PosixCapturedLimits(resident_byte_budget=4*1024**2, deadline_seconds=120))
    clock[0] = 119
    with captured:
        assert captured.operation_deadline == 120
        owner = generation(project, captured)
        with pytest.raises(CoreError) as error:
            with owner:
                assert owner._deadline == 120
                clock[0] = 120
                owner.checkpoint()
        assert error.value.code == "SOURCE_READ_DEADLINE_EXCEEDED"
        clock[0] = 119
    unchanged(project)


def test_existing_generation_uuid_is_not_reused_repaired_or_deleted(project):
    with capture(project) as captured:
        identifier = str(uuid4()); target = project.state_root / "generations" / identifier
        target.mkdir(parents=True); target.parent.chmod(0o700); target.chmod(0o700)
        sentinel = target / "foreign"; sentinel.write_bytes(b"foreign"); sentinel.chmod(0o600)
        with pytest.raises(FileExistsError):
            with generation(project, captured, generation_id=identifier): pass
        assert sentinel.read_bytes() == b"foreign" and list(target.iterdir()) == [sentinel]
    unchanged(project)


@pytest.mark.parametrize("mutation", ["source", "extra", "missing", "hardlink", "symlink", "mode", "build-work"])
def test_tampered_generation_never_discloses_result_and_retains_orphan(project, mutation):
    with capture(project) as captured:
        graph = bundle(captured); owner = generation(project, captured)
        with pytest.raises((CoreError, OSError)):
            with owner:
                seal(owner, graph)
                target = path(project, owner); leaf = target / "sources/base" / BSL
                if mutation == "source": leaf.write_bytes(b"X" * leaf.stat().st_size)
                elif mutation == "extra": (target / "extra").write_bytes(b"extra")
                elif mutation == "missing": leaf.unlink()
                elif mutation == "hardlink": os.link(leaf, target / "alias")
                elif mutation == "symlink": leaf.unlink(); leaf.symlink_to(project.source / BSL)
                elif mutation == "mode": leaf.chmod(0o644)
                else: (target / "build-work").mkdir(mode=0o700)
        with pytest.raises(CoreError): _ = owner.result
        assert path(project, owner).is_dir() and owner._phase == "closed" and not owner._directories
    unchanged(project)


@pytest.mark.parametrize("change", ["source_digest", "graph", "coverage", "reader"])
def test_seal_rejects_mismatched_bundle_or_missing_verified_reader(project, change):
    with capture(project) as captured:
        graph = bundle(captured); owner = generation(project, captured)
        if change == "source_digest": graph = replace(graph, receipt=replace(graph.receipt, source_digest="f"*64))
        elif change == "graph": graph = replace(graph, graph_bytes=b"not sqlite")
        elif change == "coverage": graph = replace(graph, coverage=b"x" * (64*1024**2+1))
        with pytest.raises(CoreError):
            with owner:
                if change == "reader": owner.seal(graph, graph_reader_factory=object(), graph_limits=VerifiedGraphLimits(image_buffer_budget=2*len(graph.graph_bytes)))
                else: seal(owner, graph)
        with pytest.raises(CoreError): _ = owner.result
    unchanged(project)


@pytest.mark.parametrize("field,value", [("max_generation_bytes", 1), ("max_inventory_items", 1),
    ("max_retained_descriptors", 1), ("max_relative_components", 2), ("resident_byte_budget", 1)])
def test_generation_preflight_limits_keep_no_complete_result(project, field, value):
    with capture(project) as captured:
        owner = generation(project, captured,
            limits=replace(subject.PosixGenerationLimits(resident_byte_budget=256*1024**2), **{field: value}))
        with pytest.raises(CoreError):
            with owner: pass
        with pytest.raises(CoreError): _ = owner.result
    unchanged(project)


def test_manifest_bound_checked_before_canonical_allocation(project, monkeypatch):
    with capture(project) as captured:
        graph = bundle(captured)
        source_size = len(captured.source_document)
        owner = generation(project, captured,
            limits=replace(subject.PosixGenerationLimits(resident_byte_budget=256*1024**2), max_manifest_bytes=source_size))
        monkeypatch.setattr(subject, "build_manifest", lambda *a: pytest.fail("Oversize final manifest allocated"))
        with pytest.raises(CoreError):
            with owner: seal(owner, graph)
        assert not (path(project, owner) / "manifest.json").exists()


def test_unsealed_exit_fails_and_caller_error_is_not_replaced_by_cleanup(project, monkeypatch):
    with capture(project) as captured:
        owner = generation(project, captured)
        with pytest.raises(CoreError, match="Unsealed"):
            with owner: pass
        assert path(project, owner).exists()
        other = generation(project, captured)
        with pytest.raises(RuntimeError, match="original"):
            with other:
                monkeypatch.setattr(retained.Directory, "verify", lambda *a: (_ for _ in ()).throw(OSError("cleanup")))
                raise RuntimeError("original")


def test_foreign_thread_and_reentrant_close_refuse_without_stealing_owner(project):
    with capture(project) as captured:
        graph = bundle(captured); owner = generation(project, captured)
        with owner:
            errors = []
            def foreign():
                for action in (captured.checkpoint, owner.checkpoint, lambda: owner.__exit__(None,None,None)):
                    try: action()
                    except CoreError as error: errors.append(error.code)
            thread = Thread(target=foreign); thread.start(); thread.join()
            assert len(errors) == 3 and owner._phase == "active" and captured._phase == "active"
            owner._busy = True
            try:
                with pytest.raises(CoreError): owner.__exit__(None,None,None)
            finally: owner._busy = False
            seal(owner, graph)
        assert owner.result.published is False


def test_generation_final_cleanup_deadline_cannot_issue_success(project, monkeypatch):
    clock = [0.0]; monkeypatch.setattr(copied, "monotonic", lambda: clock[0]); monkeypatch.setattr(subject, "monotonic", lambda: clock[0])
    with capture(project) as captured:
        graph = bundle(captured); owner = generation(project, captured)
        cleanup = owner._cleanup
        def slow_cleanup(exception): cleanup(exception); clock[0] = 31
        with pytest.raises(CoreError) as error:
            with owner:
                seal(owner, graph); monkeypatch.setattr(owner, "_cleanup", slow_cleanup)
        assert error.value.code == "SOURCE_READ_DEADLINE_EXCEEDED"
        with pytest.raises(CoreError): _ = owner.result
        clock[0] = 0  # Permit enclosing captured owner to close normally.


@pytest.mark.parametrize("value", [True, False, {"enabled": True, "disabled": [False, None, "😀"]}])
def test_complete_manifest_size_preflight_matches_bool_and_unicode(value):
    assert subject._manifest_size(value) == len(canonical_bytes(value))


@pytest.mark.parametrize("when", ["before_seal", "after_seal"])
@pytest.mark.parametrize("change", ["permission", "configuration"])
def test_current_authority_and_configuration_rechecked_before_complete_receipt(project, when, change):
    captured = capture(project)
    with captured:
        graph = bundle(captured); owner = generation(project, captured)
        with pytest.raises(CoreError):
            with owner:
                if when == "after_seal": seal(owner, graph)
                with project.state.transaction(project.owner, write=True) as tx:
                    if change == "permission": revoke_membership(tx, project.worker)
                    else: tx.configure_source_layers((SourceLayerSpec("base", 0, "base", ".", "unknown"),), expected_revision=1, source_root=project.source)
                if when == "before_seal": seal(owner, graph)
        assert path(project, owner).exists()
        with pytest.raises(CoreError): _ = owner.result
    assert captured._phase == "closed"


def test_generation_budget_accounts_combined_images_before_manifest_allocation(project, monkeypatch):
    with capture(project) as captured:
        graph = bundle(captured); first = generation(project, captured)
        with first: seal(first, graph)
        plan = first.result.resident_image_accounting
        exact = generation(project, captured, limits=subject.PosixGenerationLimits(resident_byte_budget=plan))
        with exact: seal(exact, graph)
        too_small = generation(project, captured, limits=subject.PosixGenerationLimits(resident_byte_budget=plan-1))
        monkeypatch.setattr(subject, "build_manifest", lambda *a: pytest.fail("Unreserved final manifest allocated"))
        with pytest.raises(CoreError) as error:
            with too_small: seal(too_small, graph)
        assert error.value.code == "SOURCE_CAPTURE_LIMIT_EXCEEDED"
        assert not (path(project, too_small) / "manifest.json").exists()


def test_failed_source_disclosure_does_not_retain_image_in_traceback(project, monkeypatch):
    captured = capture(project); denial = RuntimeError("terminal capture denial")
    def deny(*args, **kwargs): raise denial
    # This denial is after immutable source aliases were collected from F2.
    original = _PosixCaptureCandidate.__exit__
    def exit_then_deny(candidate, *args):
        result = original(candidate, *args)
        monkeypatch.setattr(copied, "_CapturedSources", deny)
        return result
    # Separately exercise factory's final admission failure, preserving the cause.
    monkeypatch.setattr(_PosixCaptureCandidate, "__exit__", exit_then_deny)
    with pytest.raises(RuntimeError) as error: capture(project)
    assert error.value is denial
    tb = error.value.__traceback__
    while tb:
        if tb.tb_frame.f_code.co_name == "capture_posix_sources":
            assert tb.tb_frame.f_locals["raw"] is None
            assert tb.tb_frame.f_locals["document"] is None
            assert not tb.tb_frame.f_locals["buffers"]
        tb = tb.tb_next
    # Previously admitted owner is independent; close normally.
    with captured: pass


def test_current_copied_entry_and_cumulative_byte_budget_are_required(project):
    with capture(project) as captured:
        entry = captured.entries[0]
        with pytest.raises(CoreError) as error: captured.read_bytes(replace(entry, raw_sha256="f"*64))
        assert error.value.code == "SOURCE_REF_MISMATCH" and captured._phase == "closed"
    with capture(project, limits=copied.PosixCapturedLimits(resident_byte_budget=4*1024**2, max_read_bytes=1)) as other:
        with pytest.raises(CoreError) as error: other.read_bytes(other.entries[0])
        assert error.value.code == "SOURCE_CAPTURE_LIMIT_EXCEEDED" and not other._buffers


def test_exit_fsync_failure_closes_all_actual_owned_descriptors_and_retains_primary(project, monkeypatch):
    with capture(project) as captured:
        graph = bundle(captured); owner = generation(project, captured)
        with pytest.raises(OSError, match="durability denial"):
            with owner:
                seal(owner, graph)
                caps = [owner._root, owner._generations, *owner._directories.values()]
                held = {entry[0] for cap in caps for entry in cap._chain}
                generation_fd = owner._directories[""]._fd; fsync = os.fsync
                def failing_fsync(fd):
                    if fd == generation_fd: raise OSError("durability denial")
                    return fsync(fd)
                monkeypatch.setattr(os, "fsync", failing_fsync)
        assert all(cap._closed for cap in caps)
        for fd in held:
            with pytest.raises(OSError) as error: os.fstat(fd)
            assert error.value.errno == errno.EBADF
        assert path(project, owner).is_dir()
        with pytest.raises(CoreError): _ = owner.result


@pytest.mark.skipif(not hasattr(os, "fork"), reason="Actual POSIX fork owner guards")
def test_fork_cannot_disclose_sources_or_advance_generation_owner(project):
    with capture(project) as captured:
        graph = bundle(captured); owner = generation(project, captured)
        with owner:
            entry = captured.entries[0]; read_fd, write_fd = os.pipe(); pid = os.fork()
            if pid == 0:
                os.close(read_fd); results = []
                for action in (lambda: captured.read_bytes(entry), owner.checkpoint,
                               lambda: captured.__exit__(None,None,None), lambda: owner.__exit__(None,None,None)):
                    try: action(); results.append("unexpected")
                    except CoreError as error: results.append(error.code)
                os.write(write_fd, ",".join(results).encode()); os.close(write_fd); os._exit(0)
            os.close(write_fd)
            try: result = os.read(read_fd, 512)
            finally: os.close(read_fd); status = os.waitpid(pid, 0)[1]
            assert status == 0 and result == b",".join([b"SOURCE_READ_SESSION_INVALID"] * 4)
            assert captured.read_bytes(entry) == project.images[entry.relative_path]
            seal(owner, graph)
        assert owner.result.published is False


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual Darwin private generation-parent ACL")
def test_darwin_generation_parent_acl_refused_without_repair(project):
    import pwd
    parent = project.state_root / "generations"; parent.mkdir(mode=0o700)
    account = pwd.getpwuid(os.geteuid()).pw_name
    subprocess.run(["/bin/chmod", "+a", f"user:{account} allow read", str(parent)], check=True)
    with capture(project) as captured:
        owner = generation(project, captured)
        with pytest.raises(CoreError, match="ACL"):
            with owner: pass
        assert not path(project, owner).exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux private generation-parent default ACL")
def test_linux_generation_parent_default_acl_refused_without_repair(project):
    import shutil
    if shutil.which("setfacl") is None: pytest.skip("Actual Linux setfacl unavailable")
    parent = project.state_root / "generations"; parent.mkdir(mode=0o700)
    subprocess.run(["setfacl", "-m", "d:u::rwx,d:g::---,d:o::---", str(parent)], check=True)
    with capture(project) as captured:
        owner = generation(project, captured)
        with pytest.raises(CoreError, match="ACL"):
            with owner: pass
        assert not path(project, owner).exists()


@pytest.mark.parametrize("kind", ["captured", "generation"])
@pytest.mark.parametrize("field,value", [("resident_byte_budget", True), ("deadline_seconds", 0), ("max_manifest_bytes", 1.5)])
def test_limits_reject_untyped_or_unbounded_values(kind, field, value):
    cls = copied.PosixCapturedLimits if kind == "captured" else subject.PosixGenerationLimits
    with pytest.raises(CoreError): cls(**({"resident_byte_budget": 1024} | {field: value}))
