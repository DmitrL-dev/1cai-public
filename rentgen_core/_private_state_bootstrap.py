"""Exclusive private state creation; no repair, migration or capture admission.

Creation uses held directory/file descriptors. SQLite still uses its ordinary
pathname VFS inside the private root, with namespace checks around each reopen;
this is not a descriptor-bound SQLite VFS or hostile same-UID isolation.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
import stat
import sys

from . import _posix_source_tree as retained
from .errors import CoreError

MAX_BOOTSTRAP_BYTES = 16 * 1024**2


def _unsafe(message):
    return CoreError("PRIVATE_STATE_UNSAFE", message)


def _admit_parent(parent):
    """Exclude cross-UID rename authority before the exclusive mkdir/open pair.

    Linux POSIX ACL write grants are bounded by the group permission mask;
    sticky directories still protect children owned by this effective UID.
    Directory.verify subsequently keeps the admitted mode/owner chain bound.
    """
    parent.verify()
    for descriptor, *_ in parent._chain:
        info = os.fstat(descriptor)
        if (info.st_uid not in {0, os.geteuid()}
                or (stat.S_IMODE(info.st_mode) & 0o022
                    and not info.st_mode & stat.S_ISVTX)):
            raise _unsafe("State parent namespace permits foreign replacement")
    parent.verify()


class _OwnedStateRoot:
    """One invocation's new directory and optional exclusively reserved DB."""

    def __init__(self, path, directory):
        self.path, self.directory = path, directory
        self.database_fd = None
        self.database_identity = None
        self.initialized = False
        self.started = False

    def verify(self, *, complete=False):
        self.directory.verify()
        expected = [] if self.database_fd is None else ["state.sqlite3"]
        if self.directory.names(maximum=4) != expected:
            raise _unsafe("New state directory has unexpected entries")
        if self.database_fd is not None:
            info = os.fstat(self.database_fd)
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or retained._identity(info) != self.database_identity
                    or retained._identity(self.directory.stat("state.sqlite3"))
                    != self.database_identity):
                raise _unsafe("New state database identity changed")
            retained._private(self.database_fd, info, directory=False)
        if complete and not self.initialized:
            raise _unsafe("New state bootstrap is incomplete")
        self.directory.verify()

    @contextmanager
    def create_database(self, path, schema):
        if Path(path) != self.path / "state.sqlite3" or self.started:
            raise _unsafe("One exact new project database is required")
        self.started = True
        self.verify()
        connection = sqlite3.connect(":memory:", timeout=5, isolation_level=None)
        def close_memory():
            try:
                if connection.in_transaction:
                    connection.rollback()
            finally:
                connection.close()
        with retained._on_exit(close_memory):
            try:
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("BEGIN IMMEDIATE")
                for statement in schema.split(";"):
                    if statement.strip():
                        connection.execute(statement)
                yield connection
                self.verify()
                connection.commit()
                size = (connection.execute("PRAGMA page_count").fetchone()[0]
                        * connection.execute("PRAGMA page_size").fetchone()[0])
                if not 0 < size <= MAX_BOOTSTRAP_BYTES:
                    raise _unsafe("New state bootstrap exceeds its byte bound")
                raw = connection.serialize()
                if len(raw) != size:
                    raise _unsafe("New state serialized length differs")
            except sqlite3.Error as exc:
                code = ("STATE_BUSY" if getattr(exc, "sqlite_errorcode", 0)
                        in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                        else "STATE_UNAVAILABLE")
                raise CoreError(code, "Local state transaction failed") from exc
        self.verify()
        descriptor = os.open(
            "state.sqlite3",
            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600, dir_fd=self.directory._fd,
        )
        # Register ownership immediately, before metadata/ACL operations can fail.
        self.database_fd = descriptor
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
            raise _unsafe("New database is not one owned regular file")
        # Only this new O_EXCL descriptor is normalized, never an existing leaf.
        os.fchmod(descriptor, 0o600)
        self.database_identity = retained._identity(os.fstat(descriptor))
        self.verify()
        view = memoryview(raw)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("New state database write made no progress")
            view = view[written:]
        os.fsync(descriptor)
        self.verify()
        if (os.fstat(descriptor).st_size != len(raw)
                or os.pread(descriptor, len(raw) + 1, 0) != raw):
            raise _unsafe("New state database readback differs")
        self.verify()
        # Only after all caller bootstrap code has returned does the ordinary
        # SQLite VFS reopen the file for WAL initialization. This short named
        # reopen has pre/post identity checks, not hostile same-UID isolation.
        connection = sqlite3.connect(path)
        with retained._on_exit(connection.close):
            if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
                raise _unsafe("New state database did not enter WAL mode")
        self.verify()
        os.fsync(descriptor)
        self.directory.sync()
        self.initialized = True
        self.verify(complete=True)

    def close(self):
        self.directory._closed = True
        if self.database_fd is not None:
            descriptor, self.database_fd = self.database_fd, None
            os.close(descriptor)


@contextmanager
def _new_private_root(path):
    """Native POSIX primitive; the production caller admits Linux only.

    Existing directories are never opened for repair. On every failure preserve
    the new directory as an unregistered orphan and close only our descriptors.
    No inode-check/unlink race can remove a foreign replacement during cleanup.
    """
    path = Path(path)
    name = retained._name(path.name)
    with retained.open_directory(path.parent) as parent:
        _admit_parent(parent)
        os.mkdir(name, mode=0o700, dir_fd=parent._fd)
        os.fsync(parent._fd)
        descriptor = os.open(
            name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent._fd,
        )
        root = None
        def close():
            try:
                if root is not None:
                    root.close()
            finally:
                os.close(descriptor)
        with retained._on_exit(close):
            info = os.fstat(descriptor)
            if info.st_dev != os.fstat(parent._fd).st_dev:
                raise _unsafe("New state root filesystem differs")
            directory = retained.Directory(
                descriptor,
                [*parent._chain, (descriptor, parent._fd, name, retained._identity(info))],
                private=True,
            )
            retained._local_filesystem(descriptor)
            root = _OwnedStateRoot(path, directory)
            root.verify()
            with retained._on_exit(root.verify):
                yield root


@contextmanager
def new_linux_private_state(path):
    """Production opt-in: a new Linux project state root only."""
    if sys.platform != "linux":
        raise CoreError("PRIVATE_STATE_PLATFORM_UNSUPPORTED", "Private state bootstrap requires Linux")
    with _new_private_root(path) as root:
        yield root
