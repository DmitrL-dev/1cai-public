"""Owned Win32 Job execution, using suspended creation and explicit handle lists.

The job bounds aggregate committed memory, not RSS. Pipe collectors retain at
most their byte budget and keep draining until the owned job has terminated.
No breakaway flags are enabled. This is process containment, not an OS sandbox.

Contracts: Microsoft Learn /windows/win32/procthread/job-objects,
CreateProcessW, UpdateProcThreadAttribute, JOBOBJECT_EXTENDED_LIMIT_INFORMATION.
"""

from collections.abc import Callable, Mapping, Sequence
import ctypes as c
from ctypes import wintypes as w
from dataclasses import dataclass
import math
import os
from pathlib import Path
import subprocess
import threading
import time


class ProcessFailure(Exception):
    """Bounded machine reason, without candidate, command or output details."""

    def __init__(self, code: str):
        self.code = code
        self.cleanup_failed = False
        self.cleanup_lease = None
        super().__init__(code)


@dataclass(frozen=True)
class ProcessLimits:
    wall_seconds: float = 60
    cleanup_seconds: float = 5
    stream_bytes: int = 1024 * 1024
    active_processes: int = 4
    job_memory_bytes: int = 1024 * 1024 * 1024

    def __post_init__(self):
        for value, maximum in (
            (self.wall_seconds, 60),
            (self.cleanup_seconds, 5),
        ):
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 < value <= maximum
            ):
                raise ValueError("Invalid process time limit")
        for value, maximum in (
            (self.stream_bytes, 1024 * 1024),
            (self.active_processes, 4),
            (self.job_memory_bytes, 1024 * 1024 * 1024),
        ):
            if type(value) is not int or not 0 < value <= maximum:
                raise ValueError("Invalid process resource limit")


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int
    stdout: bytes
    stderr: bytes
    pid: int


class _Security(c.Structure):
    _fields_ = [("length", w.DWORD), ("descriptor", c.c_void_p), ("inherit", w.BOOL)]


class _Startup(c.Structure):
    _fields_ = [
        ("cb", w.DWORD),
        ("reserved", w.LPWSTR),
        ("desktop", w.LPWSTR),
        ("title", w.LPWSTR),
        ("x", w.DWORD),
        ("y", w.DWORD),
        ("x_size", w.DWORD),
        ("y_size", w.DWORD),
        ("x_count", w.DWORD),
        ("y_count", w.DWORD),
        ("fill", w.DWORD),
        ("flags", w.DWORD),
        ("show", w.WORD),
        ("reserved_size", w.WORD),
        ("reserved_bytes", c.c_void_p),
        ("stdin", w.HANDLE),
        ("stdout", w.HANDLE),
        ("stderr", w.HANDLE),
    ]


class _StartupEx(c.Structure):
    _fields_ = [("startup", _Startup), ("attributes", c.c_void_p)]


class _Process(c.Structure):
    _fields_ = [
        ("process", w.HANDLE),
        ("thread", w.HANDLE),
        ("pid", w.DWORD),
        ("tid", w.DWORD),
    ]


class _BasicLimits(c.Structure):
    _fields_ = [
        ("process_time", c.c_int64),
        ("job_time", c.c_int64),
        ("flags", w.DWORD),
        ("min_working_set", c.c_size_t),
        ("max_working_set", c.c_size_t),
        ("active_processes", w.DWORD),
        ("affinity", c.c_size_t),
        ("priority", w.DWORD),
        ("scheduling", w.DWORD),
    ]


class _Io(c.Structure):
    _fields_ = [
        (name, c.c_uint64)
        for name in (
            "reads",
            "writes",
            "other",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class _ExtendedLimits(c.Structure):
    _fields_ = [
        ("basic", _BasicLimits),
        ("io", _Io),
        ("process_memory", c.c_size_t),
        ("job_memory", c.c_size_t),
        ("peak_process_memory", c.c_size_t),
        ("peak_job_memory", c.c_size_t),
    ]


class _Accounting(c.Structure):
    _fields_ = [
        ("user", c.c_int64),
        ("kernel", c.c_int64),
        ("period_user", c.c_int64),
        ("period_kernel", c.c_int64),
        ("faults", w.DWORD),
        ("total", w.DWORD),
        ("active", w.DWORD),
        ("terminated", w.DWORD),
    ]


class _Native:
    def __init__(self):
        if os.name != "nt":
            raise ProcessFailure("BSL_PLATFORM_UNSUPPORTED")
        self.api = c.WinDLL("kernel32", use_last_error=True)
        self.uncertain_setup_handles = []
        signatures = {
            "CreateJobObjectW": ([c.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": (
                [w.HANDLE, c.c_int, c.c_void_p, w.DWORD],
                w.BOOL,
            ),
            "QueryInformationJobObject": (
                [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p],
                w.BOOL,
            ),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
            "IsProcessInJob": ([w.HANDLE, w.HANDLE, c.POINTER(w.BOOL)], w.BOOL),
            "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "CreatePipe": (
                [
                    c.POINTER(w.HANDLE),
                    c.POINTER(w.HANDLE),
                    c.POINTER(_Security),
                    w.DWORD,
                ],
                w.BOOL,
            ),
            "SetHandleInformation": ([w.HANDLE, w.DWORD, w.DWORD], w.BOOL),
            "CreateFileW": (
                [
                    w.LPCWSTR,
                    w.DWORD,
                    w.DWORD,
                    c.POINTER(_Security),
                    w.DWORD,
                    w.DWORD,
                    w.HANDLE,
                ],
                w.HANDLE,
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
                    c.POINTER(_Process),
                ],
                w.BOOL,
            ),
            "ResumeThread": ([w.HANDLE], w.DWORD),
            "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
            "GetExitCodeProcess": ([w.HANDLE, c.POINTER(w.DWORD)], w.BOOL),
            "ReadFile": (
                [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p],
                w.BOOL,
            ),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result

    def check(self, value):
        if not value:
            raise ProcessFailure("BSL_PROCESS_FAILED")
        return value

    def close(self, handle):
        self.check(self.api.CloseHandle(handle))

    def _close_after_failure(self, *handles):
        for handle in handles:
            try:
                self.close(handle)
            except BaseException:
                self.uncertain_setup_handles.append(handle)

    def job(self, limits):
        job = self.check(self.api.CreateJobObjectW(None, None))
        try:
            info = _ExtendedLimits()
            info.basic.flags = (
                0x2000 | 0x8 | 0x200
            )  # kill on close, active count, job commit
            info.basic.active_processes = limits.active_processes
            info.job_memory = limits.job_memory_bytes
            self.check(
                self.api.SetInformationJobObject(job, 9, c.byref(info), c.sizeof(info))
            )
            return job
        except BaseException:
            self._close_after_failure(job)
            raise

    def pipe(self):
        read, write = w.HANDLE(), w.HANDLE()
        security = _Security(c.sizeof(_Security), None, True)
        self.check(
            self.api.CreatePipe(c.byref(read), c.byref(write), c.byref(security), 65536)
        )
        try:
            self.check(self.api.SetHandleInformation(read, 1, 0))
        except BaseException:
            self._close_after_failure(read, write)
            raise
        return read.value, write.value

    def null_input(self):
        security = _Security(c.sizeof(_Security), None, True)
        handle = self.api.CreateFileW(
            "NUL", 0x80000000, 3, c.byref(security), 3, 0, None
        )
        if handle == c.c_void_p(-1).value:
            raise ProcessFailure("BSL_PROCESS_FAILED")
        return handle

    def create_suspended(self, argv, cwd, env, stdin, stdout, stderr):
        size = c.c_size_t()
        self.api.InitializeProcThreadAttributeList(None, 1, 0, c.byref(size))
        if not 0 < size.value < 65536:
            raise ProcessFailure("BSL_PROCESS_FAILED")
        attributes = c.create_string_buffer(size.value)
        self.check(
            self.api.InitializeProcThreadAttributeList(attributes, 1, 0, c.byref(size))
        )
        try:
            handles = (w.HANDLE * 3)(stdin, stdout, stderr)
            self.check(
                self.api.UpdateProcThreadAttribute(
                    attributes, 0, 0x20002, handles, c.sizeof(handles), None, None
                )
            )
            startup = _StartupEx()
            startup.startup.cb = c.sizeof(startup)
            startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
            startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = (
                stdin,
                stdout,
                stderr,
            )
            startup.attributes = c.cast(attributes, c.c_void_p)
            command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
            environment = c.create_unicode_buffer(
                "\0".join(
                    f"{k}={v}"
                    for k, v in sorted(env.items(), key=lambda p: p[0].upper())
                )
                + "\0\0"
            )
            process = _Process()
            self.check(
                self.api.CreateProcessW(
                    argv[0],
                    command,
                    None,
                    None,
                    True,
                    0x4 | 0x400 | 0x80000 | 0x08000000,
                    environment,
                    str(cwd),
                    c.byref(startup),
                    c.byref(process),
                )
            )
            return process
        finally:
            self.api.DeleteProcThreadAttributeList(attributes)

    def assign(self, job, process):
        self.check(self.api.AssignProcessToJobObject(job, process))

    def resume(self, thread):
        if self.api.ResumeThread(thread) == 0xFFFFFFFF:
            raise ProcessFailure("BSL_PROCESS_FAILED")

    def active(self, job):
        info = _Accounting()
        self.check(
            self.api.QueryInformationJobObject(
                job, 1, c.byref(info), c.sizeof(info), None
            )
        )
        return info.active

    def terminate(self, job, process):
        member = w.BOOL()
        if process:
            self.check(self.api.IsProcessInJob(process, job, c.byref(member)))
        self.check(self.api.TerminateJobObject(job, 1))
        # Assigned processes are already terminating asynchronously. A duplicate
        # TerminateProcess may race and return ERROR_ACCESS_DENIED before their
        # process handle becomes signaled. Only an unassigned suspended root
        # needs the separate operation; cleanup still waits for both witnesses.
        if process and not member.value and not self.stopped(process):
            self.check(self.api.TerminateProcess(process, 1))

    def stopped(self, process):
        result = self.api.WaitForSingleObject(process, 0)
        if result not in (0, 258):
            raise ProcessFailure("BSL_PROCESS_FAILED")
        return result == 0

    def exit_code(self, process):
        result = w.DWORD()
        self.check(self.api.GetExitCodeProcess(process, c.byref(result)))
        return result.value

    def read(self, handle):
        buffer, length = c.create_string_buffer(65536), w.DWORD()
        if not self.api.ReadFile(handle, buffer, len(buffer), c.byref(length), None):
            if c.get_last_error() == 109:  # ERROR_BROKEN_PIPE after last writer closed
                return b""
            raise ProcessFailure("BSL_PROCESS_FAILED")
        return buffer.raw[: length.value]


class _Drain:
    def __init__(self, native, handle, maximum):
        self.native, self.handle, self.maximum = native, handle, maximum
        self.data = bytearray()
        self.exceeded = threading.Event()
        self.failed = threading.Event()
        self.thread = threading.Thread(
            target=self._run, name="bsl-output-drain", daemon=True
        )

    def _run(self):
        try:
            while chunk := self.native.read(self.handle):
                remaining = self.maximum - len(self.data)
                self.data.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.exceeded.set()
        except BaseException:
            self.failed.set()


class _CleanupLease:
    """Retained ownership after unconfirmed cleanup; never retries ambiguous closes."""

    def __init__(self, native, retained_resources):
        self.native = native
        self.retained_resources = retained_resources
        self.owned = []
        self.uncertain_handles = []
        self.drains = []
        self.process = None
        self.job = None

    def own(self, handle):
        self.owned.append(handle)
        return handle

    def close(self, handle):
        # A failing close can have closed the OS handle before raising. Remove
        # first so later cleanup cannot close an unrelated reused handle value.
        self.owned.remove(handle)
        try:
            self.native.close(handle)
        except BaseException:
            self.uncertain_handles.append(handle)
            raise

    def cleanup(self, seconds):
        end = time.monotonic() + seconds
        process, native = self.process, self.native
        if process is not None:
            if not native.stopped(process.process) or native.active(self.job):
                native.terminate(self.job, process.process)
            while not native.stopped(process.process) or native.active(self.job):
                if time.monotonic() >= end:
                    raise ProcessFailure("BSL_CLEANUP_FAILED")
                time.sleep(0.01)
            for drain in self.drains:
                drain.thread.join(max(0, end - time.monotonic()))
                if drain.thread.is_alive():
                    # CloseHandle on a pipe with pending synchronous ReadFile can
                    # block until the still-owned writer exits. Keep its handle.
                    raise ProcessFailure("BSL_CLEANUP_FAILED")
        failure = None
        for handle in list(reversed(self.owned)):
            try:
                self.close(handle)
            except BaseException as exc:
                failure = failure or exc
        if failure or self.uncertain_handles:
            raise ProcessFailure("BSL_CLEANUP_FAILED") from None
        self.retained_resources = ()


class WindowsProcessOwner:
    """One startup-owned lane, permanently quarantined by unconfirmed cleanup.

    The adapter must keep this owner for its entire lifetime. A poisoned owner
    retains the process, drains and caller's input/runtime lease even when an
    authorization exception masks the process failure. Restart is the recovery
    boundary; this class deliberately has no unsafe handle-retry/reset method.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._cleanup_lease = None

    @property
    def poisoned(self):
        return self._cleanup_lease is not None

    @property
    def cleanup_lease(self):
        return self._cleanup_lease

    def check_available(self):
        """Call before runtime or attempt IO; run_process checks again under lock."""
        if self.poisoned:
            error = ProcessFailure("BSL_OWNER_QUARANTINED")
            error.cleanup_failed = True
            error.cleanup_lease = self._cleanup_lease
            raise error
        if self._lock.locked():
            raise ProcessFailure("BSL_OWNER_BUSY")

    def run_process(
        self,
        argv,
        *,
        cwd,
        env,
        authorize,
        limits=ProcessLimits(),
        monitor=None,
        _native=None,
        retained_resources=(),
    ):
        self.check_available()
        if not self._lock.acquire(blocking=False):
            raise ProcessFailure("BSL_OWNER_BUSY")
        try:
            if self.poisoned:
                self.check_available()
            return _run_owned(
                self,
                argv,
                cwd=cwd,
                env=env,
                authorize=authorize,
                limits=limits,
                monitor=monitor,
                _native=_native,
                retained_resources=retained_resources,
            )
        finally:
            self._lock.release()


def _run_owned(
    owner, argv, *, cwd, env, authorize, limits, monitor, _native, retained_resources
):
    if (
        not argv
        or any(not isinstance(v, str) or "\0" in v for v in argv)
        or not Path(argv[0]).is_absolute()
    ):
        raise ValueError("Executable and arguments must be explicit")
    if not isinstance(cwd, Path) or not cwd.is_absolute() or not callable(authorize):
        raise ValueError("Explicit working directory and authorization required")
    if any(
        not isinstance(k, str)
        or not isinstance(v, str)
        or not k
        or "=" in k
        or "\0" in k + v
        for k, v in env.items()
    ):
        raise ValueError("Invalid child environment")
    started = time.monotonic()
    native = _native or _Native()
    lease = _CleanupLease(native, retained_resources)
    primary = None
    result = None
    try:
        lease.job = lease.own(native.job(limits))
        out_read, out_write = native.pipe()
        lease.own(out_read)
        lease.own(out_write)
        err_read, err_write = native.pipe()
        lease.own(err_read)
        lease.own(err_write)
        stdin = lease.own(native.null_input())
        authorize()
        if time.monotonic() - started >= limits.wall_seconds:
            raise ProcessFailure("BSL_TIMEOUT")
        process = native.create_suspended(argv, cwd, env, stdin, out_write, err_write)
        lease.process = process
        lease.own(process.process)
        lease.own(process.thread)
        native.assign(lease.job, process.process)
        for handle in (stdin, out_write, err_write):
            lease.close(handle)
        for handle in (out_read, err_read):
            drain = _Drain(native, handle, limits.stream_bytes)
            drain.thread.start()
            lease.drains.append(drain)
        authorize()
        if time.monotonic() - started >= limits.wall_seconds:
            raise ProcessFailure("BSL_TIMEOUT")
        native.resume(process.thread)
        lease.close(process.thread)
        while True:
            if monitor:
                monitor()
            if any(d.exceeded.is_set() for d in lease.drains):
                raise ProcessFailure("BSL_RESOURCE_LIMIT")
            if any(d.failed.is_set() for d in lease.drains):
                raise ProcessFailure("BSL_PROCESS_FAILED")
            if native.stopped(process.process) and native.active(lease.job) == 0:
                break
            if time.monotonic() - started >= limits.wall_seconds:
                raise ProcessFailure("BSL_TIMEOUT")
            time.sleep(0.01)
        result = native.exit_code(process.process)
    except BaseException as exc:
        primary = exc
    lease.uncertain_handles.extend(native.uncertain_setup_handles)
    try:
        lease.cleanup(limits.cleanup_seconds)
    except BaseException:
        owner._cleanup_lease = lease
        if primary is None:
            primary = ProcessFailure("BSL_CLEANUP_FAILED")
        primary.cleanup_failed = True
        primary.cleanup_lease = lease
    if primary is not None:
        raise primary
    if any(d.exceeded.is_set() for d in lease.drains):
        raise ProcessFailure("BSL_RESOURCE_LIMIT")
    if any(d.failed.is_set() for d in lease.drains):
        raise ProcessFailure("BSL_PROCESS_FAILED")
    return ProcessResult(
        result,
        bytes(lease.drains[0].data),
        bytes(lease.drains[1].data),
        lease.process.pid,
    )


_DEFAULT_OWNER = WindowsProcessOwner()


def run_process(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    authorize: Callable[[], None],
    limits: ProcessLimits = ProcessLimits(),
    monitor: Callable[[], None] | None = None,
    _native=None,
) -> ProcessResult:
    """Convenience lane retaining poisoned ownership until process restart.

    Adapters use their own startup-lived WindowsProcessOwner and pass their
    runtime/input resources to its run_process method for uncertain cleanup.
    """
    return _DEFAULT_OWNER.run_process(
        argv,
        cwd=cwd,
        env=env,
        authorize=authorize,
        limits=limits,
        monitor=monitor,
        _native=_native,
    )
