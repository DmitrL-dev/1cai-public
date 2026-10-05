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
    """Hold the account-owned private parent; no path-check then file reopen."""
    import os
    from pathlib import Path
    import stat

    path = _default_identity_profile() if profile is None else Path(profile)
    path = path.absolute()
    if create:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise OSError("Local identity directory must be owned by the account and mode 0700")
        return descriptor, path.name
    except BaseException:
        os.close(descriptor)
        raise


def _linux_profile_principal(profile):
    import json
    import os
    import stat
    from uuid import UUID

    parent, name = _profile_parent(profile)
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or not 1 <= info.st_size <= 1024
            ):
                raise OSError("Invalid local identity file ownership, type or permissions")
            raw = os.read(descriptor, 1025)
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
            return Principal(
                f"linux-local:{value['namespace']}:uid:{os.geteuid()}", "local_os"
            )
        finally:
            os.close(descriptor)
    finally:
        os.close(parent)


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

    if _platform != "linux":
        raise CoreError("LOCAL_IDENTITY_UNAVAILABLE", "Profile bootstrap requires Linux")
    parent = None
    temporary = None
    try:
        parent, name = _profile_parent(profile, create=True)
        candidate_name = ".rentgen-identity-" + uuid4().hex + ".tmp"
        value = {
            "schema": 1, "kind": "rentgen.local-account",
            "namespace": str(uuid4()), "uid": os.geteuid(),
        }
        descriptor = os.open(
            candidate_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600, dir_fd=parent,
        )
        temporary = candidate_name  # Cleanup owns only a successfully created file.
        try:
            os.fchmod(descriptor, 0o600)
            raw = _profile_bytes(value)
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(descriptor)
        finally:
            os.close(descriptor)
        _publish_identity_profile(parent, temporary, name)
        temporary = None
        os.fsync(parent)
        return _linux_profile_principal(profile)
    except (OSError, ValueError, KeyError, RecursionError) as exc:
        raise CoreError(
            "LOCAL_IDENTITY_UNAVAILABLE",
            "Cannot initialize local identity; use a separate private profile directory and never overwrite an existing profile",
        ) from exc
    finally:
        if parent is not None:
            try:
                if temporary is not None:
                    try:
                        os.unlink(temporary, dir_fd=parent)
                    except FileNotFoundError:
                        pass
            finally:
                os.close(parent)


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
