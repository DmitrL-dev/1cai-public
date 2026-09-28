"""Bound one trusted Git child's binary stdout while reading, without threads."""
from functools import lru_cache
import math
import os
import subprocess
import time


class GitOutputLimitExceeded(Exception):
    def __init__(self, limit, stdout):
        super().__init__("Git stdout exceeds capture limit")
        self.limit, self.stdout = limit, stdout


@lru_cache(maxsize=1)
def _peek_api():
    import ctypes
    from ctypes import wintypes

    function = ctypes.WinDLL("kernel32", use_last_error=True, winmode=0x800).PeekNamedPipe
    function.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    function.restype = wintypes.BOOL
    return function


def _read_available(stream, count):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt

        available = wintypes.DWORD()
        if not _peek_api()(msvcrt.get_osfhandle(stream.fileno()), None, 0,
                           None, ctypes.byref(available), None):
            error = ctypes.get_last_error()
            if error in (109, 232):  # BROKEN_PIPE / NO_DATA
                return b""
            raise ctypes.WinError(error)
        if not available.value:
            return None
        return os.read(stream.fileno(), min(count, available.value))
    try:
        return os.read(stream.fileno(), count)
    except BlockingIOError:
        return None


def capture_git(command, *, env, max_stdout, timeout=10):
    """Capture at most the bound plus one overflow byte and reap this child.

    No concurrent read uses this pipe. The initial OS spawn and cleanup are not
    a hard wall-clock service deadline. Descendant/controller-crash ownership
    remains outside this same-child boundary.
    """
    if type(max_stdout) is not int or not 0 <= max_stdout <= 64 * 1024**2:
        raise ValueError("Invalid Git stdout bound")
    if (type(timeout) not in (int, float) or not math.isfinite(timeout)
            or not 0 < timeout <= 60):
        raise ValueError("Invalid Git capture timeout")
    process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    output = bytearray()
    deadline = time.monotonic() + timeout
    try:
        if os.name != "nt":
            os.set_blocking(process.stdout.fileno(), False)
        while True:
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(command, timeout, output=bytes(output))
            # Observe exit before peeking: a late write after an empty peek must
            # get another drain pass, even if the child exits in between.
            code = process.poll()
            chunk = _read_available(process.stdout, min(65536, max_stdout + 1 - len(output)))
            if chunk:
                output.extend(chunk)
                if len(output) > max_stdout:
                    raise GitOutputLimitExceeded(max_stdout, bytes(output))
                continue
            if code is not None:
                return subprocess.CompletedProcess(command, code, stdout=bytes(output))
            time.sleep(min(0.01, max(0, deadline - time.monotonic())))
    finally:
        try:
            if process.poll() is None:
                process.kill()
            process.wait()
        finally:
            process.stdout.close()
