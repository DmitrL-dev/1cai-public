"""Real POSIX private creation controls; Linux registry admission stays OS-specific."""

from contextlib import closing, contextmanager
import os
from pathlib import Path
import sqlite3
import stat
import sys
from uuid import uuid4

import pytest

from rentgen_core import _private_state_bootstrap as bootstrap
from rentgen_core import _sqlite
from rentgen_core.context import Principal
from rentgen_core.errors import CoreError
from rentgen_core.registry import ProjectRegistry
from rentgen_core.state import ProjectState

pytestmark = pytest.mark.skipif(
    sys.platform not in {"linux", "darwin"}, reason="Actual POSIX private creation primitives"
)
linux = pytest.mark.skipif(sys.platform != "linux", reason="Actual Linux registry bootstrap")
OWNER = Principal("test-owner", "local_os")


@pytest.fixture
def root(tmp_path):
    # Canonicalize only this fixture: the system /var alias on macOS is not a
    # product path accepted by the no-follow Linux bootstrap.
    return tmp_path.resolve()


def create_state(owned):
    return ProjectState.create(
        owned.path / "state.sqlite3", str(uuid4()), OWNER, _bootstrap=owned
    )


def assert_state(state):
    with state.transaction(OWNER) as tx:
        tx.require_all({"project:read", "project:admin"})
        head = tx.get_project_head()
        assert head.revision == 0 and head.snapshot is None
    with closing(sqlite3.connect(state.path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (4,)
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT project_id FROM project").fetchone() == (state.project_id,)
    assert sorted(p.name for p in state.path.parent.iterdir()) == ["state.sqlite3"]


@pytest.mark.parametrize("mask", [0, 0o022, 0o077])
def test_real_private_state_schema_permissions_membership_and_wal(root, mask):
    previous = os.umask(mask)
    try:
        with bootstrap._new_private_root(root / "state") as owned:
            state = create_state(owned)
            owned.verify(complete=True)
            assert stat.S_IMODE(owned.path.stat().st_mode) == 0o700
            assert stat.S_IMODE(state.path.stat().st_mode) == 0o600
            assert_state(state)
    finally:
        os.umask(previous)
    assert_state(state)
    with pytest.raises(CoreError, match="closed"):
        owned.verify()


@pytest.mark.parametrize("change", ["root", "database", "root-permissions", "database-permissions"])
def test_scope_exit_rejects_post_initialization_changes_and_closes_owned_fds(root, change):
    path = root / "state"
    descriptors = []
    with pytest.raises(CoreError):
        with bootstrap._new_private_root(path) as owned:
            create_state(owned)
            descriptors.extend((owned.directory._fd, owned.database_fd))
            if change == "root":
                path.rename(root / "original-root")
                path.mkdir(mode=0o700)
                (path / "state.sqlite3").write_bytes(b"foreign database")
                (path / "state.sqlite3").chmod(0o600)
            elif change == "database":
                (path / "state.sqlite3").rename(root / "original.sqlite3")
                (path / "state.sqlite3").write_bytes(b"foreign database")
                (path / "state.sqlite3").chmod(0o600)
            elif change == "root-permissions":
                path.chmod(0o755)
            else:
                (path / "state.sqlite3").chmod(0o644)
    assert len(descriptors) == 2
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    if change in {"root", "database"}:
        assert (path / "state.sqlite3").read_bytes() == b"foreign database"
    if change == "root-permissions":
        assert stat.S_IMODE(path.stat().st_mode) == 0o755
    if change == "database-permissions":
        assert stat.S_IMODE((path / "state.sqlite3").stat().st_mode) == 0o644


@pytest.mark.parametrize("change", ["root", "database"])
def test_scope_exit_change_preserves_primary_denial_after_initialization(root, change):
    path = root / "state"
    failure = CoreError("TEST_DENIED", "Primary post-bootstrap denial")
    cause = ValueError("Original post-bootstrap cause")
    with pytest.raises(CoreError) as caught:
        with bootstrap._new_private_root(path) as owned:
            create_state(owned)
            if change == "root":
                path.rename(root / "original-root")
                path.mkdir(mode=0o700)
            else:
                (path / "state.sqlite3").rename(root / "original.sqlite3")
            (path / "state.sqlite3").write_bytes(b"foreign database")
            raise failure from cause
    assert caught.value is failure and caught.value.__cause__ is cause
    assert (path / "state.sqlite3").read_bytes() == b"foreign database"


def test_empty_root_scope_stays_permitted_and_expires(root):
    with bootstrap._new_private_root(root / "state") as owned:
        owned.verify()
    assert list((root / "state").iterdir()) == []
    with pytest.raises(CoreError, match="closed"):
        owned.verify()


@pytest.mark.parametrize("kind", ["private", "unsafe", "file", "symlink", "dangling"])
def test_existing_state_is_never_repaired_or_removed(root, kind):
    path = root / "state"
    target = root / "target"
    target.mkdir(mode=0o700)
    marker = target / "marker"
    marker.write_bytes(b"foreign")
    if kind in {"private", "unsafe"}:
        path.mkdir(mode=0o700 if kind == "private" else 0o777)
        path.chmod(0o700 if kind == "private" else 0o777)
    elif kind == "file":
        path.write_bytes(b"existing")
    else:
        path.symlink_to(target if kind == "symlink" else root / "absent", target_is_directory=True)
    before = path.lstat()
    with pytest.raises(FileExistsError):
        with bootstrap._new_private_root(path):
            pytest.fail("Existing root was admitted")
    after = path.lstat()
    assert (after.st_ino, after.st_mode, after.st_uid) == (before.st_ino, before.st_mode, before.st_uid)
    assert marker.read_bytes() == b"foreign"
    if kind == "file":
        assert path.read_bytes() == b"existing"


def test_symlink_ancestor_is_not_resolved_for_creation(root):
    target = root / "target"
    target.mkdir()
    (root / "alias").symlink_to(target, target_is_directory=True)
    with pytest.raises((CoreError, OSError)):
        with bootstrap._new_private_root(root / "alias" / "state"):
            pytest.fail("Symlink ancestor admitted")
    assert list(target.iterdir()) == []


@pytest.mark.parametrize("mode", [0o777, 0o775, 0o707])
def test_cross_uid_writable_parent_namespace_is_refused_before_mkdir(root, mode):
    parent = root / "shared"
    parent.mkdir()
    parent.chmod(mode)
    with pytest.raises(CoreError, match="foreign replacement"):
        with bootstrap._new_private_root(parent / "state"):
            pytest.fail("Writable non-sticky namespace admitted")
    assert list(parent.iterdir()) == []
    assert stat.S_IMODE(parent.stat().st_mode) == mode


def test_sticky_owned_parent_retains_private_child_namespace(root):
    parent = root / "sticky"
    parent.mkdir()
    parent.chmod(0o1777)
    with bootstrap._new_private_root(parent / "state") as owned:
        state = create_state(owned)
        owned.verify(complete=True)
    assert_state(state)
    assert stat.S_IMODE(parent.stat().st_mode) == 0o1777


def test_incomplete_state_and_repeated_factory_are_refused(root):
    with bootstrap._new_private_root(root / "state") as owned:
        with pytest.raises(CoreError, match="incomplete"):
            owned.verify(complete=True)
        create_state(owned)
        with pytest.raises(CoreError, match="One exact"):
            create_state(owned)


def test_exact_database_path_is_required_before_any_file_creation(root):
    with bootstrap._new_private_root(root / "state") as owned:
        with pytest.raises(CoreError, match="One exact"):
            with _sqlite.create_database(owned.path / "other.sqlite3", "CREATE TABLE t(a);", _owned=owned):
                pytest.fail("Wrong database path admitted")
        assert list(owned.path.iterdir()) == []


def test_bootstrap_error_keeps_primary_cause_and_empty_orphan(root):
    failure = CoreError("TEST_DENIED", "Primary bootstrap denial")
    cause = ValueError("Original cause")
    with pytest.raises(CoreError) as caught:
        with bootstrap._new_private_root(root / "state") as owned:
            with _sqlite.create_database(owned.path / "state.sqlite3", "CREATE TABLE t(a);", _owned=owned):
                raise failure from cause
    assert caught.value is failure and caught.value.__cause__ is cause
    assert (root / "state").is_dir() and list((root / "state").iterdir()) == []


def test_schema_sqlite_error_remains_state_unavailable_and_orphan(root):
    with pytest.raises(CoreError) as caught:
        with bootstrap._new_private_root(root / "state") as owned:
            with _sqlite.create_database(owned.path / "state.sqlite3", "INVALID SQL;", _owned=owned):
                pytest.fail("Invalid schema accepted")
    assert caught.value.code == "STATE_UNAVAILABLE"
    assert isinstance(caught.value.__cause__, sqlite3.Error)
    assert list((root / "state").iterdir()) == []


@pytest.mark.parametrize("cleanup", ["rollback", "close"])
def test_memory_cleanup_failure_does_not_mask_primary_denial(root, monkeypatch, cleanup):
    original_connect = sqlite3.connect
    failure = CoreError("TEST_DENIED", "Primary bootstrap denial")
    cause = ValueError("Primary denial cause")
    class Connection:
        def __init__(self, connection):
            self.connection = connection
        def __getattr__(self, name):
            return getattr(self.connection, name)
        def rollback(self):
            self.connection.rollback()
            if cleanup == "rollback":
                raise OSError("Secondary rollback failure")
        def close(self):
            self.connection.close()
            if cleanup == "close":
                raise OSError("Secondary close failure")
    def connect(*args, **kwargs):
        return Connection(original_connect(*args, **kwargs))
    monkeypatch.setattr(sqlite3, "connect", connect)
    with pytest.raises(CoreError) as caught:
        with bootstrap._new_private_root(root / "state") as owned:
            with _sqlite.create_database(owned.path / "state.sqlite3", "CREATE TABLE t(a);", _owned=owned):
                raise failure from cause
    assert caught.value is failure and caught.value.__cause__ is cause
    assert list((root / "state").iterdir()) == []


def test_bootstrap_byte_limit_precedes_serialization_and_file_reservation(root, monkeypatch):
    monkeypatch.setattr(bootstrap, "MAX_BOOTSTRAP_BYTES", 4096)
    with pytest.raises(CoreError, match="byte bound"):
        with bootstrap._new_private_root(root / "state") as owned:
            create_state(owned)
    assert list((root / "state").iterdir()) == []


def test_partial_descriptor_writes_produce_complete_sqlite_bytes(root, monkeypatch):
    original_write = os.write
    writes = []
    def partial(descriptor, raw):
        writes.append(len(raw))
        return original_write(descriptor, raw[:997])
    monkeypatch.setattr(os, "write", partial)
    with bootstrap._new_private_root(root / "state") as owned:
        state = create_state(owned)
    assert len(writes) > 1 and writes[-1] <= 997
    assert_state(state)


def test_zero_progress_write_leaves_private_orphan_and_closes_owned_fd(root, monkeypatch):
    descriptors = []
    def no_progress(descriptor, raw):
        descriptors.append(descriptor)
        return 0
    monkeypatch.setattr(os, "write", no_progress)
    with pytest.raises(OSError, match="no progress"):
        with bootstrap._new_private_root(root / "state") as owned:
            create_state(owned)
    assert len(descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    path = root / "state" / "state.sqlite3"
    assert path.read_bytes() == b"" and stat.S_IMODE(path.stat().st_mode) == 0o600


def test_default_database_creation_remains_the_existing_factory(root):
    path = root / "default.sqlite3"
    previous = os.umask(0o022)
    try:
        state = ProjectState.create(path, str(uuid4()), OWNER)
    finally:
        os.umask(previous)
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    with state.transaction(OWNER) as tx:
        tx.require_all({"project:read", "project:admin"})
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)


def test_default_database_creation_retains_original_failure_cleanup(root):
    path = root / "default.sqlite3"
    failure = ValueError("Original default bootstrap failure")
    with pytest.raises(ValueError) as caught:
        with _sqlite.create_database(path, "CREATE TABLE t(a);"):
            raise failure
    assert caught.value is failure
    assert not any(root.glob("default.sqlite3*"))


@pytest.mark.parametrize("kind", ["root", "ancestor"])
def test_replacement_during_memory_bootstrap_preserves_foreign_namespace(root, kind):
    parent = root / "parent"
    parent.mkdir()
    state = parent / "state"
    with pytest.raises((CoreError, OSError)):
        with bootstrap._new_private_root(state) as owned:
            with _sqlite.create_database(state / "state.sqlite3", "CREATE TABLE t(a);", _owned=owned):
                selected = state if kind == "root" else parent
                selected.rename(root / "moved")
                state.mkdir(parents=True, mode=0o700)
                (state / "state.sqlite3").write_bytes(b"foreign database")
                (state / "state.sqlite3-journal").write_bytes(b"foreign journal")
    assert (state / "state.sqlite3").read_bytes() == b"foreign database"
    assert (state / "state.sqlite3-journal").read_bytes() == b"foreign journal"
    original = root / "moved" if kind == "root" else root / "moved" / "state"
    assert list(original.iterdir()) == []


@pytest.mark.parametrize("change", ["replace", "root", "hardlink", "permissions", "truncate"])
def test_post_write_changes_deny_before_wal_and_never_cleanup_foreign(root, monkeypatch, change):
    original_fsync = os.fsync
    applied = []
    state = root / "state"
    def fsync(descriptor):
        result = original_fsync(descriptor)
        if not applied and stat.S_ISREG(os.fstat(descriptor).st_mode) and os.fstat(descriptor).st_size:
            applied.append(True)
            path = state / "state.sqlite3"
            if change == "replace":
                path.rename(state / "owned.saved")
                path.write_bytes(b"foreign database")
                path.chmod(0o600)
            elif change == "root":
                state.rename(root / "owned-root")
                state.mkdir(mode=0o700)
                path.write_bytes(b"foreign database")
                (state / "state.sqlite3-journal").write_bytes(b"foreign journal")
            elif change == "hardlink":
                os.link(path, root / "alias")
            elif change == "permissions":
                path.chmod(0o644)
            else:
                os.ftruncate(descriptor, 1)
        return result
    monkeypatch.setattr(os, "fsync", fsync)
    with pytest.raises((CoreError, OSError)):
        with bootstrap._new_private_root(state) as owned:
            create_state(owned)
    assert applied
    if change in {"replace", "root"}:
        assert (state / "state.sqlite3").read_bytes() == b"foreign database"
    if change == "root":
        assert (state / "state.sqlite3-journal").read_bytes() == b"foreign journal"
    if change == "permissions":
        assert stat.S_IMODE((state / "state.sqlite3").stat().st_mode) == 0o644
    if change == "hardlink":
        assert (root / "alias").exists() and (state / "state.sqlite3").stat().st_nlink == 2


def test_unexpected_entry_and_changed_root_permissions_are_not_repaired(root):
    for name, mutate in [
        ("extra", lambda p: (p / "foreign").write_bytes(b"foreign")),
        ("mode", lambda p: p.chmod(0o755)),
    ]:
        path = root / name
        with pytest.raises(CoreError):
            with bootstrap._new_private_root(path) as owned:
                with _sqlite.create_database(path / "state.sqlite3", "CREATE TABLE t(a);", _owned=owned):
                    mutate(path)
        assert not (path / "state.sqlite3").exists()
    assert (root / "extra" / "foreign").read_bytes() == b"foreign"
    assert stat.S_IMODE((root / "mode").stat().st_mode) == 0o755


def test_non_linux_production_entry_is_refused_without_disk_changes(root):
    if sys.platform == "linux":
        pytest.skip("Negative non-Linux dispatch requires an actual non-Linux OS")
    with pytest.raises(CoreError) as caught:
        with bootstrap.new_linux_private_state(root / "state"):
            pytest.fail("Non-Linux production bootstrap admitted")
    assert caught.value.code == "PRIVATE_STATE_PLATFORM_UNSUPPORTED"
    assert not (root / "state").exists()


@linux
def test_linux_registry_registers_only_complete_private_state(root):
    source = root / "source"
    source.mkdir()
    registry = ProjectRegistry.create(root / "registry.sqlite3")
    registered = registry.register(OWNER, source_root=source, state_root=root / "state", display_name="Private")
    assert registry.get(registered.project_id) == registered
    assert registry.list_for(OWNER)[0].project_id == registered.project_id
    assert stat.S_IMODE(registered.state_root.stat().st_mode) == 0o700
    assert_state(ProjectState(registered.state_root / "state.sqlite3", registered.project_id))


@linux
def test_linux_registry_commit_failure_keeps_descriptors_and_rolls_back_catalog(root, monkeypatch):
    source = root / "source"
    source.mkdir()
    registry = ProjectRegistry.create(root / "registry.sqlite3")
    original_transaction = _sqlite.transaction
    original_root = bootstrap.new_linux_private_state
    observed = []
    failure = RuntimeError("Catalog commit boundary failure")
    @contextmanager
    def retained_root(path):
        with original_root(path) as owned:
            observed.append(owned)
            yield owned
    @contextmanager
    def transaction(path, *, write=False):
        with original_transaction(path, write=write) as connection:
            yield connection
            if Path(path) == registry.path and write:
                observed[0].verify(complete=True)
                os.fstat(observed[0].database_fd)
                raise failure
    monkeypatch.setattr(bootstrap, "new_linux_private_state", retained_root)
    monkeypatch.setattr(_sqlite, "transaction", transaction)
    with pytest.raises(RuntimeError) as caught:
        registry.register(OWNER, source_root=source, state_root=root / "state", display_name="Fail")
    assert caught.value is failure
    assert registry.list_for(OWNER) == ()
    assert stat.S_IMODE((root / "state").stat().st_mode) == 0o700
    with closing(sqlite3.connect(root / "state" / "state.sqlite3")) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (4,)
    with pytest.raises(CoreError, match="closed"):
        observed[0].verify()


@linux
def test_linux_registry_rejects_symlink_parent_without_resolving_it(root):
    source = root / "source"
    source.mkdir()
    target = root / "target"
    target.mkdir()
    (root / "alias").symlink_to(target, target_is_directory=True)
    registry = ProjectRegistry.create(root / "registry.sqlite3")
    with pytest.raises((CoreError, OSError)):
        registry.register(OWNER, source_root=source, state_root=root / "alias" / "state", display_name="Alias")
    assert registry.list_for(OWNER) == () and list(target.iterdir()) == []


@linux
def test_linux_inherited_default_acl_is_rejected_without_repair(root):
    from test_local_identity_lifetime import add_acl
    parent = root / "parent"
    parent.mkdir(mode=0o700)
    add_acl(parent, default=True)
    with pytest.raises(CoreError):
        with bootstrap.new_linux_private_state(parent / "state"):
            pytest.fail("Inherited default ACL admitted")
    assert list((parent / "state").iterdir()) == []
    assert os.getxattr(parent / "state", "system.posix_acl_default")
