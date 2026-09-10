"""Trusted local CLI/stdio identity from the Windows *process* access token.

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
