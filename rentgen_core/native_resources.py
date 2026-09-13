"""One native executor per project state, with bounded periodic disk accounting."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import shutil
import stat
import time

from ._windows_source_tree import pinned_directory, WindowsHandleOps, _retained_stamp
from .errors import CoreError
from .native_process import OwnedJob
from .snapshots import validate_operation_id

NAMESPACES = ("platform-checks", "test-runs", "metadata-runs")
RETAINED_RUN_LIMIT = 256


@contextmanager
def _file_slot(root, name, busy_code):
    import msvcrt

    root = Path(root).absolute()
    with pinned_directory(root):
        lock = root / name
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_BINARY, 0o600)
        acquired = False
        try:
            ops = WindowsHandleOps()
            handle = msvcrt.get_osfhandle(descriptor)
            if _retained_stamp(ops, handle).directory or ops.final_path(handle) != lock:
                raise CoreError("NATIVE_LOCK_INVALID", "Invalid native executor lock")
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                acquired = True
            except OSError as exc:
                raise CoreError(
                    busy_code, "Another native operation holds this project lock"
                ) from exc
            yield
        finally:
            try:
                if acquired:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            finally:
                os.close(descriptor)


@contextmanager
def project_slot(root):
    root = Path(root).absolute()
    with _file_slot(root, "native-executor.lock", "NATIVE_EXECUTOR_BUSY"):
        identity = hashlib.sha256(str(root).casefold().encode()).hexdigest()
        job = OwnedJob("Local\\RentgenCore.Native." + identity)
        try:
            yield job
        finally:
            job.close()


def reserve_run(root, run, *, limits=None):
    """Bound retained attempts before allocating any per-operation artifacts.

    Completed, failed and unknown outcomes all consume a slot indefinitely.
    Only the two synchronous native callers use this admission boundary.
    """
    root, run = Path(root).absolute(), Path(run).absolute()
    limits = DiskLimits() if limits is None else limits
    validate_operation_id(run.name)
    if run.parent.parent != root or run.parent.name not in NAMESPACES[:2]:
        raise CoreError("NATIVE_STORAGE_INVALID", "Not an owned native run")
    created = False
    try:
        with _file_slot(root, "native-admission.lock", "NATIVE_ADMISSION_BUSY"):
            with pinned_directory(run.parent):
                if run.exists():
                    raise FileExistsError(str(run))
                retained = 0
                for name in NAMESPACES:
                    parent = root / name
                    if not parent.exists():
                        continue
                    with pinned_directory(parent), os.scandir(parent) as entries:
                        for entry in entries:
                            info = entry.stat(follow_symlinks=False)
                            if (
                                not stat.S_ISDIR(info.st_mode)
                                or info.st_file_attributes & 0x400
                            ):
                                raise CoreError(
                                    "NATIVE_STORAGE_INVALID", "Unsafe retained run"
                                )
                            retained += 1
                            if retained >= RETAINED_RUN_LIMIT:
                                raise CoreError(
                                    "NATIVE_RETENTION_LIMIT",
                                    "Native retained-run limit reached",
                                    details={
                                        "retained_runs": retained,
                                        "retained_run_limit": RETAINED_RUN_LIMIT,
                                    },
                                )
                budget = DiskBudget(root, run, limits)
                budget.check(force=True)
                if (
                    budget.last["project_bytes"] + limits.run_bytes
                    > limits.project_bytes
                    or budget.last["free_bytes"] - limits.run_bytes < limits.free_bytes
                ):
                    raise CoreError(
                        "NATIVE_STORAGE_LIMIT",
                        "Insufficient headroom for a native run",
                        details={**budget.last, "reserve_bytes": limits.run_bytes},
                    )
                run.mkdir()
                created = True
                return {
                    "policy": "native-admission-v1",
                    "retention": "retain_all_no_eviction",
                    "retained_run_limit": RETAINED_RUN_LIMIT,
                    "reserve_bytes": limits.run_bytes,
                    "disk_limits": asdict(limits),
                }
    except (CoreError, OSError) as exc:
        if created:
            raise CoreError(
                "NATIVE_ADMISSION_INCOMPLETE",
                "Native run directory retained after admission failure; query its status",
                details={
                    "run_id": run.name,
                    "admitted": True,
                    "status": "incomplete",
                    "cause": exc.code
                    if isinstance(exc, CoreError)
                    else "FILESYSTEM_ERROR",
                },
            ) from exc
        if not isinstance(exc, CoreError):
            raise
        raise CoreError(
            exc.code,
            str(exc),
            details={**exc.details, "run_id": run.name, "admitted": False},
        ) from exc


@dataclass(frozen=True)
class DiskLimits:
    run_bytes: int = 8 * 1024**3
    project_bytes: int = 32 * 1024**3
    free_bytes: int = 4 * 1024**3
    entries: int = 200000


def _usage(root, current, maximum):
    total = selected = count = 0
    stack = [(root, 0)]
    while stack:
        directory, depth = stack.pop()
        if depth > 128:
            raise CoreError("NATIVE_STORAGE_LIMIT", "Native inventory depth exceeded")
        # Accounting observes changing files; it never reads content or follows
        # a known reparse point. Destructive cleanup uses pinned handles instead.
        try:
            info = directory.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(info.st_mode) or info.st_file_attributes & 0x400:
            raise CoreError("NATIVE_STORAGE_INVALID", "Unsafe native output directory")
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1
                if count > maximum:
                    raise CoreError(
                        "NATIVE_STORAGE_LIMIT", "Native inventory entry limit"
                    )
                try:
                    info = entry.stat(follow_symlinks=False)
                except FileNotFoundError:
                    continue  # Native runtime can remove its own temporary files.
                if info.st_file_attributes & 0x400:
                    raise CoreError(
                        "NATIVE_STORAGE_INVALID",
                        "Native output contains a reparse point",
                    )
                path = Path(entry.path)
                if stat.S_ISDIR(info.st_mode):
                    stack.append((path, depth + 1))
                elif stat.S_ISREG(info.st_mode):
                    total += info.st_size
                    if path.is_relative_to(current):
                        selected += info.st_size
                else:
                    raise CoreError(
                        "NATIVE_STORAGE_INVALID", "Unknown native output type"
                    )
    return total, selected, count


class DiskBudget:
    def __init__(self, root, run, limits=DiskLimits()):
        self.root, self.run, self.limits = root, run, limits
        self.next_check = 0
        self.last = {}

    def check(self, *, force=False):
        if not force and time.monotonic() < self.next_check:
            return
        total = selected = count = 0
        for name in NAMESPACES:
            root = self.root / name
            if root.exists():
                size, current, entries = _usage(
                    root, self.run, self.limits.entries - count
                )
                total += size
                selected += current
                count += entries
        free = shutil.disk_usage(self.root).free
        self.last = {"project_bytes": total, "run_bytes": selected, "free_bytes": free}
        if (
            total > self.limits.project_bytes
            or selected > self.limits.run_bytes
            or free < self.limits.free_bytes
        ):
            raise CoreError(
                "NATIVE_STORAGE_LIMIT",
                "Native storage budget exceeded",
                details=self.last,
            )
        self.next_check = time.monotonic() + 0.5


class NativeResources:
    def __init__(self, ctx, run, job):
        self.ctx, self.run, self.job = ctx, run, job
        self.disk = DiskBudget(ctx.state.path.parent, run)

    def check(self):
        from .platform_runs import _authorize

        _authorize(self.ctx)
        self.disk.check()

    def finished(self):
        self.check()
        if self.job.active():
            raise CoreError(
                "NATIVE_EXECUTOR_BUSY", "Native descendants have not exited"
            )
        self.disk.check(force=True)


@contextmanager
def execution_resources(ctx, run):
    from .platform_runs import _authorize

    _authorize(ctx)
    with project_slot(ctx.state.path.parent) as job:
        value = NativeResources(ctx, run, job)
        value.check()
        yield value
