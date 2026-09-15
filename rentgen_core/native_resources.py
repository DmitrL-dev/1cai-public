"""One native executor per project state, with bounded periodic disk accounting."""
from contextlib import contextmanager, ExitStack
from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import time

from ._windows_source_tree import pinned_directory, WindowsHandleOps, _retained_stamp
from .errors import CoreError
from .native_process import OwnedJob
from .snapshots import validate_operation_id
from .manifests import canonical_bytes, sha256

NAMESPACES = ("platform-checks", "test-runs", "metadata-runs", "ibcmd-fixtures")
RETAINED_RUN_LIMIT = 256


def _archive_path(root, run):
    return root / "native-archive" / (run.parent.name + "-" + run.name)


def _archive_invalid():
    return CoreError("NATIVE_ARCHIVE_INVALID", "Native archive evidence is invalid")


def _archive_directory_exists(path):
    """No-follow existence: a dangling junction is an object, never absence."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISDIR(info.st_mode) or info.st_file_attributes & 0x400:
        raise _archive_invalid()
    return True


@contextmanager
def _pinned_archive_root(root):
    with pinned_directory(root):
        archive = root / "native-archive"
        if _archive_directory_exists(archive):
            with pinned_directory(archive):
                yield
        else:
            yield


@contextmanager
def _archive_inventory(run):
    """Pin the entire bounded tree before publishing its logical archive."""
    ops = WindowsHandleOps()
    with pinned_directory(run.parent), ExitStack() as pins:
        inventory = []

        def visit(path, expected=None, depth=0):
            if len(inventory) >= 4096 or depth > 128:
                raise CoreError("NATIVE_ARCHIVE_LIMIT", "Archive inventory limit")
            handle = ops.open(path, directory=path == run or expected.directory)
            pins.callback(ops.close, handle)
            before = _retained_stamp(ops, handle)
            if ops.final_path(handle) != path or (
                expected is not None and before.identity != expected.identity
            ):
                raise _archive_invalid()
            item = {
                "path": path.relative_to(run).as_posix(),
                "identity": list(before.identity),
                "directory": before.directory,
                "size": before.size,
            }
            inventory.append(item)
            if before.directory:
                children = []
                for entry in ops.enumerate(handle):
                    if len(inventory) + len(children) >= 4096:
                        raise CoreError(
                            "NATIVE_ARCHIVE_LIMIT", "Archive inventory limit"
                        )
                    children.append(entry)
                for name, stamp in sorted(children):
                    visit(path / name, stamp, depth + 1)
            else:
                digest = hashlib.sha256()
                for chunk in ops.chunks(handle):
                    digest.update(chunk)
                item["sha256"] = digest.hexdigest()
            if _retained_stamp(ops, handle) != before:
                raise _archive_invalid()

        visit(run)
        yield inventory


def _archived(root, run, inventory=None):
    with _pinned_archive_root(root):
        return _archive_record(root, run, inventory)


def _archive_record(root, run, inventory):
    from .context import validate_project_id
    from .platform_runs import _read

    archive = _archive_path(root, run)
    if not _archive_directory_exists(archive):
        return None
    with pinned_directory(archive):
        manifest = _read(archive / "manifest.json")
        receipt = _read(archive / "receipt.json")
        expected = {
            "schema",
            "project_id",
            "state_root",
            "namespace",
            "run_id",
            "profile_id",
            "inventory",
            "requested_by",
        }
        if (
            set(manifest) != expected
            or type(manifest["schema"]) is not int
            or manifest["schema"] != 1
            or manifest["state_root"] != str(root)
            or manifest["namespace"] != run.parent.name
            or manifest["run_id"] != run.name
            or canonical_bytes(receipt)
            != canonical_bytes(
                {
                    "schema": 1,
                    "status": "archived",
                    "released_logical_bytes": 0,
                    "manifest_sha256": sha256(canonical_bytes(manifest)),
                }
            )
        ):
            raise _archive_invalid()
        validate_project_id(manifest["project_id"])
        actor = manifest["requested_by"]
        if (
            type(actor) is not dict
            or set(actor) != {"id", "authority"}
            or type(actor["id"]) is not str
            or not actor["id"].strip()
            or actor["authority"] not in ("local_os", "verified_token", "local_service")
        ):
            raise _archive_invalid()
        request = _read(
            run
            / (
                "runtime-request.json"
                if run.parent.name == "metadata-runs"
                else "request.json"
            )
        )
        binding = (
            request
            if run.parent.name in {"metadata-runs", "ibcmd-fixtures"}
            else request.get("input")
        )
        if (
            not isinstance(binding, dict)
            or request.get("project_id") != manifest["project_id"]
            or binding.get("profile_id") != manifest["profile_id"]
        ):
            raise _archive_invalid()
        if inventory is None:
            with _archive_inventory(run) as current:
                if canonical_bytes(manifest["inventory"]) != canonical_bytes(current):
                    raise _archive_invalid()
        elif canonical_bytes(manifest["inventory"]) != canonical_bytes(inventory):
            raise _archive_invalid()
        return manifest, receipt


def archive_native_run(ctx, operation_id, *, namespace, profile_id=None):
    """Admin-only logical archive; never delete, move, or stop native resources.

    Full evidence stays readable and counted against the disk budget. Only a
    validated archive releases an admission slot; existing UUIDs cannot restart.
    """
    from .platform_runs import _get
    from .edt_profiles import authorized
    from .edt_execution import write_record

    with authorized(ctx, {"project:read", "project:admin"}) as authorize:
        validate_operation_id(operation_id)
        if namespace not in NAMESPACES:
            raise _archive_invalid()
        if (namespace == "platform-checks" and profile_id is not None) or (
            namespace != "platform-checks"
            and (
                not isinstance(profile_id, str)
                or re.fullmatch(r"[0-9a-f]{64}", profile_id) is None
            )
        ):
            raise _archive_invalid()
        root = ctx.state.path.parent.absolute()
        run = root / namespace / operation_id
        with (
            project_slot(root),
            _file_slot(root, "native-admission.lock", "NATIVE_ADMISSION_BUSY"),
            _pinned_archive_root(root),
        ):
            with _archive_inventory(run) as inventory:
                if namespace == "metadata-runs":
                    from .metadata_runs import get_preview

                    result = get_preview(ctx, operation_id)
                    actual_profile = result["profile_id"]
                elif namespace == "ibcmd-fixtures":
                    from .edt_fixture_executor import _get_fixture_result

                    result = _get_fixture_result(
                        ctx,
                        operation_id,
                        fixture_root=str(root),
                        permissions={"project:read", "project:admin"},
                    )
                    if result["status"] not in {"completed", "failed"}:
                        raise _archive_invalid()
                    actual_profile = result["profile_id"]
                else:
                    result = _get(ctx, operation_id, namespace=namespace)
                    if (
                        result["status"] not in {"completed", "failed"}
                        or result["request"] is None
                    ):
                        raise _archive_invalid()
                    actual_profile = result["request"]["input"].get("profile_id")
                if profile_id != actual_profile or (
                    namespace != "platform-checks" and not isinstance(profile_id, str)
                ):
                    raise _archive_invalid()
                previous = _archived(root, run, inventory)
                if previous is not None:
                    manifest, receipt = previous
                    if (
                        manifest["project_id"] != ctx.project_id
                        or manifest["profile_id"] != profile_id
                    ):
                        raise _archive_invalid()
                    return receipt
                manifest = {
                    "schema": 1,
                    "project_id": ctx.project_id,
                    "state_root": str(root),
                    "namespace": namespace,
                    "run_id": operation_id,
                    "profile_id": profile_id,
                    "inventory": inventory,
                    "requested_by": asdict(ctx.principal),
                }
                # Both records fit the strict bounded reader before any write.
                if len(canonical_bytes(manifest)) > 1536 * 1024:
                    raise CoreError("NATIVE_ARCHIVE_LIMIT", "Archive manifest limit")
                receipt = {
                    "schema": 1,
                    "status": "archived",
                    "released_logical_bytes": 0,
                    "manifest_sha256": sha256(canonical_bytes(manifest)),
                }
                authorize()
                archive = _archive_path(root, run)
                with pinned_directory(root):
                    archive.parent.mkdir(exist_ok=True)
                    with pinned_directory(archive.parent):
                        archive.mkdir()
                        with pinned_directory(archive):
                            # Admission holds the same lock: it observes only a
                            # complete pair or fails closed on a partial archive.
                            write_record(archive / "manifest.json", manifest)
                            write_record(archive / "receipt.json", receipt)
                return receipt


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

    Outcomes consume a slot until a verified explicit administrative archive.
    Compilation, YAxUnit and EDT share this admission boundary.
    """
    root, run = Path(root).absolute(), Path(run).absolute()
    limits = DiskLimits() if limits is None else limits
    validate_operation_id(run.name)
    if run.parent.parent != root or run.parent.name not in NAMESPACES:
        raise CoreError("NATIVE_STORAGE_INVALID", "Not an owned native run")
    created = False
    try:
        with (
            _file_slot(root, "native-admission.lock", "NATIVE_ADMISSION_BUSY"),
            _pinned_archive_root(root),
        ):
            # Namespaces are fixed immediate children of the pinned project root.
            # Reserve can be called before a namespace has its first operation.
            with pinned_directory(root):
                run.parent.mkdir(exist_ok=True)
            with pinned_directory(run.parent):
                if run.exists():
                    raise FileExistsError(str(run))
                if _archive_directory_exists(_archive_path(root, run)):
                    raise _archive_invalid()  # A removed archived UUID cannot restart.
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
                            if _archived(root, Path(entry.path)) is not None:
                                continue
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
        with _pinned_archive_root(self.root):
            self._check(force=force)

    def _check(self, *, force=False):
        if not force and time.monotonic() < self.next_check:
            return
        total = selected = count = 0
        for name in (*NAMESPACES, "native-archive"):
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
