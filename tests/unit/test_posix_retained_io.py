"""Real POSIX descriptors, namespace races and durable owner-report publication."""

import errno
from contextlib import ExitStack, contextmanager
import os
import stat
import subprocess
import sys
import time

import pytest

from rentgen_core import _posix_source_tree as backend
from rentgen_core.errors import CoreError
from rentgen_core.owner_report import build_owner_report
from rentgen_core.owner_report_store import OwnerReportStore
from rentgen_core.platform_filesystem import open_directory, read_retained

pytestmark = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Actual POSIX filesystem acceptance")
PROJECT = "12345678-1234-5678-1234-567812345678"
SNAPSHOT = "b" * 64
REPORT = "12345678-1234-4234-8234-123456789abc"


@pytest.fixture
def root(tmp_path):
    # Canonicalize only this newly owned fixture root: /var is a macOS symlink.
    return tmp_path.resolve()


def store_at(root):
    store = OwnerReportStore(root / "receipts")
    store.initialize()
    return store


def load(store, report_id=REPORT):
    return store.get(report_id, expected_project_id=PROJECT, expected_snapshot_id=SNAPSHOT, authorize=lambda: None)


def test_native_retained_bytes_are_copied_and_capability_expires(root):
    path = root / "source"
    path.write_bytes(b"original")
    raw = read_retained(path, 8)
    path.write_bytes(b"modified")
    assert raw == b"original"
    with open_directory(root) as cap:
        assert cap.read("source", 8) == b"modified"
    with pytest.raises(CoreError, match="closed"):
        cap.read("source", 8)


@pytest.mark.parametrize("kind", ["symlink", "ancestor", "hardlink", "fifo", "directory"])
def test_native_reader_rejects_aliases_and_special_leaves(root, kind):
    path = root / "source"
    target = root / "actual"
    target.write_bytes(b"private")
    if kind == "symlink":
        path.symlink_to(target)
    elif kind == "ancestor":
        parent = root / "real"
        parent.mkdir()
        (parent / "file").write_bytes(b"private")
        path.symlink_to(parent, target_is_directory=True)
        path /= "file"
    elif kind == "hardlink":
        os.link(target, path)
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        path.mkdir()
    with pytest.raises((CoreError, OSError)):
        read_retained(path, 10)
    assert target.read_bytes() == b"private"


@pytest.mark.parametrize("bound", [-1, True, backend.MAX_BYTES + 1])
def test_invalid_bound_refused_before_leaf_open(root, monkeypatch, bound):
    with open_directory(root) as cap:
        monkeypatch.setattr(cap, "file", lambda *a, **k: pytest.fail("Invalid bound opened a leaf"))
        with pytest.raises(ValueError):
            cap.read("missing", bound)


def test_read_bound_and_inventory_bound_are_enforced(root):
    (root / "large").write_bytes(b"1234")
    with open_directory(root) as cap:
        with pytest.raises(CoreError, match="byte bound"):
            cap.read("large", 3)
        with pytest.raises(CoreError, match="entry bound"):
            cap.names(maximum=0)
        assert cap.read("large", 4) == b"1234"


def test_same_size_real_child_mutation_is_rejected_on_scope_exit(root):
    path = root / "source"
    path.write_bytes(b"AAAA")
    with open_directory(root) as cap:
        with pytest.raises(CoreError, match="changed"):
            with cap.file("source") as stream:
                assert stream.read(4) == b"AAAA"
                subprocess.run([sys.executable, "-c", "import pathlib,sys;pathlib.Path(sys.argv[1]).write_bytes(b'BBBB')", str(path)], check=True)
    assert path.read_bytes() == b"BBBB"


def test_held_directory_replacement_rejects_without_foreign_open(root):
    selected = root / "selected"
    selected.mkdir()
    (selected / "source").write_bytes(b"selected")
    foreign = root / "foreign"
    foreign.mkdir()
    (foreign / "source").write_bytes(b"foreign")
    with pytest.raises(CoreError, match="changed"):
        with open_directory(selected) as cap:
            selected.rename(root / "moved")
            selected.symlink_to(foreign, target_is_directory=True)
            cap.read("source", 8)
    assert (foreign / "source").read_bytes() == b"foreign"


@pytest.mark.parametrize("scope", ["directory", "child", "file", "create"])
def test_original_denial_and_cause_survive_exit_namespace_failure(root, scope):
    selected = root / "selected"
    selected.mkdir(mode=0o700)
    (selected / "source").write_bytes(b"source")
    denied = CoreError("ACCESS_DENIED", "Explicit callback denial")
    cause = ValueError("Trusted callback cause")
    with pytest.raises(CoreError) as error:
        with ExitStack() as contexts:
            if scope == "directory":
                contexts.enter_context(open_directory(selected))
            else:
                parent = contexts.enter_context(open_directory(root))
                child = contexts.enter_context(parent.child("selected", private=scope == "create"))
                if scope == "file":
                    contexts.enter_context(child.file("source"))
                elif scope == "create":
                    contexts.enter_context(child.create_file("new"))
            selected.rename(root / "moved")
            raise denied from cause
    assert error.value is denied
    assert error.value.__cause__ is cause


@pytest.mark.parametrize("scope", ["directory", "child", "file", "create"])
def test_handled_outer_exception_never_suppresses_new_verification_failure(root, scope):
    selected = root / "selected"
    selected.mkdir(mode=0o700)
    (selected / "source").write_bytes(b"source")
    with pytest.raises((CoreError, OSError)):
        try:
            raise ValueError("Already handled, unrelated caller failure")
        except ValueError:
            with ExitStack() as contexts:
                if scope == "directory":
                    contexts.enter_context(open_directory(selected))
                else:
                    parent = contexts.enter_context(open_directory(root))
                    child = contexts.enter_context(parent.child("selected", private=scope == "create"))
                    if scope == "file":
                        contexts.enter_context(child.file("source"))
                    elif scope == "create":
                        contexts.enter_context(child.create_file("new"))
                selected.rename(root / "moved")


def test_collision_recovery_never_returns_receipt_after_leaf_replacement(root, monkeypatch):
    import json

    store = store_at(root)
    report = build_owner_report(PROJECT, SNAPSHOT)
    seed = root / "seed"
    seed.mkdir()
    accepted = store_at(seed).save(report, report_id=REPORT, authorize=lambda: None)
    raw = json.dumps(accepted, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    original_file = backend.Directory.file
    @contextmanager
    def replace_after_read(cap, name):
        with original_file(cap, name) as stream:
            yield stream
            if name == REPORT + ".json":
                # Real namespace change after reading exact valid receipt bytes.
                (store.reports / name).rename(store.reports / "unavailable.json")
    def collide(cap, name, candidate):
        with cap.create_file(name) as stream:
            stream.write(raw)
        raise FileExistsError("Collision fallback must still verify reads")
    monkeypatch.setattr(backend.Directory, "file", replace_after_read)
    monkeypatch.setattr(backend.Directory, "publish_bytes", collide)
    with pytest.raises(CoreError) as error:
        store.save(report, report_id=REPORT, authorize=lambda: None)
    assert error.value.code == "OWNER_REPORT_STORE_RECOVERY_REQUIRED"


def test_handled_outer_exception_never_suppresses_publication_identity_failure(root, monkeypatch):
    root.chmod(0o700)
    rename = backend._rename_exclusive
    with open_directory(root, private=True) as cap:
        def substitute(fd, source, destination):
            os.rename(source, "retained-original", src_dir_fd=fd, dst_dir_fd=fd)
            descriptor = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
            try:
                os.write(descriptor, b"candidate")
            finally:
                os.close(descriptor)
            rename(fd, source, destination)
        monkeypatch.setattr(backend, "_rename_exclusive", substitute)
        with pytest.raises(CoreError, match="identity differ"):
            try:
                raise ValueError("Already handled caller failure")
            except ValueError:
                cap.publish_bytes("receipt", b"candidate")


def test_unlock_failure_does_not_replace_authorization_denial(root, monkeypatch):
    import fcntl

    store = store_at(root)
    flock = fcntl.flock
    denied = CoreError("ACCESS_DENIED", "Revoked before publication")
    def fail_unlock(fd, operation):
        if operation == fcntl.LOCK_UN:
            raise OSError(errno.EIO, "Injected unlock failure")
        return flock(fd, operation)
    calls = []
    def authorize():
        calls.append(None)
        if len(calls) == 2:
            raise denied
    monkeypatch.setattr(fcntl, "flock", fail_unlock)
    with pytest.raises(CoreError) as error:
        store.save(build_owner_report(PROJECT, SNAPSHOT), authorize=authorize)
    assert error.value is denied
    assert list(store.reports.iterdir()) == []


@pytest.mark.parametrize("fail_at", [1, 3])
def test_entry_fstat_failure_closes_every_opened_descriptor(root, monkeypatch, fail_at):
    real_open, real_stat = os.open, os.fstat
    opened, calls = [], []
    def tracked_open(*args, **kwargs):
        fd = real_open(*args, **kwargs)
        opened.append(fd)
        return fd
    def fail_stat(fd):
        calls.append(fd)
        if len(calls) == fail_at:
            raise OSError(errno.EIO, "Injected entry fstat failure")
        return real_stat(fd)
    with monkeypatch.context() as patch:
        patch.setattr(os, "open", tracked_open)
        patch.setattr(os, "fstat", fail_stat)
        with pytest.raises(OSError) as error:
            with open_directory(root):
                pytest.fail("Entry failure admitted a directory")
        assert error.value.errno == errno.EIO
    assert len(opened) == fail_at
    for fd in opened:
        with pytest.raises(OSError) as error:
            real_stat(fd)
        assert error.value.errno == errno.EBADF


@pytest.mark.parametrize("name", ["../escape", ".", "..", "a/b", "", "x\0y"])
def test_directory_methods_reject_nonleaf_names(root, name):
    with open_directory(root) as cap:
        with pytest.raises(CoreError):
            cap.read(name, 10)


def test_public_directory_cannot_open_writable_or_create(root):
    (root / "source").write_bytes(b"source")
    with open_directory(root) as cap:
        for method in (lambda: cap.create_file("new"),):
            with pytest.raises(CoreError, match="private directory"):
                with method():
                    pytest.fail("Public capability admitted a writer")
    assert (root / "source").read_bytes() == b"source"
    assert not (root / "new").exists()


def test_private_publication_is_complete_exclusive_and_fsynced(root):
    root.chmod(0o700)
    with open_directory(root, private=True) as cap:
        cap.publish_bytes("receipt", b"accepted")
        with pytest.raises(FileExistsError):
            cap.publish_bytes("receipt", b"replacement")
        assert cap.read("receipt", 8) == b"accepted"
        assert cap.names() == ["receipt"]
        assert stat.S_IMODE(cap.stat("receipt").st_mode) == 0o600


def test_failed_publish_never_removes_other_files(root, monkeypatch):
    root.chmod(0o700)
    other = root / "foreign"
    other.write_bytes(b"keep")
    with open_directory(root, private=True) as cap:
        def fail(*args):
            raise OSError(errno.EIO, "Injected publication failure")
        monkeypatch.setattr(backend, "_rename_exclusive", fail)
        with pytest.raises(OSError):
            cap.publish_bytes("receipt", b"candidate")
        assert cap.names() == ["foreign"]
    assert other.read_bytes() == b"keep"


def test_publish_cleanup_preserves_original_denial_when_namespace_changes(root, monkeypatch):
    selected = root / "selected"
    selected.mkdir(mode=0o700)
    moved = root / "moved"
    denied = CoreError("ACCESS_DENIED", "Explicit publication denial")
    cause = ValueError("Trusted callback cause")
    def deny(*args):
        selected.rename(moved)
        raise denied from cause
    monkeypatch.setattr(backend, "_rename_exclusive", deny)
    with pytest.raises(CoreError) as error:
        with open_directory(selected, private=True) as cap:
            cap.publish_bytes("receipt", b"retained candidate")
    assert error.value is denied
    assert error.value.__cause__ is cause
    assert not (moved / "receipt").exists()
    assert [p.read_bytes() for p in moved.iterdir()] == [b"retained candidate"]


def test_postrename_identity_check_rejects_different_inode_even_with_same_bytes(root, monkeypatch):
    root.chmod(0o700)
    rename = backend._rename_exclusive
    with open_directory(root, private=True) as cap:
        def substitute(fd, source, destination):
            os.rename(source, "retained-original", src_dir_fd=fd, dst_dir_fd=fd)
            descriptor = os.open(source, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=fd)
            try:
                os.write(descriptor, b"candidate")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            rename(fd, source, destination)
        monkeypatch.setattr(backend, "_rename_exclusive", substitute)
        with pytest.raises(CoreError, match="identity differ"):
            cap.publish_bytes("receipt", b"candidate")
        assert cap.read("receipt", 9) == b"candidate"
        assert cap.read("retained-original", 9) == b"candidate"


def test_durability_failure_retains_complete_unknown_final_for_explicit_retry(root, monkeypatch):
    store = store_at(root)
    report = build_owner_report(PROJECT, SNAPSHOT)
    real_fsync = os.fsync
    failed, directory_syncs = [], []
    def fail_after_publish(fd):
        info = os.fstat(fd)
        if stat.S_ISDIR(info.st_mode) and (store.reports / (REPORT + ".json")).exists():
            if not failed:
                failed.append(True)
                raise OSError(errno.EIO, "Injected final directory fsync failure")
            if info.st_ino == store.reports.stat().st_ino:
                directory_syncs.append(info.st_ino)
        return real_fsync(fd)
    monkeypatch.setattr(os, "fsync", fail_after_publish)
    with pytest.raises(CoreError) as error:
        store.save(report, report_id=REPORT, authorize=lambda: None)
    assert error.value.code == "OWNER_REPORT_STORE_RECOVERY_REQUIRED"
    assert failed == [True]
    first = load(store)
    assert directory_syncs == []
    assert store.save(report, report_id=REPORT, authorize=lambda: None) == first
    assert directory_syncs == [store.reports.stat().st_ino]
    assert list(store.reports.iterdir()) == [store.reports / (REPORT + ".json")]


def test_idempotent_retry_cannot_turn_persistent_directory_eio_into_success(root, monkeypatch):
    store = store_at(root)
    report = build_owner_report(PROJECT, SNAPSHOT)
    real_fsync = os.fsync
    def fail_directory(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode) and (store.reports / (REPORT + ".json")).exists():
            raise OSError(errno.EIO, "Persistent final directory fsync failure")
        return real_fsync(fd)
    monkeypatch.setattr(os, "fsync", fail_directory)
    for _ in range(2):
        with pytest.raises(CoreError) as error:
            store.save(report, report_id=REPORT, authorize=lambda: None)
        assert error.value.code == "OWNER_REPORT_STORE_RECOVERY_REQUIRED"
        assert len(list(store.reports.iterdir())) == 1
    monkeypatch.setattr(os, "fsync", real_fsync)
    assert store.save(report, report_id=REPORT, authorize=lambda: None) == load(store)


def test_real_processes_serialize_same_receipt_without_overwrite(root):
    import json

    store = store_at(root)
    report = json.dumps(build_owner_report(PROJECT, SNAPSHOT))
    script = "from rentgen_core.owner_report_store import OwnerReportStore; import json,sys; r=OwnerReportStore(sys.argv[1]).save(json.loads(sys.argv[2]),report_id=sys.argv[3],authorize=lambda:None); print(r['receipt_id'])"
    children = []
    try:
        for _ in range(4):
            children.append(subprocess.Popen([sys.executable, "-c", script, str(store.root), report, REPORT], stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        receipts = []
        for child in children:
            stdout, stderr = child.communicate(timeout=10)
            assert child.returncode == 0, stderr.decode()
            receipts.append(stdout.decode().strip())
        assert len(set(receipts)) == 1
        assert receipts[0] == load(store)["receipt_id"]
        assert len(list(store.reports.iterdir())) == 1
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)


def test_busy_lock_owned_by_real_child_refuses_new_publication(root):
    store = store_at(root)
    marker = root / "child-ready"
    script = "import fcntl,pathlib,sys,time; f=open(sys.argv[1],'r+b'); fcntl.flock(f,fcntl.LOCK_EX); pathlib.Path(sys.argv[2]).write_bytes(b'ready'); time.sleep(10)"
    child = subprocess.Popen([sys.executable, "-c", script, str(store.root / "store.lock"), str(marker)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 3
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.read_bytes() == b"ready"
        with pytest.raises(CoreError) as error:
            store.save(build_owner_report(PROJECT, SNAPSHOT), authorize=lambda: None)
        assert error.value.code == "OWNER_REPORT_STORE_BUSY"
        assert list(store.reports.iterdir()) == []
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)


def test_owner_store_restart_reads_exact_receipt_and_private_modes(root):
    store = store_at(root)
    receipt = store.save(build_owner_report(PROJECT, SNAPSHOT), report_id=REPORT, authorize=lambda: None)
    reopened = OwnerReportStore(store.root)
    reopened.initialize()
    assert load(reopened) == receipt
    assert reopened.list(expected_project_id=PROJECT, expected_snapshot_id=SNAPSHOT, authorize=lambda: None) == [receipt]
    for path in (store.root, store.reports):
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
    for path in (store.root / "store.lock", store.reports / (REPORT + ".json")):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("component", ["root", "reports", "lock"])
def test_store_symlink_replacement_never_writes_foreign_directory(root, component):
    store = store_at(root)
    foreign = root / "foreign"
    foreign.mkdir()
    sentinel = foreign / "sentinel"
    sentinel.write_bytes(b"keep")
    selected = {"root": store.root, "reports": store.reports, "lock": store.root / "store.lock"}[component]
    selected.rename(selected.with_name(selected.name + "-old"))
    selected.symlink_to(sentinel if component == "lock" else foreign, target_is_directory=component != "lock")
    with pytest.raises(CoreError):
        store.save(build_owner_report(PROJECT, SNAPSHOT), report_id=REPORT, authorize=lambda: None)
    assert list(foreign.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"keep"


@pytest.mark.parametrize("raw", [b"", b"1", b"00"])
def test_corrupt_lock_fails_closed_before_receipt_publication(root, raw):
    store = store_at(root)
    (store.root / "store.lock").write_bytes(raw)
    with pytest.raises(CoreError) as error:
        store.save(build_owner_report(PROJECT, SNAPSHOT), authorize=lambda: None)
    assert error.value.code == "OWNER_REPORT_STORE_RECOVERY_REQUIRED"
    assert list(store.reports.iterdir()) == []


def test_prepublication_revocation_does_not_create_receipt(root):
    store = store_at(root)
    calls = []
    def authorize():
        calls.append(None)
        if len(calls) == 2:
            raise CoreError("ACCESS_DENIED", "Revoked before publication")
    with pytest.raises(CoreError, match="Revoked"):
        store.save(build_owner_report(PROJECT, SNAPSHOT), report_id=REPORT, authorize=authorize)
    assert len(calls) == 2
    assert list(store.reports.iterdir()) == []


def test_report_directory_swapped_by_authorization_is_rejected(root):
    store = store_at(root)
    foreign = root / "foreign"
    foreign.mkdir()
    foreign.chmod(0o700)
    calls = []
    def authorize():
        calls.append(None)
        if len(calls) == 2:
            store.reports.rename(store.root / "retained-old")
            store.reports.symlink_to(foreign, target_is_directory=True)
    with pytest.raises(CoreError):
        store.save(build_owner_report(PROJECT, SNAPSHOT), report_id=REPORT, authorize=authorize)
    assert list(foreign.iterdir()) == []
    assert list((store.root / "retained-old").iterdir()) == []


def test_incomplete_temporary_is_recovery_required_not_history(root):
    store = store_at(root)
    (store.reports / ".rentgen-interrupted.tmp").write_bytes(b"partial")
    with pytest.raises(CoreError) as error:
        store.save(build_owner_report(PROJECT, SNAPSHOT), authorize=lambda: None)
    assert error.value.code == "OWNER_REPORT_STORE_RECOVERY_REQUIRED"
    assert len(list(store.reports.iterdir())) == 1


@pytest.mark.parametrize("mode", [0o755, 0o750, 0o777])
def test_existing_nonprivate_store_is_rejected_without_chmod(root, mode):
    selected = root / "receipts"
    selected.mkdir(mode=mode)
    selected.chmod(mode)
    with pytest.raises(CoreError, match="unsafe"):
        OwnerReportStore(selected).initialize()
    assert stat.S_IMODE(selected.stat().st_mode) == mode
    assert list(selected.iterdir()) == []


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual Darwin extended ACL")
def test_mac_private_acl_is_rejected_on_held_descriptor(root):
    import pwd

    root.chmod(0o700)
    account = pwd.getpwuid(os.getuid()).pw_name
    subprocess.run(["/bin/chmod", "+a", f"user:{account} allow read", str(root)], check=True)
    with pytest.raises(CoreError, match="ACL"):
        with open_directory(root, private=True):
            pytest.fail("Private directory ACL was admitted")


@pytest.mark.skipif(sys.platform != "darwin", reason="Actual Darwin extended ACL")
def test_private_ancestor_acl_is_rechecked_while_child_is_held(root):
    import pwd

    root.chmod(0o700)
    account = pwd.getpwuid(os.getuid()).pw_name
    with pytest.raises(CoreError, match="ACL"):
        with open_directory(root, private=True) as parent:
            with parent.child("child", create=True, private=True) as child:
                subprocess.run(["/bin/chmod", "+a", f"user:{account} allow read", str(root)], check=True)
                child.publish_bytes("denied", b"bytes")
    assert list((root / "child").iterdir()) == []


@pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux default ACL xattr")
def test_linux_private_directory_default_acl_is_rejected_even_with_mode_0700(root):
    import struct

    root.chmod(0o700)
    # Fixed Linux UAPI: include/uapi/linux/{posix_acl,posix_acl_xattr}.h (v6.12).
    # An extended default ACL need not change directory access-mode bits.
    undefined = 0xFFFFFFFF
    # A named current-UID entry is still extended and mapped in user namespaces.
    entries = [(0x01, 7, undefined), (0x02, 4, os.geteuid()), (0x04, 0, undefined),
               (0x10, 0, undefined), (0x20, 0, undefined)]
    acl = struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *entry) for entry in entries)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.setxattr(fd, "system.posix_acl_default", acl)
        assert os.getxattr(fd, "system.posix_acl_default") == acl
        assert stat.S_IMODE(os.fstat(fd).st_mode) == 0o700
    finally:
        os.close(fd)
    with pytest.raises(CoreError, match="ACL"):
        with open_directory(root, private=True):
            pytest.fail("Linux private default ACL was admitted")
