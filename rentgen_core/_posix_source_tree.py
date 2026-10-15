"""Verified POSIX directory capabilities and copied retained bytes.

Descriptors confine operations; they are not Windows deny-write/delete leases.
Concurrent namespace or file mutation is rejected when observed. Consumers use
the returned immutable bytes, never reopen the verified pathname. This is not a
filesystem-wide snapshot or protection against a malicious same-UID process.
"""

from contextlib import contextmanager
import ctypes
import errno
import os
from pathlib import Path
import stat
import sys
from uuid import uuid4

from .errors import CoreError

MAX_BYTES = 256 * 1024**2
MAX_ENTRIES = 100_000
MAX_COMPONENTS = 256


def _unsafe(message="POSIX retained path is unsafe or changed"):
    return CoreError("SNAPSHOT_CORRUPT", message)


def _name(value):
    if (
        type(value) is not str or value in {"", ".", ".."}
        or "/" in value or "\x00" in value
        or len(os.fsencode(value)) > 255
    ):
        raise _unsafe("One bounded directory entry name is required")
    return value


def _identity(info):
    return info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid


def _stamp(info):
    return (*_identity(info), info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, getattr(info, "st_flags", 0))


def _libc():
    return ctypes.CDLL(None, use_errno=True)


@contextmanager
def _on_exit(finalize):
    """Strict success checks; preserve only exceptions from this operation body."""
    try:
        yield
    except BaseException:
        try:
            finalize()
        except BaseException:
            pass  # The operation already failed; never replace its denial/cause.
        raise
    else:
        finalize()  # An unrelated caller's handled exception is not a failure here.


def _close_all(chain):
    failure = None
    for fd, *_ in reversed(chain):
        try:
            os.close(fd)
        except OSError as exc:
            failure = failure or exc
    if failure is not None:
        raise failure


def _local_filesystem(fd):
    """Allow explicitly selected local filesystem semantics, fail closed otherwise."""
    library = _libc()
    raw = ctypes.create_string_buffer(4096)
    if sys.platform == "darwin":
        function = library.fstatfs64
    elif sys.platform == "linux":
        function = library.fstatfs
    else:
        raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "No POSIX filesystem adapter")
    function.argtypes = [ctypes.c_int, ctypes.c_void_p]
    function.restype = ctypes.c_int
    if function(fd, raw) != 0:
        raise OSError(ctypes.get_errno(), "Cannot identify retained filesystem")
    if sys.platform == "darwin":
        # Darwin statfs64 (sys/mount.h): flags at 64, f_fstypename[16] at 72.
        local = bool(int.from_bytes(raw.raw[64:68], sys.byteorder) & 0x1000)
        supported = local and raw.raw[72:88].split(b"\0", 1)[0] in {b"apfs", b"hfs"}
    else:
        kind = ctypes.c_long.from_buffer(raw).value & 0xFFFFFFFF
        supported = kind in {0xEF53, 0x58465342, 0x9123683E, 0x01021994, 0x794C7630}
    if not supported:
        raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "Unsupported retained filesystem")


def _private(fd, info, *, directory):
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != (0o700 if directory else 0o600):
        raise _unsafe("Private retained object ownership or permissions differ")
    if sys.platform == "darwin":
        library = _libc()
        get_acl = library.acl_get_fd_np
        get_acl.argtypes = [ctypes.c_int, ctypes.c_int]
        get_acl.restype = ctypes.c_void_p
        get_entry = library.acl_get_entry
        get_entry.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)]
        get_entry.restype = ctypes.c_int
        free = library.acl_free
        free.argtypes, free.restype = [ctypes.c_void_p], ctypes.c_int
        ctypes.set_errno(0)
        acl = get_acl(fd, 0x100)  # ACL_TYPE_EXTENDED, never path based.
        if not acl:
            # Darwin reports ENOENT when this held, fstat-verified object has no ACL.
            if ctypes.get_errno() == errno.ENOENT:
                return
            raise _unsafe("Cannot inspect private retained ACL")
        try:
            valid = library.acl_valid
            valid.argtypes, valid.restype = [ctypes.c_void_p], ctypes.c_int
            if valid(acl) != 0:
                raise _unsafe("Invalid private retained ACL")
            entry = ctypes.c_void_p()
            ctypes.set_errno(0)
            result = get_entry(acl, 0, ctypes.byref(entry))
            if result != -1 or ctypes.get_errno() != errno.EINVAL:
                raise _unsafe("Extended ACL is not admitted for private retained objects")
        finally:
            free(acl)
    else:
        names = ("system.posix_acl_access", "system.posix_acl_default") if directory else ("system.posix_acl_access",)
        for name in names:
            try:
                os.getxattr(fd, name)
            except OSError as exc:
                if exc.errno not in {errno.ENODATA, errno.ENOTSUP}:
                    raise
            else:
                raise _unsafe("Extended ACL is not admitted for private retained objects")


def _rename_exclusive(fd, source, destination):
    library = _libc()
    if sys.platform == "linux":
        function, flag = library.renameat2, 1  # RENAME_NOREPLACE
    elif sys.platform == "darwin":
        function, flag = library.renameatx_np, 0x4  # RENAME_EXCL, not Linux's 1.
    else:
        raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "No exclusive POSIX publication")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(fd, os.fsencode(source), fd, os.fsencode(destination), flag) != 0:
        code = ctypes.get_errno()
        raise OSError(code, "Exclusive retained publication failed")


class Directory:
    """An operation-scoped directory capability. Do not retain it after context exit."""

    def __init__(self, fd, chain, *, private=False, private_ancestors=()):
        self._fd, self._chain, self._private = fd, chain, private
        self._private_ancestors = tuple(private_ancestors) + ((fd,) if private else ())
        self._closed = False

    def verify(self):
        if self._closed:
            raise _unsafe("Directory capability is closed")
        for fd, parent, name, identity in self._chain:
            current = os.fstat(fd)
            if not stat.S_ISDIR(current.st_mode) or _identity(current) != identity:
                raise _unsafe()
            if parent is not None and _identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) != identity:
                raise _unsafe()
        for fd in self._private_ancestors:
            _private(fd, os.fstat(fd), directory=True)

    @contextmanager
    def child(self, name, *, create=False, private=False):
        name = _name(name)
        self.verify()
        if create:
            try:
                os.mkdir(name, mode=0o700, dir_fd=self._fd)
            except FileExistsError:
                pass
            # Retry also confirms a child left complete by an earlier fsync error.
            os.fsync(self._fd)
        fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self._fd)
        cap = None
        def close():
            if cap is not None:
                cap._closed = True
            os.close(fd)
        with _on_exit(close):
            info = os.fstat(fd)
            if info.st_dev != os.fstat(self._fd).st_dev:
                raise _unsafe("Nested retained filesystem is not admitted")
            cap = Directory(fd, [*self._chain, (fd, self._fd, name, _identity(info))],
                            private=private, private_ancestors=self._private_ancestors)
            _local_filesystem(fd)
            cap.verify()
            with _on_exit(cap.verify):
                yield cap

    def stat(self, name):
        self.verify()
        info = os.stat(_name(name), dir_fd=self._fd, follow_symlinks=False)
        self.verify()
        return info

    def sync(self):
        """Confirm owned namespace durability, including explicit idempotent retry."""
        if not self._private:
            raise _unsafe("Sync requires a private directory capability")
        self.verify()
        os.fsync(self._fd)
        self.verify()

    def names(self, *, maximum=MAX_ENTRIES):
        if type(maximum) is not int or not 0 <= maximum <= MAX_ENTRIES:
            raise ValueError("Invalid retained inventory bound")
        self.verify()
        before = _stamp(os.fstat(self._fd))
        names = []
        # scandir(fd) duplicates the descriptor internally; no pathname reopen.
        with os.scandir(self._fd) as entries:
            for entry in entries:
                if len(names) >= maximum:
                    raise _unsafe("Retained inventory exceeds its entry bound")
                names.append(_name(entry.name))
        if _stamp(os.fstat(self._fd)) != before:
            raise _unsafe("Retained directory changed during inventory")
        self.verify()
        return sorted(names)

    @contextmanager
    def file(self, name):
        """Open a regular file read-only without create/truncate; yield binary stream."""
        name = _name(name)
        self.verify()
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        fd = os.open(name, flags, dir_fd=self._fd)
        with _on_exit(lambda: os.close(fd)):
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise _unsafe("Retained leaf must be a single-link regular file")
            if before.st_dev != os.fstat(self._fd).st_dev:
                raise _unsafe("Retained leaf filesystem differs")
            if self._private:
                _private(fd, before, directory=False)
            self.verify()
            if _stamp(self.stat(name)) != _stamp(before):
                raise _unsafe()
            stream = os.fdopen(fd, "rb", closefd=False)
            with _on_exit(stream.close):
                with _on_exit(lambda: self._verify_leaf(name, fd, before, unchanged=True)):
                    yield stream

    def _verify_leaf(self, name, fd, before, *, unchanged):
        after = os.fstat(fd)
        if (_identity(after) != _identity(before) or after.st_nlink != 1
                or (unchanged and _stamp(after) != _stamp(before))
                or _stamp(self.stat(name)) != _stamp(after)):
            raise _unsafe("Retained file changed during operation")
        if self._private:
            _private(fd, after, directory=False)
        self.verify()

    def read(self, name, maximum):
        if type(maximum) is not int or not 0 <= maximum <= MAX_BYTES:
            raise ValueError("Invalid retained byte bound")
        with self.file(name) as stream:
            before = os.fstat(stream.fileno())
            if before.st_size > maximum:
                raise _unsafe("Retained file exceeds byte bound")
            raw = stream.read(maximum + 1)
            if len(raw) > maximum or len(raw) != before.st_size:
                raise _unsafe("Retained file length differs")
        return raw

    @contextmanager
    def create_file(self, name):
        """Exclusively create private 0600 leaf; yield binary stream, flush+fsync on exit."""
        name = _name(name)
        if not self._private:
            raise _unsafe("Writes require a private directory capability")
        self.verify()
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=self._fd)
        with _on_exit(lambda: os.close(fd)):
            before = os.fstat(fd)
            _private(fd, before, directory=False)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or _stamp(self.stat(name)) != _stamp(before)):
                raise _unsafe("New owned file identity differs")
            stream = os.fdopen(fd, "wb", closefd=False)
            def finish():
                stream.flush()
                os.fsync(fd)
                self._verify_leaf(name, fd, before, unchanged=False)
                self.sync()
            with _on_exit(stream.close):
                with _on_exit(finish):
                    yield stream

    def publish_bytes(self, name, raw):
        """Publish complete bounded bytes without overwrite; failed finals are retained."""
        name = _name(name)
        if type(raw) is not bytes or len(raw) > MAX_BYTES:
            raise ValueError("Bounded immutable publication bytes required")
        temporary = ".rentgen-" + uuid4().hex + ".tmp"
        identity, published = None, False
        def cleanup():
            if identity is not None and not published:
                try:
                    if _identity(self.stat(temporary)) == identity:
                        os.unlink(temporary, dir_fd=self._fd)
                        os.fsync(self._fd)
                except FileNotFoundError:
                    pass
        with _on_exit(cleanup):
            with self.create_file(temporary) as stream:
                identity = _identity(os.fstat(stream.fileno()))
                stream.write(raw)
            self.verify()
            if _identity(self.stat(temporary)) != identity:
                raise _unsafe("Owned publication temporary identity differs")
            _rename_exclusive(self._fd, temporary, name)
            published = True
            self.sync()
            if _identity(self.stat(name)) != identity or self.read(name, len(raw)) != raw:
                raise _unsafe("Published retained bytes or identity differ")
            self.verify()


@contextmanager
def open_directory(path, *, private=False):
    """Open all absolute ancestors without following links; only final may be private."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or len(path.parts) > MAX_COMPONENTS or path.anchor != "/":
        raise _unsafe("Absolute bounded POSIX directory path is required")
    chain, cap = [], None
    def cleanup():
        if cap is not None:
            cap._closed = True
        _close_all(chain)
    with _on_exit(cleanup):
        for name in ("/", *path.parts[1:]):
            parent = chain[-1][0] if chain else None
            fd = os.open(name if parent is not None else "/",
                         os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=parent)
            # Register ownership before any fallible metadata operation.
            chain.append((fd, parent, name, None))
            info = os.fstat(fd)
            chain[-1] = (fd, parent, name, _identity(info))
        _local_filesystem(chain[-1][0])
        cap = Directory(chain[-1][0], chain, private=private)
        cap.verify()
        with _on_exit(cap.verify):
            yield cap


def read_retained(path, maximum):
    path = Path(path)
    with open_directory(path.parent) as directory:
        return directory.read(path.name, maximum)
