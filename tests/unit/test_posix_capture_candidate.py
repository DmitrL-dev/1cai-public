"""Real owned POSIX source-copy boundary; no scanner or publication acceptance."""
from dataclasses import replace
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
from rentgen_core import _posix_capture_candidate as backend
from rentgen_core import _posix_source_tree as retained
from rentgen_core._posix_live_tree import PosixLiveLimits, PosixLiveTree
from rentgen_core.context import Principal
from rentgen_core.errors import CoreError
from rentgen_core.manifests import canonical_bytes, parse_source_document, sha256
from rentgen_core.source_configuration import SourceLayerSpec
from rentgen_core.state import ProjectState

pytestmark = pytest.mark.skipif(sys.platform not in {"darwin", "linux"}, reason="Actual POSIX owned source candidate")
PROJECT = "11111111-1111-4111-8111-111111111111"
MODULE = "CommonModules/Пример/Ext/Module.bsl"


@pytest.fixture
def project(tmp_path):
    root = tmp_path.resolve(); source = root / "source"; source.mkdir(mode=0o755)
    state_root = root / "state"; state_root.mkdir(mode=0o700)
    contents = {MODULE: b"\xef\xbb\xbf" + "Функция Значение() Экспорт\nВозврат 1;\nКонецФункции\n".encode(),
                "binary.bin": b"\x00\xff", "zero": b""}
    for name, raw in contents.items():
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    (source / "Empty/Nested").mkdir(parents=True)
    owner, worker = Principal("owner", "local_os"), Principal("worker", "local_os")
    state = ProjectState.create(state_root / "state.sqlite3", PROJECT, owner)
    with state.transaction(owner, write=True) as tx: grant_membership(tx, worker, {"project:read", "analysis:run"})
    with state.transaction(worker) as tx: head = tx.get_project_head()
    options = dict(state=state, principal=worker, source_root=source, expected_head=head,
        limits=backend.PosixCandidateLimits(resident_byte_budget=2*1024**2), live_limits=PosixLiveLimits(),
        authorize_capture=lambda: None, candidate_id=str(uuid4()))
    return SimpleNamespace(root=root, source=source, state_root=state_root, contents=contents,
        state=state, owner=owner, worker=worker, head=head, options=options)


def opened(project, **changes):
    return backend.open_posix_capture_candidate(**(project.options | changes))


def candidate_path(project, candidate=None):
    return project.state_root / "staging" / (candidate.candidate_id if candidate is not None else project.options["candidate_id"])


def module(candidate):
    return next(entry for entry in candidate.entries if entry.relative_path == MODULE)


def resources(candidate):
    caps = [candidate._root, candidate._staging, *candidate._dirs.values()]
    fds = {entry[0] for cap in caps for entry in cap._chain}
    streams = [record[0] for record in candidate._files.values()]
    fds.update(stream.fileno() for stream in streams)
    return caps, fds, streams


def closed(candidate, held=None):
    assert candidate._phase == "closed" and not candidate._buffers and not candidate._files and not candidate._dirs
    assert candidate._source_document is candidate._authorize is candidate._stack is candidate._live is None
    if held is not None:
        caps, fds, streams = held
        assert all(cap._closed for cap in caps) and all(stream.closed for stream in streams)
        for fd in fds:
            with pytest.raises(OSError) as error: os.fstat(fd)
            assert error.value.errno == errno.EBADF


def test_complete_source_candidate_uses_two_real_live_passes_and_immutable_builder_inputs(project, monkeypatch):
    pread = os.pread; source_ids = {path.stat().st_ino for path in project.source.rglob("*") if path.is_file()}
    live_reads = []; candidate = opened(project)
    def observed(fd, size, offset):
        if os.fstat(fd).st_ino in source_ids: live_reads.append(fd)
        return pread(fd, size, offset)
    monkeypatch.setattr(os, "pread", observed)
    with candidate:
        held = resources(candidate); entries = candidate.entries; document = candidate.source_document
        assert candidate._live is None and candidate.project_id == PROJECT and candidate.source_revision == 1
        assert sha256(document) == candidate.source_digest
        assert parse_source_document(document)["project_id"] == PROJECT
        assert {entry.relative_path for entry in entries} == set(project.contents)
        assert module(candidate).encoding == "utf-8-sig"
        path = candidate_path(project)
        assert (path / "source-manifest.json").read_bytes() == document and not (path / "manifest.json").exists()
        for child in path.rglob("*"):
            assert stat.S_IMODE(child.stat().st_mode) == (0o700 if child.is_dir() else 0o600)
        # Source capture is closed; builder inputs never reopen either content tree.
        monkeypatch.setattr(os, "pread", lambda *a: pytest.fail("Builder reopened content"))
        monkeypatch.setattr(retained.Directory, "file", lambda *a, **k: pytest.fail("Builder reopened a pathname"))
        for entry in entries: assert candidate.read_bytes(entry) == project.contents[entry.relative_path]
    assert len(live_reads) == 2 * len(project.contents)
    closed(candidate, held)
    assert candidate.receipt["status"] == "source_verified_candidate" and candidate.receipt["published"] is False
    assert candidate_path(project).is_dir()
    with project.state.transaction(project.worker) as tx:
        assert tx.get_project_head() == project.head
        assert tx._connection.execute("SELECT count(*) FROM snapshots").fetchone()[0] == 0
    with pytest.raises(CoreError): candidate.read_bytes(entries[0])
    with pytest.raises(CoreError): candidate.__enter__()


def test_builder_bytes_survive_original_live_source_deletion(project):
    with opened(project) as candidate:
        entry = module(candidate); (project.source / MODULE).unlink()
        assert candidate.read_bytes(entry) == project.contents[MODULE]


def test_live_state_exclusion_contains_candidate_writes_and_uses_actual_configuration(project):
    nested = project.source / ".state"; project.state_root.rename(nested)
    project.state_root = nested; project.state = ProjectState(nested / "state.sqlite3", PROJECT)
    project.options["state"] = project.state
    with opened(project) as candidate:
        document = parse_source_document(candidate.source_document)
        assert document["excluded_state_subtrees"] == [dict(layer_id="base", relative_path=".state")]
        assert set(entry.relative_path for entry in candidate.entries) == set(project.contents)


def test_existing_uuid_candidate_is_never_reused_overwritten_or_deleted(project):
    path = candidate_path(project); path.mkdir(parents=True); path.parent.chmod(0o700); path.chmod(0o700)
    sentinel = path / "foreign"; sentinel.write_bytes(b"foreign"); sentinel.chmod(0o600)
    candidate = opened(project)
    with pytest.raises(FileExistsError):
        with candidate: pytest.fail("Existing attempt admitted")
    closed(candidate); assert sentinel.read_bytes() == b"foreign" and list(path.iterdir()) == [sentinel]


@pytest.mark.parametrize("field,value", [("max_source_bytes", 1), ("max_source_entries", 1), ("max_manifest_bytes", 1),
                                         ("max_retained_descriptors", 1), ("max_relative_components", 2), ("resident_byte_budget", 1)])
def test_preflight_budgets_refuse_and_partial_attempts_are_retained_without_cleanup_delete(project, field, value):
    candidate = opened(project, limits=replace(project.options["limits"], **{field: value}))
    with pytest.raises(CoreError):
        with candidate: pytest.fail("Over-budget candidate admitted")
    closed(candidate)
    path = candidate_path(project)
    if field != "max_retained_descriptors": assert path.is_dir()


def test_source_and_resident_thresholds_are_checked_before_content_allocation(project, monkeypatch):
    first = opened(project)
    with first: pass
    plan = first.receipt["resident_image_accounting"]
    total = sum(map(len, project.contents.values()))
    limits = replace(project.options["limits"], resident_byte_budget=plan, max_source_bytes=total)
    with opened(project, candidate_id=str(uuid4()), limits=limits): pass
    pread = os.pread; copies = []
    def observed(*args): copies.append(args); return pread(*args)
    monkeypatch.setattr(os, "pread", observed)
    with pytest.raises(CoreError) as error:
        with opened(project, candidate_id=str(uuid4()), limits=replace(limits, resident_byte_budget=plan-1)): pass
    assert error.value.code == "SOURCE_CAPTURE_LIMIT_EXCEEDED" and not copies


def test_unicode_decoder_and_json_images_have_conservative_expansion_reservation(project):
    raw = b"a" * 65532 + "😀".encode()
    (project.source / "😀.bsl").write_bytes(raw); project.contents["😀.bsl"] = raw
    candidate = opened(project)
    with candidate:
        document = candidate.source_document
        assert any(entry.relative_path == "😀.bsl" for entry in candidate.entries)
    plan = candidate.receipt["resident_image_accounting"]
    total = sum(map(len, project.contents.values()))
    assert plan >= total + max(len(raw) + 5*65536 + 1, 9*len(document) + 1)


@pytest.mark.parametrize("value", [None, 1, "quote\"\\\n😀", ["x", None, 2], {"x": "😀", "z": [1, "a"]}])
def test_manifest_size_preflight_matches_canonical_encoding_without_full_image(value):
    assert backend._json_size(value) == len(canonical_bytes(value))


def test_large_unicode_manifest_length_preflight_matches_real_canonical_serializer():
    document = {"entries": [{"relative_path": "😀" + "a"*200 + str(index), "raw_sha256": "f"*64}
                            for index in range(4096)]}
    encoded = canonical_bytes(document)
    assert len(encoded) > 1024**2 and backend._json_size(document) == len(encoded)


def test_mutation_between_actual_source_passes_is_rejected_and_keeps_orphan(project, monkeypatch):
    original = PosixLiveTree.inventory; calls = []
    def observed(tree, *args):
        result = original(tree, *args); calls.append(result)
        if len(calls) == 2: (project.source / MODULE).write_bytes(b"x" * len(project.contents[MODULE]))
        return result
    monkeypatch.setattr(PosixLiveTree, "inventory", observed)
    candidate = opened(project)
    with pytest.raises(CoreError):
        with candidate: pytest.fail("Changed second pass admitted")
    closed(candidate); assert candidate_path(project).is_dir()


@pytest.mark.parametrize("kind", ["unknown", "modified", "hardlink", "public-mode"])
def test_owned_candidate_inventory_and_private_copy_stamps_are_rechecked(project, kind):
    candidate = opened(project)
    with pytest.raises(CoreError):
        with candidate:
            held = resources(candidate); entry = module(candidate)
            target = candidate_path(project) / "sources/base" / MODULE
            if kind == "unknown": (candidate_path(project) / "unknown").write_bytes(b"unknown")
            elif kind == "modified": target.write_bytes(b"corrupt")
            elif kind == "hardlink": os.link(target, candidate_path(project) / "alias")
            else: target.chmod(0o644)
            if kind != "unknown": candidate.read_bytes(entry)
    closed(candidate, held); assert candidate_path(project).is_dir()


def test_source_copy_replacement_with_equal_bytes_is_not_owned_inode(project):
    changed = [False]
    def authorize():
        target = candidate_path(project) / "sources/base" / MODULE
        if target.exists() and not changed[0]:
            changed[0] = True; target.rename(target.with_name("moved"))
            target.write_bytes(project.contents[MODULE]); target.chmod(0o600)
    candidate = opened(project, authorize_capture=authorize)
    with pytest.raises(CoreError, match="replaced after creation"):
        with candidate: pytest.fail("Replacement copy granted ownership")
    closed(candidate); assert changed[0]


def test_directory_replacement_after_exclusive_create_is_refused_without_deleting_either_tree(project, monkeypatch):
    original = retained.Directory.sync; replaced = [False]
    def sync(directory):
        original(directory)
        path = candidate_path(project)
        if path.exists() and not replaced[0]:
            replaced[0] = True; path.rename(path.with_name("moved")); path.mkdir(mode=0o700)
    monkeypatch.setattr(retained.Directory, "sync", sync)
    candidate = opened(project)
    with pytest.raises(CoreError, match="replaced after creation"):
        with candidate: pytest.fail("Replacement directory granted ownership")
    closed(candidate); assert candidate_path(project).exists() and candidate_path(project).with_name("moved").exists()


def test_actual_fsync_failure_closes_all_opened_fds_and_retains_attempt(project, monkeypatch):
    original_open, original_sync = os.open, os.fsync; fds = []; failure = OSError(errno.EIO, "lost fsync acknowledgement")
    def opened_fd(*args, **kwargs):
        fd = original_open(*args, **kwargs); fds.append(fd); return fd
    def sync(fd):
        original_sync(fd)
        if stat.S_ISREG(os.fstat(fd).st_mode): raise failure
    monkeypatch.setattr(os, "open", opened_fd); monkeypatch.setattr(os, "fsync", sync)
    candidate = opened(project)
    with pytest.raises(OSError) as error:
        with candidate: pytest.fail("Failed durability admitted")
    assert error.value is failure; closed(candidate); assert candidate_path(project).is_dir()
    for fd in fds:
        with pytest.raises(OSError) as error: os.fstat(fd)
        assert error.value.errno == errno.EBADF


def test_primary_builder_failure_survives_candidate_namespace_swap_and_closes_resources(project):
    failure = ValueError("builder failed"); cause = OSError("original cause"); candidate = opened(project)
    with pytest.raises(ValueError) as error:
        with candidate:
            held = resources(candidate); path = candidate_path(project)
            path.rename(path.with_name("moved")); path.mkdir(mode=0o700)
            (path / "foreign").write_bytes(b"foreign")
            raise failure from cause
    assert error.value is failure and error.value.__cause__ is cause
    closed(candidate, held); assert (candidate_path(project) / "foreign").read_bytes() == b"foreign"


def test_current_membership_head_and_configuration_are_rechecked(project):
    with opened(project) as candidate:
        held = resources(candidate)
        with project.state.transaction(project.owner, write=True) as tx: revoke_membership(tx, project.worker)
        with pytest.raises(CoreError) as error: candidate.entries
        assert error.value.code == "PROJECT_FORBIDDEN"
        closed(candidate, held)


def test_expected_head_conflict_refuses_before_candidate_creation(project):
    with pytest.raises(CoreError) as error:
        with opened(project, expected_head=replace(project.head, revision=project.head.revision + 1)): pass
    assert error.value.code == "HEAD_CONFLICT" and not (project.state_root / "staging").exists()


def test_audited_configuration_change_invalidates_builder_inputs(project):
    with opened(project) as candidate:
        held = resources(candidate); entry = module(candidate)
        with project.state.transaction(project.owner, write=True) as tx:
            tx.configure_source_layers((SourceLayerSpec("base", 0, "base", ".", "unknown"),),
                expected_revision=1, source_root=project.source)
        with pytest.raises(CoreError) as error: candidate.read_bytes(entry)
        assert error.value.code in {"HEAD_CONFLICT", "SOURCE_CONFIGURATION_CONFLICT"}
        closed(candidate, held)


@pytest.mark.parametrize("where", ["state", "staging"])
def test_existing_nonprivate_namespace_is_refused_without_repair(project, where):
    path = project.state_root if where == "state" else project.state_root / "staging"
    if where == "staging": path.mkdir(mode=0o700)
    path.chmod(0o755)
    with pytest.raises(CoreError, match="permissions"):
        with opened(project): pytest.fail("Unsafe private parent admitted")
    assert stat.S_IMODE(path.stat().st_mode) == 0o755


@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_actual_live_aliases_cannot_enter_owned_copy(project, kind):
    target = project.source / "alias"
    if kind == "symlink": target.symlink_to(project.source / MODULE)
    else: os.link(project.source / MODULE, target)
    candidate = opened(project)
    with pytest.raises(CoreError):
        with candidate: pytest.fail("Live alias was copied")
    closed(candidate); assert candidate_path(project).is_dir()


def test_success_exit_repeats_actual_bottom_up_directory_fsync(project, monkeypatch):
    original = os.fsync; events = []
    def sync(fd):
        original(fd)
        events.append((os.fstat(fd).st_dev, os.fstat(fd).st_ino))
    monkeypatch.setattr(os, "fsync", sync)
    with opened(project) as candidate:
        expected = [(os.fstat(candidate._dirs[relative]._fd).st_dev, os.fstat(candidate._dirs[relative]._fd).st_ino)
            for relative in sorted(candidate._dirs, key=lambda value: value.count("/") + bool(value), reverse=True)]
        expected.extend([(os.fstat(cap._fd).st_dev, os.fstat(cap._fd).st_ino) for cap in (candidate._staging, candidate._root)])
        events.clear()
    assert events == expected


def test_cancellation_closes_resources_preserves_primary_and_retains_unpublished_candidate(project):
    failure = KeyboardInterrupt("cancelled"); candidate = opened(project)
    with pytest.raises(KeyboardInterrupt) as error:
        with candidate:
            held = resources(candidate)
            raise failure
    assert error.value is failure; closed(candidate, held); assert candidate_path(project).exists()
    with pytest.raises(CoreError): candidate.receipt


def test_revoke_after_real_builder_input_preparation_prevents_disclosure(project, monkeypatch):
    with opened(project) as candidate:
        entry = module(candidate); held = resources(candidate); original = candidate._file_check
        def check(relative):
            value = original(relative)
            with project.state.transaction(project.owner, write=True) as tx: revoke_membership(tx, project.worker)
            return value
        monkeypatch.setattr(candidate, "_file_check", check)
        with pytest.raises(CoreError) as error: candidate.read_bytes(entry)
        assert error.value.code == "PROJECT_FORBIDDEN"; closed(candidate, held)
        traceback = error.value.__traceback__
        while traceback:
            if traceback.tb_frame.f_code.co_name == "_call": assert traceback.tb_frame.f_locals["result"] is None
            traceback = traceback.tb_next


def test_retained_entry_denial_traceback_has_no_undisclosed_source_or_manifest_images(project):
    denial = CoreError("PROJECT_FORBIDDEN", "Denied before source manifest write")
    def authorize():
        if candidate._live is None and candidate._source_document is not None: raise denial
    candidate = opened(project, authorize_capture=authorize)
    with pytest.raises(CoreError) as error:
        with candidate: pytest.fail("Denied manifest admitted")
    assert error.value is denial; closed(candidate)
    names = set(); traceback = error.value.__traceback__
    while traceback:
        frame = traceback.tb_frame; name = frame.f_code.co_name
        if name == "__enter__" and frame.f_globals.get("__name__") == backend.__name__:
            assert frame.f_locals["raw"] is frame.f_locals["expected"] is None; names.add(name)
        if name == "_write_verified": assert frame.f_locals["raw"] is None; names.add(name)
        traceback = traceback.tb_next
    assert names == {"__enter__", "_write_verified"}


def test_builder_read_byte_budget_and_source_entry_binding_are_fail_closed(project):
    with opened(project, limits=replace(project.options["limits"], max_builder_read_bytes=1)) as candidate:
        with pytest.raises(CoreError) as error: candidate.read_bytes(module(candidate))
        assert error.value.code == "SOURCE_CAPTURE_LIMIT_EXCEEDED"; closed(candidate)
    with opened(project, candidate_id=str(uuid4())) as candidate:
        with pytest.raises(CoreError) as error: candidate.read_bytes(replace(module(candidate), raw_sha256="f"*64))
        assert error.value.code == "SOURCE_REF_MISMATCH"; closed(candidate)


def test_foreign_thread_public_exit_and_read_cannot_consume_owner_close(project):
    with opened(project) as candidate:
        entry = module(candidate); held = resources(candidate); errors = []
        def foreign():
            for operation in (lambda: candidate.read_bytes(entry), lambda: candidate.__exit__(None, None, None)):
                try: operation()
                except CoreError as error: errors.append(error.code)
        thread = Thread(target=foreign); thread.start(); thread.join(timeout=5)
        assert not thread.is_alive() and errors == ["SOURCE_READ_SESSION_INVALID"] * 2
        assert candidate.read_bytes(entry) == project.contents[MODULE]
    closed(candidate, held)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="Actual POSIX fork owner guard")
def test_forked_child_cannot_inherit_builder_inputs_or_close_parent(project):
    with opened(project) as candidate:
        entry = module(candidate); held = resources(candidate); read_fd, write_fd = os.pipe(); pid = os.fork()
        if pid == 0:
            os.close(read_fd); errors = []
            for operation in (lambda: candidate.read_bytes(entry), lambda: candidate.__exit__(None, None, None)):
                try: operation(); errors.append("unexpected success")
                except CoreError as error: errors.append(error.code)
            os.write(write_fd, ",".join(errors).encode()); os.close(write_fd); os._exit(0)
        os.close(write_fd)
        try: result = os.read(read_fd, 256)
        finally: os.close(read_fd); status = os.waitpid(pid, 0)[1]
        assert status == 0 and result == b"SOURCE_READ_SESSION_INVALID,SOURCE_READ_SESSION_INVALID"
        assert candidate.read_bytes(entry) == project.contents[MODULE]
    closed(candidate, held)


@pytest.mark.parametrize("phase", ["entry", "read", "exit"])
def test_reentrant_authorizer_cannot_disclose_or_consume_candidate_context(project, phase):
    armed = [phase == "entry"]; refusals = []
    def authorize():
        if armed[0]:
            for operation in (lambda: candidate.entries, lambda: candidate.__exit__(None, None, None)):
                with pytest.raises(CoreError) as error: operation()
                assert error.value.code == "SOURCE_READ_SESSION_INVALID"; refusals.append(error.value)
    candidate = opened(project, authorize_capture=authorize)
    with candidate:
        held = resources(candidate); entry = module(candidate); armed[0] = phase == "read"
        assert candidate.read_bytes(entry) == project.contents[MODULE]
        armed[0] = phase == "exit"
    assert refusals; closed(candidate, held)


@pytest.mark.parametrize("phase", ["entry", "read", "exit"])
def test_deadline_covers_entry_builder_disclosure_and_exit(project, monkeypatch, phase):
    now = [100]; monkeypatch.setattr(backend, "monotonic", lambda: now[0])
    def authorize():
        if phase == "entry": now[0] += 30
    candidate = opened(project, authorize_capture=authorize)
    with pytest.raises(CoreError) as error:
        with candidate:
            entry = module(candidate); held = resources(candidate); now[0] += 30
            if phase == "read": candidate.read_bytes(entry)
    assert error.value.code == "SOURCE_READ_DEADLINE_EXCEEDED"; closed(candidate)
    if phase != "entry": closed(candidate, held)


@pytest.mark.parametrize("field,value", [("resident_byte_budget", True), ("resident_byte_budget", 2*1024**3+1), ("deadline_seconds", 31)])
def test_candidate_limits_are_explicit_typed_and_do_not_expand_maxima(field, value):
    options = dict(resident_byte_budget=1) | {field: value}
    with pytest.raises(CoreError): backend.PosixCandidateLimits(**options)


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual Darwin private candidate-parent ACL")
def test_mac_private_staging_acl_refused_before_candidate_creation(project):
    import pwd
    parent = project.state_root / "staging"; parent.mkdir(mode=0o700)
    account = pwd.getpwuid(os.geteuid()).pw_name
    subprocess.run(["/bin/chmod", "+a", f"user:{account} allow read", str(parent)], check=True)
    with pytest.raises(CoreError, match="ACL"):
        with opened(project): pytest.fail("Private parent ACL admitted")
    assert not candidate_path(project).exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux private candidate-parent default ACL")
def test_linux_private_staging_default_acl_refused_with_mode_0700(project):
    import struct
    parent = project.state_root / "staging"; parent.mkdir(mode=0o700)
    undefined = 0xFFFFFFFF
    entries = [(1, 7, undefined), (2, 4, os.geteuid()), (4, 0, undefined), (16, 0, undefined), (32, 0, undefined)]
    acl = struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *entry) for entry in entries)
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.setxattr(fd, "system.posix_acl_default", acl)
        assert stat.S_IMODE(os.fstat(fd).st_mode) == 0o700
    finally: os.close(fd)
    with pytest.raises(CoreError, match="ACL"):
        with opened(project): pytest.fail("Private default ACL admitted")
    assert not candidate_path(project).exists()
