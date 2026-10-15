"""Real held-descriptor identity checks; Linux admission stays Linux-only.

Darwin cases exercise only the private POSIX reader/walk and native Darwin ACLs.
They do not change platform dispatch or qualify Linux bootstrap on macOS.
"""
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
from uuid import uuid4

import pytest

from rentgen_core import local_identity as identity
from rentgen_core.errors import CoreError


pytestmark = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Actual POSIX descriptors")
linux = pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux identity bootstrap")


def profile_at(root, *, namespace=None):
    profile = root / "private" / "identity.json"
    profile.parent.mkdir(mode=0o700, parents=True)
    profile.write_bytes(identity._profile_bytes({
        "schema": 1, "kind": "rentgen.local-account",
        "namespace": namespace or str(uuid4()), "uid": os.geteuid(),
    }))
    profile.chmod(0o600)
    return profile


@pytest.fixture
def profile(tmp_path):
    return profile_at(tmp_path.resolve() / "ancestor")


def test_reader_preserves_canonical_principal_and_deliberately_copied_namespace(profile):
    before = profile.read_bytes()
    expected = json.loads(before)["namespace"]
    principal = identity._linux_profile_principal(profile)
    assert principal.id == f"linux-local:{expected}:uid:{os.geteuid()}"
    copied = profile_at(profile.parent.parent.parent / "copy", namespace=expected)
    assert identity._linux_profile_principal(copied) == principal
    assert profile.read_bytes() == copied.read_bytes() == before


@pytest.mark.parametrize("create", [False, True])
def test_any_symlink_ancestor_is_refused_without_creating_below_it(profile, create):
    alias = profile.parent.parent.parent / "alias"
    alias.symlink_to(profile.parent.parent, target_is_directory=True)
    requested = alias / ("new" if create else "private") / "identity.json"
    with pytest.raises(OSError):
        with identity._profile_parent(requested, create=create):
            pytest.fail("Symlink ancestor was followed")
    assert not (profile.parent.parent / "new").exists()


def test_create_walk_is_private_and_never_repairs_existing_permissions(tmp_path):
    root = tmp_path.resolve()
    requested = root / "new" / "nested" / "identity.json"
    with identity._profile_parent(requested, create=True) as (parent, name):
        assert name == "identity.json"
        assert stat.S_IMODE(os.fstat(parent.fd).st_mode) == 0o700
        assert stat.S_IMODE((root / "new").stat().st_mode) == 0o700
    requested.parent.chmod(0o755)
    with pytest.raises(OSError):
        with identity._profile_parent(requested, create=True):
            pytest.fail("Existing public directory was admitted")
    assert stat.S_IMODE(requested.parent.stat().st_mode) == 0o755
    assert list(requested.parent.iterdir()) == []


@pytest.mark.parametrize("suffix", ["private/../private/identity.json", "../identity.json"])
def test_parent_traversal_is_refused_before_creation(tmp_path, suffix):
    root = tmp_path.resolve()
    with pytest.raises(OSError):
        with identity._profile_parent(root / suffix, create=True):
            pytest.fail("Parent traversal was admitted")
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("path", ["/", "/" + "x" * 256])
def test_invalid_final_name_is_an_identity_filesystem_error(path):
    with pytest.raises(OSError):
        identity._profile_parent(path)


def during_read(monkeypatch, profile, action):
    original = os.read
    inode = profile.stat().st_ino
    called = False

    def read(fd, count):
        nonlocal called
        raw = original(fd, count)
        if not called and os.fstat(fd).st_ino == inode:
            called = True
            action()
        return raw

    monkeypatch.setattr(os, "read", read)


def test_ancestor_swap_during_read_refuses_disclosure_and_preserves_replacement(profile, monkeypatch):
    ancestor = profile.parent.parent
    saved = ancestor.with_name("saved")
    replacement = None

    def swap():
        nonlocal replacement
        ancestor.rename(saved)
        replacement = profile_at(ancestor)

    during_read(monkeypatch, profile, swap)
    with pytest.raises(OSError, match="ancestor namespace"):
        identity._linux_profile_principal(profile)
    assert replacement is not None
    assert identity._linux_profile_principal(replacement).id != identity._linux_profile_principal(saved / "private" / "identity.json").id


@pytest.mark.parametrize("defect", ["bytes", "mode", "hardlink", "replacement"])
def test_file_stamp_or_namespace_mutation_during_read_is_refused(profile, monkeypatch, defect):
    def mutate():
        if defect == "bytes":
            value = json.loads(profile.read_bytes())
            value["namespace"] = str(uuid4())
            profile.write_bytes(identity._profile_bytes(value))
        elif defect == "mode":
            profile.chmod(0o644)
        elif defect == "hardlink":
            os.link(profile, profile.with_suffix(".linked"))
        else:
            raw = profile.read_bytes()
            profile.rename(profile.with_suffix(".saved"))
            profile.write_bytes(raw)
            profile.chmod(0o600)

    during_read(monkeypatch, profile, mutate)
    with pytest.raises(OSError):
        identity._linux_profile_principal(profile)


def test_short_reads_are_completed_within_the_existing_1024_byte_bound(profile, monkeypatch):
    original = os.read
    expected = identity._linux_profile_principal(profile)
    monkeypatch.setattr(os, "read", lambda fd, count: original(fd, min(count, 7)))
    assert identity._linux_profile_principal(profile) == expected


def test_mutation_during_document_validation_is_refused(profile, monkeypatch):
    original = identity._profile_bytes

    def encode(value):
        raw = original(value)
        changed = dict(value, namespace=str(uuid4()))
        profile.write_bytes(original(changed))
        return raw

    monkeypatch.setattr(identity, "_profile_bytes", encode)
    with pytest.raises(OSError, match="changed"):
        identity._linux_profile_principal(profile)


def add_acl(path, *, default=False):
    if sys.platform == "darwin":
        import pwd

        assert not default
        account = pwd.getpwuid(os.geteuid()).pw_name
        subprocess.run(["/bin/chmod", "+a", f"user:{account} allow read", str(path)], check=True)
    else:
        undefined = 0xFFFFFFFF
        owner_permissions = 7 if path.is_dir() else 6
        entries = [(0x01, owner_permissions, undefined), (0x02, 4, os.geteuid()),
                   (0x04, 0, undefined), (0x10, 0, undefined), (0x20, 0, undefined)]
        raw = struct.pack("<I", 2) + b"".join(struct.pack("<HHI", *entry) for entry in entries)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            name = "system.posix_acl_default" if default else "system.posix_acl_access"
            os.setxattr(fd, name, raw)
            assert os.getxattr(fd, name) == raw
        finally:
            os.close(fd)


@pytest.mark.parametrize("target", ["parent", "file"])
def test_real_native_private_acl_is_refused_even_with_private_mode(profile, target):
    selected = profile.parent if target == "parent" else profile
    before = stat.S_IMODE(selected.stat().st_mode)
    add_acl(selected)
    assert stat.S_IMODE(selected.stat().st_mode) == before
    with pytest.raises(OSError, match="ACL"):
        identity._linux_profile_principal(profile)


def test_real_native_parent_acl_introduced_during_read_is_refused(profile, monkeypatch):
    during_read(monkeypatch, profile, lambda: add_acl(profile.parent))
    with pytest.raises(OSError, match="ACL"):
        identity._linux_profile_principal(profile)


@linux
def test_real_linux_default_acl_on_private_parent_is_refused(profile):
    add_acl(profile.parent, default=True)
    assert stat.S_IMODE(profile.parent.stat().st_mode) == 0o700
    with pytest.raises(CoreError) as caught:
        identity.current_local_principal(identity_profile=profile)
    assert caught.value.code == "LOCAL_IDENTITY_UNAVAILABLE"


@pytest.mark.parametrize("failure", [OSError("primary read error"), KeyboardInterrupt()])
def test_cleanup_failure_preserves_the_current_read_failure(profile, monkeypatch, failure):
    original_close = os.close

    def close(fd):
        original_close(fd)
        raise OSError("secondary close error")

    monkeypatch.setattr(os, "read", lambda *args: (_ for _ in ()).throw(failure))
    monkeypatch.setattr(os, "close", close)
    with pytest.raises(type(failure)) as caught:
        identity._linux_profile_principal(profile)
    assert caught.value is failure


@pytest.mark.parametrize("failed_open", [1, 3, 5])
def test_failed_ancestor_entry_closes_every_owned_descriptor(profile, monkeypatch, failed_open):
    original_open, original_stat = os.open, os.fstat
    opened = []
    failure = OSError("injected held-ancestor metadata failure")

    def open_fd(*args, **kwargs):
        fd = original_open(*args, **kwargs)
        opened.append(fd)
        return fd

    def stat_fd(fd):
        if len(opened) == failed_open and fd == opened[-1]:
            raise failure
        return original_stat(fd)

    monkeypatch.setattr(os, "open", open_fd)
    monkeypatch.setattr(os, "fstat", stat_fd)
    with pytest.raises(OSError) as caught:
        identity._linux_profile_principal(profile)
    assert caught.value is failure
    assert len(opened) == failed_open
    for fd in opened:
        with pytest.raises(OSError):
            original_stat(fd)


@linux
def test_real_bootstrap_nested_private_namespace_and_exact_profile_bytes(tmp_path):
    profile = tmp_path.resolve() / "new" / "nested" / "identity.json"
    principal = identity.initialize_local_identity(profile)
    raw = profile.read_bytes()
    assert identity.current_local_principal(identity_profile=profile) == principal
    assert raw == identity._profile_bytes(json.loads(raw))
    assert set(json.loads(raw)) == {"schema", "kind", "namespace", "uid"}
    assert stat.S_IMODE(profile.stat().st_mode) == 0o600
    assert stat.S_IMODE(profile.parent.stat().st_mode) == 0o700
    assert list(profile.parent.iterdir()) == [profile]


@linux
def test_owned_temporary_mode_is_initialized_under_restrictive_umask(tmp_path):
    profile = tmp_path.resolve() / "private" / "identity.json"
    profile.parent.mkdir(mode=0o700)
    root = Path(__file__).resolve().parents[2]
    code = """
import json, os, sys
from rentgen_core import local_identity as identity
previous = os.umask(0o777)
try:
    principal = identity.initialize_local_identity(sys.argv[1])
finally:
    os.umask(previous)
print(json.dumps({'principal': principal.id, 'module': identity.__file__}))
"""
    result = subprocess.run([sys.executable, "-c", code, str(profile)], cwd=root,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    record = json.loads(result.stdout)
    assert Path(record["module"]).resolve() == root / "rentgen_core" / "local_identity.py"
    assert identity.current_local_principal(identity_profile=profile).id == record["principal"]
    assert stat.S_IMODE(profile.stat().st_mode) == 0o600
    assert stat.S_IMODE(profile.parent.stat().st_mode) == 0o700
    assert list(profile.parent.iterdir()) == [profile]


@linux
def test_bootstrap_rejects_default_acl_without_permission_repair(tmp_path):
    profile = profile_at(tmp_path.resolve())
    profile.unlink()
    add_acl(profile.parent, default=True)
    with pytest.raises(CoreError) as caught:
        identity.initialize_local_identity(profile)
    assert caught.value.code == "LOCAL_IDENTITY_UNAVAILABLE"
    assert list(profile.parent.iterdir()) == []


@linux
def test_parent_swap_before_publication_denies_and_preserves_foreign_namespace(tmp_path, monkeypatch):
    ancestor = tmp_path.resolve() / "ancestor"
    profile = ancestor / "private" / "identity.json"
    original_write = os.write
    saved = ancestor.with_name("saved")

    def write(fd, raw):
        count = original_write(fd, raw)
        ancestor.rename(saved)
        foreign = profile_at(ancestor)
        assert foreign == profile
        return count

    monkeypatch.setattr(os, "write", write)
    with pytest.raises(CoreError):
        identity.initialize_local_identity(profile)
    assert list((saved / "private").iterdir()) == []
    assert list(profile.parent.iterdir()) == [profile]
    assert identity.current_local_principal(identity_profile=profile).id.startswith("linux-local:")


@linux
def test_failed_publication_never_unlinks_a_replaced_temporary(tmp_path, monkeypatch):
    profile = tmp_path.resolve() / "private" / "identity.json"
    failure = OSError("primary publication failure")
    foreign = b"foreign temporary bytes"

    def replace(parent, temporary, name):
        os.rename(temporary, temporary + ".saved", src_dir_fd=parent, dst_dir_fd=parent)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent)
        try:
            os.write(fd, foreign)
        finally:
            os.close(fd)
        raise failure

    monkeypatch.setattr(identity, "_publish_identity_profile", replace)
    with pytest.raises(CoreError) as caught:
        identity.initialize_local_identity(profile)
    assert caught.value.__cause__ is failure
    files = list(profile.parent.iterdir())
    assert len(files) == 2 and not profile.exists()
    assert next(path for path in files if path.suffix == ".tmp").read_bytes() == foreign


@linux
@pytest.mark.parametrize("defect", ["different_inode", "different_bytes"])
def test_published_inode_and_bytes_are_both_verified(tmp_path, monkeypatch, defect):
    profile = tmp_path.resolve() / "private" / "identity.json"
    original_publish = identity._publish_identity_profile

    def replace(parent, temporary, name):
        original_publish(parent, temporary, name)
        if defect == "different_inode":
            os.rename(name, name + ".saved", src_dir_fd=parent, dst_dir_fd=parent)
            raw = (profile.parent / (name + ".saved")).read_bytes()
            profile.write_bytes(raw)
            profile.chmod(0o600)
        else:
            value = json.loads(profile.read_bytes())
            value["namespace"] = str(uuid4())
            profile.write_bytes(identity._profile_bytes(value))

    monkeypatch.setattr(identity, "_publish_identity_profile", replace)
    with pytest.raises(CoreError):
        identity.initialize_local_identity(profile)
    assert profile.exists()
    if defect == "different_inode":
        assert profile.read_bytes() == profile.with_suffix(".json.saved").read_bytes()
        assert profile.stat().st_ino != profile.with_suffix(".json.saved").stat().st_ino


@linux
def test_final_sync_failure_preserves_published_identity_and_retry_never_replaces(tmp_path, monkeypatch):
    profile = tmp_path.resolve() / "private" / "identity.json"
    original_sync = os.fsync
    failed = False

    def sync(fd):
        nonlocal failed
        if not failed and profile.exists() and stat.S_ISDIR(os.fstat(fd).st_mode):
            failed = True
            raise OSError("final directory fsync failure")
        original_sync(fd)

    monkeypatch.setattr(os, "fsync", sync)
    with pytest.raises(CoreError):
        identity.initialize_local_identity(profile)
    assert failed
    raw = profile.read_bytes()
    principal = identity.current_local_principal(identity_profile=profile)
    with pytest.raises(CoreError):
        identity.initialize_local_identity(profile)
    assert profile.read_bytes() == raw
    assert identity.current_local_principal(identity_profile=profile) == principal
    assert list(profile.parent.iterdir()) == [profile]


@linux
def test_publication_cleanup_failure_preserves_primary_cause(tmp_path, monkeypatch):
    profile = tmp_path.resolve() / "private" / "identity.json"
    failure = OSError("primary publication failure")
    monkeypatch.setattr(identity, "_publish_identity_profile", lambda *args: (_ for _ in ()).throw(failure))
    monkeypatch.setattr(os, "unlink", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("secondary cleanup failure")))
    with pytest.raises(CoreError) as caught:
        identity.initialize_local_identity(profile)
    assert caught.value.__cause__ is failure
    assert not profile.exists()
