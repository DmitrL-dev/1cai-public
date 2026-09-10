"""Windows 10+ child ownership from CreateProcess, including controller crashes."""
import ctypes as c
from ctypes import wintypes as w
from functools import lru_cache
import os
import subprocess
import time

from .errors import CoreError


class _Limits(c.Structure):
    _fields_ = [
        ("process_time", c.c_int64),
        ("job_time", c.c_int64),
        ("flags", w.DWORD),
        ("minimum", c.c_size_t),
        ("maximum", c.c_size_t),
        ("processes", w.DWORD),
        ("affinity", c.c_size_t),
        ("priority", w.DWORD),
        ("scheduling", w.DWORD),
    ]


class _Extended(c.Structure):
    _fields_ = [
        ("basic", _Limits),
        ("io", c.c_uint64 * 6),
        ("process_memory", c.c_size_t),
        ("job_memory", c.c_size_t),
        ("peak_process", c.c_size_t),
        ("peak_job", c.c_size_t),
    ]


class _Accounting(c.Structure):
    _fields_ = [
        ("times", c.c_int64 * 4),
        ("faults", w.DWORD),
        ("total", w.DWORD),
        ("active", w.DWORD),
        ("terminated", w.DWORD),
    ]


class _Startup(c.Structure):
    _fields_ = [
        ("cb", w.DWORD),
        ("reserved", w.LPWSTR),
        ("desktop", w.LPWSTR),
        ("title", w.LPWSTR),
        ("x", w.DWORD),
        ("y", w.DWORD),
        ("xsize", w.DWORD),
        ("ysize", w.DWORD),
        ("xchars", w.DWORD),
        ("ychars", w.DWORD),
        ("fill", w.DWORD),
        ("flags", w.DWORD),
        ("show", w.WORD),
        ("reserved_count", w.WORD),
        ("reserved_bytes", c.c_void_p),
        ("stdin", w.HANDLE),
        ("stdout", w.HANDLE),
        ("stderr", w.HANDLE),
    ]


class _StartupEx(c.Structure):
    _fields_ = [("startup", _Startup), ("attributes", c.c_void_p)]


class _ProcessInfo(c.Structure):
    _fields_ = [
        ("process", w.HANDLE),
        ("thread", w.HANDLE),
        ("pid", w.DWORD),
        ("tid", w.DWORD),
    ]


@lru_cache(maxsize=1)
def _api():
    if os.name != "nt":
        raise CoreError("CAPTURE_PLATFORM_UNSUPPORTED", "Native jobs require Windows")
    k = c.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateJobObjectW": ([c.c_void_p, w.LPCWSTR], w.HANDLE),
        "SetInformationJobObject": ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
        "QueryInformationJobObject": (
            [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p],
            w.BOOL,
        ),
        "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
        "CloseHandle": ([w.HANDLE], w.BOOL),
        "GetCurrentProcess": ([], w.HANDLE),
        "DuplicateHandle": (
            [
                w.HANDLE,
                w.HANDLE,
                w.HANDLE,
                c.POINTER(w.HANDLE),
                w.DWORD,
                w.BOOL,
                w.DWORD,
            ],
            w.BOOL,
        ),
        "InitializeProcThreadAttributeList": (
            [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)],
            w.BOOL,
        ),
        "UpdateProcThreadAttribute": (
            [
                c.c_void_p,
                w.DWORD,
                c.c_size_t,
                c.c_void_p,
                c.c_size_t,
                c.c_void_p,
                c.c_void_p,
            ],
            w.BOOL,
        ),
        "DeleteProcThreadAttributeList": ([c.c_void_p], None),
        "CreateProcessW": (
            [
                w.LPCWSTR,
                w.LPWSTR,
                c.c_void_p,
                c.c_void_p,
                w.BOOL,
                w.DWORD,
                c.c_void_p,
                w.LPCWSTR,
                c.POINTER(_StartupEx),
                c.POINTER(_ProcessInfo),
            ],
            w.BOOL,
        ),
        "GetExitCodeProcess": ([w.HANDLE, c.POINTER(w.DWORD)], w.BOOL),
        "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
    }
    for name, (args, result) in signatures.items():
        function = getattr(k, name)
        function.argtypes, function.restype = args, result
    return k


def _ok(value):
    if not value:
        raise c.WinError(c.get_last_error())
    return value


class OwnedJob:
    def __init__(self, name=None):
        self.handle = _ok(_api().CreateJobObjectW(None, name))
        try:
            # A new owner must never adopt a still-running orphaned tree.
            if self.active():
                raise CoreError(
                    "NATIVE_EXECUTOR_BUSY", "Native processes still occupy this project"
                )
            limits = _Extended()
            limits.basic.flags = 0x2000 | 0x8  # KILL_ON_JOB_CLOSE | ACTIVE_PROCESS
            limits.basic.processes = 32
            _ok(
                _api().SetInformationJobObject(
                    self.handle, 9, c.byref(limits), c.sizeof(limits)
                )
            )
        except BaseException:
            _api().CloseHandle(self.handle)
            self.handle = None
            raise

    def active(self):
        value = _Accounting()
        _ok(
            _api().QueryInformationJobObject(
                self.handle, 1, c.byref(value), c.sizeof(value), None
            )
        )
        return value.active

    def close(self):
        if self.handle is None:
            return
        try:
            if self.active():
                _ok(_api().TerminateJobObject(self.handle, 125))
                deadline = time.monotonic() + 15
                while self.active():
                    if time.monotonic() >= deadline:
                        raise CoreError(
                            "NATIVE_CLEANUP_TIMEOUT",
                            "Native descendants have not exited",
                        )
                    time.sleep(0.02)
        finally:
            _api().CloseHandle(self.handle)
            self.handle = None


class OwnedProcess:
    """Small poll/wait API; files are supplied by the owner, no shell or pipes."""

    def __init__(self, command, executable, stdout, stderr, *, parent_job=None):
        import msvcrt

        self.job, self.handle, self.returncode = OwnedJob(), None, None
        self.args = command
        k, duplicates, attributes = _api(), [], None
        try:
            with open(os.devnull, "rb") as stdin:
                for stream in (stdin, stdout, stderr):
                    duplicate = w.HANDLE()
                    _ok(
                        k.DuplicateHandle(
                            k.GetCurrentProcess(),
                            msvcrt.get_osfhandle(stream.fileno()),
                            k.GetCurrentProcess(),
                            c.byref(duplicate),
                            0,
                            True,
                            2,
                        )
                    )
                    duplicates.append(duplicate.value)
            handles = (w.HANDLE * len(duplicates))(*duplicates)
            jobs = ([parent_job.handle] if parent_job else []) + [self.job.handle]
            job_handles = (w.HANDLE * len(jobs))(*jobs)
            size = c.c_size_t()
            k.InitializeProcThreadAttributeList(None, 2, 0, c.byref(size))
            buffer = c.create_string_buffer(size.value)
            _ok(k.InitializeProcThreadAttributeList(buffer, 2, 0, c.byref(size)))
            attributes = buffer
            _ok(
                k.UpdateProcThreadAttribute(
                    buffer, 0, 0x20002, handles, c.sizeof(handles), None, None
                )
            )
            _ok(
                k.UpdateProcThreadAttribute(
                    buffer, 0, 0x2000D, job_handles, c.sizeof(job_handles), None, None
                )
            )
            startup = _StartupEx()
            startup.startup.cb = c.sizeof(startup)
            startup.startup.flags = 0x100 | 1  # USESTDHANDLES | USESHOWWINDOW
            (
                startup.startup.stdin,
                startup.startup.stdout,
                startup.startup.stderr,
            ) = duplicates
            startup.attributes = c.cast(buffer, c.c_void_p)
            info = _ProcessInfo()
            _ok(
                k.CreateProcessW(
                    str(executable),
                    c.create_unicode_buffer(command),
                    None,
                    None,
                    True,
                    0x80000 | 0x08000000,
                    None,
                    None,
                    c.byref(startup),
                    c.byref(info),
                )
            )
            self.handle, self.pid = info.process, info.pid
            k.CloseHandle(info.thread)
        except BaseException:
            self.close()
            raise
        finally:
            if attributes is not None:
                k.DeleteProcThreadAttributeList(attributes)
            for handle in duplicates:
                k.CloseHandle(handle)

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        state = _api().WaitForSingleObject(self.handle, 0)
        if state == 258:
            return None
        if state != 0:
            raise c.WinError(c.get_last_error())
        value = w.DWORD()
        _ok(_api().GetExitCodeProcess(self.handle, c.byref(value)))
        self.returncode = value.value
        return self.returncode

    def wait(self, timeout):
        state = _api().WaitForSingleObject(
            self.handle, min(int(timeout * 1000), 0xFFFFFFFE)
        )
        if state == 258:
            raise subprocess.TimeoutExpired(self.args, timeout)
        return self.poll()

    def close(self):
        try:
            self.job.close()
            if self.handle:
                self.wait(15)
        finally:
            if self.handle:
                _api().CloseHandle(self.handle)
                self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
