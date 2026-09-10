"""One native executor per project state, with bounded periodic disk accounting."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import stat
import time

from ._windows_source_tree import pinned_directory, WindowsHandleOps, _retained_stamp
from .errors import CoreError
from .native_process import OwnedJob


@contextmanager
def project_slot(root):
    import msvcrt

    root = Path(root).absolute()
    with pinned_directory(root):
        lock = root / "native-executor.lock"
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_BINARY, 0o600)
        acquired, job = False, None
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
                    "NATIVE_EXECUTOR_BUSY", "Another native executor holds this project"
                ) from exc
            identity = hashlib.sha256(str(root).casefold().encode()).hexdigest()
            job = OwnedJob("Local\\RentgenCore.Native." + identity)
            yield job
        finally:
            try:
                if job:
                    job.close()
            finally:
                if acquired:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                os.close(descriptor)


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
        for name in ("platform-checks", "test-runs", "metadata-runs"):
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
