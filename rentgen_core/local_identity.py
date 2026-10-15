"""Trusted local CLI/stdio identity from Windows token or Linux profile ownership.

Not an authentication adapter for remote HTTP users. No environment or username
fallback is permitted. Importing this module does not load Windows libraries.
"""
import ctypes
from ctypes import wintypes
import sys

from .context import Principal
from .errors import CoreError

_platform = sys.platform


class _WindowsTokenAPI:
    def __init__(self):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.security = ctypes.WinDLL("advapi32", use_last_error=True)
        signatures = (
            (self.kernel.GetCurrentProcess, [], wintypes.HANDLE),
            (self.kernel.CloseHandle, [wintypes.HANDLE], wintypes.BOOL),
            (self.kernel.LocalFree, [ctypes.c_void_p], ctypes.c_void_p),
            (
                self.security.OpenProcessToken,
                [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)],
                wintypes.BOOL,
            ),
            (
                self.security.GetTokenInformation,
                [
                    wintypes.HANDLE,
                    ctypes.c_int,
                    ctypes.c_void_p,
                    wintypes.DWORD,
                    ctypes.POINTER(wintypes.DWORD),
                ],
                wintypes.BOOL,
            ),
            (
                self.security.ConvertSidToStringSidW,
                [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)],
                wintypes.BOOL,
            ),
        )
        for function, args, result in signatures:
            function.argtypes, function.restype = args, result

    def open_token(self):
        token = wintypes.HANDLE()
        if not self.security.OpenProcessToken(
            self.kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return token

    def token_user(self, token):
        size = wintypes.DWORD()
        result = self.security.GetTokenInformation(
            token, 1, None, 0, ctypes.byref(size)
        )
        if (
            result
            or ctypes.get_last_error() != 122
            or not ctypes.sizeof(ctypes.c_void_p) <= size.value <= 65536
        ):
            raise OSError("Invalid TokenUser buffer size")
        storage = ctypes.create_string_buffer(size.value)
        if not self.security.GetTokenInformation(
            token, 1, storage, size.value, ctypes.byref(size)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        # TOKEN_USER begins with SID_AND_ATTRIBUTES; the first field is PSID.
        sid = ctypes.cast(storage, ctypes.POINTER(ctypes.c_void_p))[0]
        if not sid:
            raise OSError("TokenUser did not contain a SID")
        return storage, sid

    def sid_string(self, sid):
        result = wintypes.LPWSTR()
        if not self.security.ConvertSidToStringSidW(sid, ctypes.byref(result)):
            raise ctypes.WinError(ctypes.get_last_error())
        return result

    def free_string(self, value):
        if self.kernel.LocalFree(ctypes.cast(value, ctypes.c_void_p)):
            raise OSError("Cannot release SID string")

    def close_token(self, token):
        if not self.kernel.CloseHandle(token):
            raise ctypes.WinError(ctypes.get_last_error())


def current_windows_principal() -> Principal:
    """Authenticate the current process for a trusted local command/stdio server."""
    if _platform != "win32":
        raise CoreError(
            "LOCAL_IDENTITY_UNAVAILABLE", "Local process identity requires Windows"
        )
    try:
        api = _WindowsTokenAPI()
        token = api.open_token()
        try:
            storage, sid = api.token_user(token)
            value = api.sid_string(sid)
            try:
                text = value.value
                if not text or not text.startswith("S-1-"):
                    raise OSError("Invalid process SID")
                return Principal("windows-sid:" + text, "local_os")
            finally:
                api.free_string(value)
        finally:
            api.close_token(token)
    except OSError as exc:
        raise CoreError(
            "LOCAL_IDENTITY_UNAVAILABLE",
            "Cannot authenticate the Windows process token",
        ) from exc


def _default_identity_profile():
    """Resolve the OS account's home, never caller-controlled HOME/USER values."""
    import os
    from pathlib import Path
    import pwd

    account = pwd.getpwuid(os.geteuid())
    home = Path(account.pw_dir)
    if account.pw_uid != os.geteuid() or not home.is_absolute():
        raise OSError("Cannot resolve the local OS account")
    return home / ".local" / "state" / "rentgen" / "local-identity" / "identity.json"


def _profile_parent(profile, *, create=False):
    """Hold a no-follow ancestor chain through the private identity directory."""
    from contextlib import contextmanager
    import os
    from pathlib import Path
    import stat
    from ._posix_source_tree import _identity, _on_exit, _close_all, _name

    path = _default_identity_profile() if profile is None else Path(profile)
    path = path.absolute()
    if path.anchor != "/" or ".." in path.parts or len(path.parts) > 256:
        raise OSError("A bounded absolute identity profile path is required")
    try:
        name = _name(path.name)
    except CoreError as exc:
        raise OSError("One bounded identity profile filename is required") from exc

    class Parent:
        def __init__(self):
            self.chain = []

        @property
        def fd(self):
            return self.chain[-1][0]

        def verify(self, *, private=True):
            for fd, parent, entry, identity in self.chain:
                info = os.fstat(fd)
                if not stat.S_ISDIR(info.st_mode) or _identity(info) != identity:
                    raise OSError("Local identity ancestor changed")
                if parent is not None and _identity(os.stat(entry, dir_fd=parent, follow_symlinks=False)) != identity:
                    raise OSError("Local identity ancestor namespace changed")
            if private:
                _identity_private(self.fd, os.fstat(self.fd), directory=True)

        def sync(self):
            self.verify()
            os.fsync(self.fd)
            self.verify()

    @contextmanager
    def opened():
        parent = Parent()
        with _on_exit(lambda: _close_all(parent.chain)):
            for entry in ("/", *path.parent.parts[1:]):
                previous = parent.fd if parent.chain else None
                if previous is not None:
                    parent.verify(private=False)
                    if create:
                        try:
                            os.mkdir(entry, mode=0o700, dir_fd=previous)
                        except FileExistsError:
                            pass
                        # Also confirm namespace durability after a prior failed fsync.
                        os.fsync(previous)
                fd = os.open(entry, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=previous)
                parent.chain.append((fd, previous, entry, None))
                parent.chain[-1] = (fd, previous, entry, _identity(os.fstat(fd)))
                parent.verify(private=False)
            parent.verify()
            with _on_exit(parent.verify):
                yield parent, name

    return opened()


def _identity_private(descriptor, info, *, directory):
    """Reuse the native descriptor ACL check without leaking snapshot errors."""
    from ._posix_source_tree import _private

    try:
        _private(descriptor, info, directory=directory)
    except CoreError as exc:
        raise OSError("Invalid local identity private ownership, permissions or ACL") from exc


def _identity_file(parent, name, descriptor, *, expected=None, empty=False):
    import os
    import stat
    from ._posix_source_tree import _stamp

    parent.verify()
    info = os.fstat(descriptor)
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or not (0 if empty else 1) <= info.st_size <= 1024):
        raise OSError("Invalid local identity file type, link count or size")
    _identity_private(descriptor, info, directory=False)
    stamp = _stamp(info)
    if expected is not None and stamp != expected:
        raise OSError("Local identity file changed")
    if _stamp(os.stat(name, dir_fd=parent.fd, follow_symlinks=False)) != stamp:
        raise OSError("Local identity file namespace changed")
    parent.verify()
    return stamp


def _read_identity(parent, name, descriptor, *, expected_raw=None):
    """Parse only copied bytes whose held file and namespace remain unchanged."""
    import json
    import os
    from uuid import UUID

    before = _identity_file(parent, name, descriptor)
    os.lseek(descriptor, 0, os.SEEK_SET)
    raw = bytearray()
    while len(raw) < 1025:
        block = os.read(descriptor, 1025 - len(raw))
        if not block:
            break
        raw.extend(block)
    raw = bytes(raw)
    _identity_file(parent, name, descriptor, expected=before)
    if len(raw) != before[6] or (expected_raw is not None and raw != expected_raw):
        raise OSError("Local identity bytes differ")
    value = json.loads(raw)
    if (
        type(value) is not dict
        or set(value) != {"schema", "kind", "namespace", "uid"}
        or type(value["schema"]) is not int or value["schema"] != 1
        or value["kind"] != "rentgen.local-account"
        or type(value["uid"]) is not int or value["uid"] != os.geteuid()
        or type(value["namespace"]) is not str
        or str(UUID(value["namespace"])) != value["namespace"]
        or UUID(value["namespace"]).version != 4
        or raw != _profile_bytes(value)
    ):
        raise ValueError("Invalid local identity document")
    _identity_file(parent, name, descriptor, expected=before)
    return Principal(f"linux-local:{value['namespace']}:uid:{os.geteuid()}", "local_os")


def _linux_profile_principal(profile):
    import os
    from ._posix_source_tree import _on_exit

    with _profile_parent(profile) as (parent, name):
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                             dir_fd=parent.fd)
        with _on_exit(lambda: os.close(descriptor)):
            principal = _read_identity(parent, name, descriptor)
    return principal


def _profile_bytes(value):
    import json

    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def _publish_identity_profile(parent, temporary, name):
    """Linux atomic no-replace rename; no two-link or partial-final-file window."""
    import os

    library = ctypes.CDLL(None, use_errno=True)
    try:
        rename = library.renameat2
    except AttributeError as exc:
        raise OSError("Atomic no-replace identity publication is unavailable") from exc
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(temporary), parent, os.fsencode(name), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def initialize_local_identity(profile=None) -> Principal:
    """Explicit Linux bootstrap only; never changes an existing identity file.

    The random namespace is a stable local ownership label, not a bearer token
    or cross-host authentication credential. Keep it separate from project data.
    Copying this profile deliberately preserves the same installation identity.
    Same-UID hostile processes, root and modified project databases are outside
    this trusted-local-adapter boundary, as with Windows process-SID adapters.
    """
    import os
    from uuid import uuid4
    from ._posix_source_tree import _identity, _on_exit

    if _platform != "linux":
        raise CoreError("LOCAL_IDENTITY_UNAVAILABLE", "Profile bootstrap requires Linux")
    try:
        with _profile_parent(profile, create=True) as (parent, name):
            parent.sync()
            temporary = ".rentgen-identity-" + uuid4().hex + ".tmp"
            raw = _profile_bytes({
                "schema": 1, "kind": "rentgen.local-account",
                "namespace": str(uuid4()), "uid": os.geteuid(),
            })
            descriptor = os.open(
                temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600, dir_fd=parent.fd,
            )
            with _on_exit(lambda: os.close(descriptor)):
                owned = _identity(os.fstat(descriptor))
                published = False

                def cleanup():
                    if not published:
                        try:
                            info = os.stat(temporary, dir_fd=parent.fd, follow_symlinks=False)
                            current = _identity(os.fstat(descriptor))
                            # Mode/ctime can change while creating our own inode.
                            if (_identity(info) == current and current[:2] == owned[:2]
                                    and current[3] == owned[3]):
                                os.unlink(temporary, dir_fd=parent.fd)
                                os.fsync(parent.fd)
                        except FileNotFoundError:
                            pass

                with _on_exit(cleanup):
                    parent.verify()
                    if _identity(os.stat(temporary, dir_fd=parent.fd, follow_symlinks=False)) != owned:
                        raise OSError("New local identity temporary namespace changed")
                    # Set the mode only on this exclusively created, held inode.
                    # Existing profiles/directories are never permission-repaired.
                    os.fchmod(descriptor, 0o600)
                    owned = _identity(os.fstat(descriptor))
                    _identity_file(parent, temporary, descriptor, empty=True)
                    written = 0
                    while written < len(raw):
                        count = os.write(descriptor, raw[written:])
                        if count <= 0:
                            raise OSError("Incomplete local identity write")
                        written += count
                    os.fsync(descriptor)
                    before = _identity_file(parent, temporary, descriptor)
                    _read_identity(parent, temporary, descriptor, expected_raw=raw)
                    _identity_file(parent, temporary, descriptor, expected=before)
                    _publish_identity_profile(parent.fd, temporary, name)
                    published = True  # A failed final sync never deletes the final identity.
                    parent.sync()
                    principal = _read_identity(parent, name, descriptor, expected_raw=raw)
        return principal
    except (OSError, ValueError, KeyError, RecursionError) as exc:
        raise CoreError(
            "LOCAL_IDENTITY_UNAVAILABLE",
            "Cannot initialize local identity; use a separate private profile directory and never overwrite an existing profile",
        ) from exc


def current_local_principal(*, identity_profile=None) -> Principal:
    """Read trusted local OS ownership; protocol payloads never select identity."""
    if _platform == "win32":
        if identity_profile is not None:
            raise CoreError("INVALID_ARGUMENT", "Windows identity comes only from its process token")
        return current_windows_principal()
    if _platform != "linux":
        raise CoreError("LOCAL_IDENTITY_UNAVAILABLE", "Local identity adapter is not qualified for this OS")
    try:
        return _linux_profile_principal(identity_profile)
    except (OSError, ValueError, KeyError, RecursionError) as exc:
        raise CoreError(
            "LOCAL_IDENTITY_UNAVAILABLE",
            "Cannot authenticate local profile ownership; initialize a separate private identity profile explicitly",
        ) from exc
