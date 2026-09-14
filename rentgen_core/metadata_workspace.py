"""Owned workspace writer for a snapshot-bound metadata candidate.

The writer mutates only a directory explicitly created by Rentgen.  It never
writes the registered project source root or a 1C infobase. Mutations check the
original/candidate inventories and serialize cooperating workspace callers.
Receipts support readback, not silent replay; external writers ignore this lock.
"""

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import os
from pathlib import Path
import shutil
import stat

from ._windows_source_tree import pinned_directory, read_retained
from .edt_inventory import exported_inventory
from .edt_profiles import PERMISSIONS, parse_json
from .edt_execution import write_record as _write_record
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .metadata_runs import get_preview, run_path as preview_run_path
from .platform_check import _pin_inputs
from .snapshots import validate_operation_id
from .source_paths import validate_file_paths


SCHEMA = 1
MAX_RECORD = 2 * 1024**2
MAX_FILES = 8192
MAX_FILE = 256 * 1024**2
MAX_TOTAL = 4 * 1024**3
_ACTIVE_BOUNDARY = ContextVar("metadata_workspace_boundary", default=None)


def _identity(path, *, directory=False, code="METADATA_WORKSPACE_CONFLICT"):
    try:
        info = path.lstat()
    except OSError as exc:
        raise CoreError(code, "Workspace path is unavailable") from exc
    _require(
        (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
        and not bool(getattr(info, "st_file_attributes", 0) & 0x400)
        and (directory or info.st_nlink == 1),
        code,
        "Workspace path is a link or has an unexpected type",
    )
    return info.st_dev, info.st_ino


@contextmanager
def _workspace_mutex(root):
    """Serialize admission reads with writers without creating a workspace file."""
    if os.name != "nt":
        yield
        return
    import ctypes

    code = "METADATA_WORKSPACE_LOCK_INVALID"
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel32.CreateMutexW
    create_mutex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    create_mutex.restype = ctypes.c_void_p
    wait = kernel32.WaitForSingleObject
    wait.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    wait.restype = ctypes.c_uint32
    release = kernel32.ReleaseMutex
    release.argtypes = [ctypes.c_void_p]
    release.restype = ctypes.c_int
    close = kernel32.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    close.restype = ctypes.c_int
    root = Path(root)
    identity = _identity(root, directory=True, code="METADATA_WORKSPACE_LOCK_INVALID")
    name = f"Global\\RentgenWorkspace-{identity[0]:x}-{identity[1]:x}"
    handle = create_mutex(None, 0, name)
    if not handle:
        raise CoreError(code, "Workspace admission mutex could not be created")
    acquired = False
    try:
        result = wait(handle, 0)
        if result == 0x102:  # WAIT_TIMEOUT
            raise CoreError(
                code="METADATA_WORKSPACE_BUSY",
                message="Another workspace operation is active",
            )
        _require(
            result in {0, 0x80},
            code,
            "Workspace admission mutex could not be acquired",
        )
        acquired = True
        yield
    finally:
        if acquired:
            release(handle)
        close(handle)


@contextmanager
def _workspace_lock(root, *, before_lock=None):
    with _workspace_mutex(root):
        if before_lock is not None:
            before_lock()
        with _workspace_lock_impl(root) as check:
            yield check


@contextmanager
def _workspace_lock_impl(root):
    """One cooperative writer per owned workspace; never remove the lock file."""
    code = "METADATA_WORKSPACE_LOCK_INVALID"
    root = Path(root)
    # A root directory pin also blocks our receipt replacements on Windows.
    # Pin its parent; observe root/tree identity again at publication boundaries.
    pin = pinned_directory(root.parent) if os.name == "nt" else nullcontext()
    with pin:
        root_identity = _identity(root, directory=True)
        tree_identity = _identity(_tree(root), directory=True)
        lock = root / "workspace-operation.lock"
        if os.path.lexists(lock):
            _identity(lock, code=code)
        flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_NONBLOCK", 0)
        try:
            try:
                descriptor = os.open(lock, flags | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
            except FileExistsError:
                descriptor = os.open(lock, flags)
                created = False
        except OSError as exc:
            raise CoreError(code, "Workspace lock could not be opened") from exc
        acquired = False
        try:
            info = os.fstat(descriptor)
            identity = (info.st_dev, info.st_ino)
            _require(
                stat.S_ISREG(info.st_mode)
                and info.st_nlink == 1
                and _identity(lock, code=code) == identity,
                code,
                "Workspace lock identity differs from its path",
            )
            if created:
                os.write(descriptor, b"0")
                os.fsync(descriptor)
            _require(
                os.fstat(descriptor).st_size == 1, code, "Workspace lock is incomplete"
            )
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as exc:
                raise CoreError(
                    "METADATA_WORKSPACE_BUSY", "Another workspace operation is active"
                ) from exc

            def check(*paths):
                _require(
                    _identity(lock, code=code) == identity
                    and os.fstat(descriptor).st_size == 1,
                    code,
                    "Workspace lock was replaced or changed",
                )
                _require(
                    _identity(root, directory=True) == root_identity
                    and _identity(_tree(root), directory=True) == tree_identity,
                    "METADATA_WORKSPACE_CONFLICT",
                    "Workspace directory identity changed",
                )
                for path in paths:
                    _require(
                        path.is_relative_to(root) and ".." not in path.parts,
                        "METADATA_WORKSPACE_UNSAFE",
                        "Publication path is outside workspace",
                    )
                    parent = root
                    for part in path.relative_to(root).parts[:-1]:
                        parent /= part
                        _identity(parent, directory=True)
                    if os.path.lexists(path):
                        _identity(path, directory=path.is_dir())

            check()
            yield check
            check()
        finally:
            try:
                if acquired:
                    if os.name == "nt":
                        os.lseek(descriptor, 0, os.SEEK_SET)
                        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)


def _workspace_operation(function):
    @wraps(function)
    def serialized(ctx, operation_id, workspace_root, **kwargs):
        _check(ctx)
        validate_operation_id(operation_id)
        root = _workspace_root(workspace_root)
        _owned_paths(ctx, root)
        _require(
            root.is_dir(), "METADATA_WORKSPACE_NOT_FOUND", "Owned workspace is absent"
        )
        root_identity = _identity(root, directory=True)
        tree_identity = _identity(_tree(root), directory=True)

        def admission():
            marker = _prevalidate_marker(ctx, operation_id, root)
            if not os.path.lexists(root / "workspace-operation.lock"):
                # Reject imported receipts before creating even the lock file.
                _validated_receipts(
                    ctx,
                    operation_id,
                    root,
                    marker,
                    receipt_reader=_read_sealed_admission,
                )

        with _workspace_lock(root, before_lock=admission) as identity_check:
            _require(
                _identity(root, directory=True) == root_identity
                and _identity(_tree(root), directory=True) == tree_identity,
                "METADATA_WORKSPACE_CONFLICT",
                "Workspace directory identity changed during admission",
            )
            # Retained marker reads pin root and must not run in a losing caller:
            # those pins can block an admitted writer's receipt replacement.
            root, marker = _load_root(ctx, operation_id, root)
            _validated_receipts(ctx, operation_id, root, marker)

            def boundary(*paths):
                _check(ctx)
                identity_check(*paths)

            token = _ACTIVE_BOUNDARY.set(boundary)
            try:
                # The function reloads marker, state and inventories after admission.
                return function(ctx, operation_id, root, **kwargs)
            finally:
                _ACTIVE_BOUNDARY.reset(token)

    return serialized


def _boundary(*paths):
    check = _ACTIVE_BOUNDARY.get()
    if check is not None:
        check(*paths)


def write_record(path, value):
    _boundary(path)
    _write_record(path, value)


def _publish_replace(source, target):
    _boundary(source, target)
    os.replace(source, target)


def _publish_unlink(path):
    _boundary(path)
    path.unlink()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _digest(rows):
    return sha256(canonical_bytes(rows))


def _validate_rows(rows):
    _require(
        type(rows) is list and 1 <= len(rows) <= MAX_FILES,
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace inventory has an invalid shape",
    )
    previous = None
    total = 0
    for row in rows:
        _require(
            type(row) is dict
            and set(row) == {"path", "size", "sha256"}
            and type(row["path"]) is str
            and type(row["size"]) is int
            and 0 <= row["size"] <= MAX_FILE
            and type(row["sha256"]) is str
            and len(row["sha256"]) == 64,
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace inventory row is invalid",
        )
        validate_file_paths((row["path"],))
        _require(
            all(character in "0123456789abcdef" for character in row["sha256"]),
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace inventory hash is invalid",
        )
        _require(
            previous is None or previous < row["path"],
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace inventory is not sorted",
        )
        previous = row["path"]
        total += row["size"]
    _require(
        total <= MAX_TOTAL,
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace inventory exceeds limits",
    )


def _check(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(PERMISSIONS)


def _require(condition, code, message):
    if not condition:
        raise CoreError(code, message)


def _workspace_root(value):
    if not isinstance(value, Path):
        value = Path(value)
    if not value.is_absolute() or ".." in value.parts:
        raise CoreError(
            "METADATA_WORKSPACE_INVALID", "Absolute workspace path is required"
        )
    return value.resolve()


def _owned_paths(ctx, root):
    source = ctx.source_root.resolve()
    state = ctx.state.path.parent.resolve()
    if root == source or root.is_relative_to(source):
        raise CoreError(
            "METADATA_WORKSPACE_UNSAFE", "Workspace cannot be inside the source tree"
        )
    if root == state or root.is_relative_to(state):
        raise CoreError(
            "METADATA_WORKSPACE_UNSAFE", "Workspace cannot be inside project state"
        )


def _tree(root):
    return root / "tree"


def _marker_path(root):
    return root / ".rentgen-workspace.json"


def _state_path(root):
    return root / "workspace-state.json"


def _result_path(root):
    return root / "workspace-result.json"


def _undo_path(root):
    return root / "workspace-undo.json"


def _recovery_path(root):
    return root / "workspace-recovery.json"


def _backup(root):
    return root / ".rentgen-backup"


def _stage(root):
    return root / ".rentgen-stage"


def _undo_stage(root):
    return root / ".rentgen-undo-stage"


def _verified_backup(root, original_rows, check):
    backup = _backup(root)
    _require(
        backup.is_dir() and not backup.is_symlink(),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Apply backup is absent or unsafe",
    )
    _require(
        _inventory(backup, check) == original_rows,
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Apply backup does not match the original inventory",
    )
    return backup


def _seal(value, key):
    return {**value, key: sha256(canonical_bytes(value))}


def _parse_sealed(raw, key):
    value = parse_json(raw)
    _require(
        type(value) is dict
        and key in value
        and _seal({k: v for k, v in value.items() if k != key}, key) == value,
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Receipt hash differs",
    )
    return value


def _prevalidate_marker(ctx, operation_id, root):
    """Reject unowned roots without writes or a directory pin before admission."""
    code = "METADATA_WORKSPACE_RECOVERY_REQUIRED"
    path = _marker_path(root)
    try:
        identity = _identity(path, code=code)
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            _require(
                stat.S_ISREG(info.st_mode)
                and info.st_nlink == 1
                and not bool(getattr(info, "st_file_attributes", 0) & 0x400)
                and (info.st_dev, info.st_ino) == identity
                and info.st_size <= MAX_RECORD,
                code,
                "Workspace marker is unsafe or too large",
            )
            raw = stream.read(MAX_RECORD + 1)
            _require(
                len(raw) <= MAX_RECORD and _identity(path, code=code) == identity,
                code,
                "Workspace marker changed during admission",
            )
        marker = _parse_sealed(raw, "marker_id")
        _validate_marker(ctx, operation_id, root, marker)
        return marker
    except (CoreError, OSError, ValueError, TypeError) as exc:
        raise CoreError(
            code, "Workspace ownership marker is absent or invalid"
        ) from exc


def _read_sealed(path, key):
    try:
        return _parse_sealed(read_retained(path, MAX_RECORD), key)
    except (CoreError, OSError, ValueError, TypeError) as exc:
        if (
            isinstance(exc, CoreError)
            and exc.code == "METADATA_WORKSPACE_RECOVERY_REQUIRED"
        ):
            raise
        raise CoreError(
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace receipt is incomplete or changed",
        ) from exc


def _read_sealed_admission(path, key):
    """Read one receipt without retaining Windows pins before lock admission.

    The full pinned reader remains the authority after ``_workspace_lock`` is
    acquired. This short no-follow read only lets admission reject an imported
    receipt without holding a root/receipt handle while another writer may be
    acquiring the lock.
    """
    code = "METADATA_WORKSPACE_RECOVERY_REQUIRED"
    try:
        identity = _identity(path, code=code)
        descriptor = _open_admission_read(path)
        try:
            info = os.fstat(descriptor)
            _require(
                stat.S_ISREG(info.st_mode)
                and info.st_nlink == 1
                and (info.st_dev, info.st_ino) == identity
                and info.st_size <= MAX_RECORD,
                code,
                "Workspace receipt is unsafe or too large",
            )
            raw = os.read(descriptor, MAX_RECORD + 1)
            _require(
                len(raw) <= MAX_RECORD and _identity(path, code=code) == identity,
                code,
                "Workspace receipt changed during admission",
            )
        finally:
            os.close(descriptor)
        return _parse_sealed(raw, key)
    except (CoreError, OSError, ValueError, TypeError) as exc:
        if isinstance(exc, CoreError) and exc.code == code:
            raise
        raise CoreError(code, "Workspace receipt is incomplete or changed") from exc


def _open_admission_read(path):
    """Open a receipt without denying an admitted writer's replacement.

    ``os.open`` on Windows requests the CRT's default share mode, which can
    deny ``os.replace`` while an admission read is in progress.  Use a native
    handle with FILE_SHARE_DELETE for this short, pre-lock read; the final
    pinned read after admission remains authoritative.
    """
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        return os.open(path, flags)
    import ctypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    handle = create_file(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
        None,
        3,  # OPEN_EXISTING
        0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle == invalid:
        error = ctypes.get_last_error()
        raise OSError(error, "CreateFileW failed", str(path))
    try:
        return msvcrt.open_osfhandle(int(handle), os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel32.CloseHandle(handle)
        raise


def _inventory(root, check, *, allow_empty=False):
    rows = exported_inventory(root, authorize=check)
    _require(
        (0 if allow_empty else 1) <= len(rows) <= MAX_FILES,
        "METADATA_WORKSPACE_LIMIT",
        "Workspace file limit exceeded",
    )
    _require(
        sum(row["size"] for row in rows) <= MAX_TOTAL,
        "METADATA_WORKSPACE_LIMIT",
        "Workspace byte limit exceeded",
    )
    validate_file_paths(row["path"] for row in rows)
    return rows


def _write_bytes(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    _boundary(path)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _replace_record(path, value):
    """Atomically replace a small receipt while retaining a recovery marker."""
    temporary = path.with_name(path.name + ".tmp")
    _require(
        not temporary.exists(),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Receipt replacement has an unresolved temporary file",
    )
    write_record(temporary, value)
    _publish_replace(temporary, path)


def _write_or_replace_record(path, value):
    if path.exists():
        _replace_record(path, value)
    else:
        write_record(path, value)


def _copy_rows(source, target, rows, *, check, retained=False):
    for row in rows:
        check()
        relative = Path(row["path"])
        source_path, target_path = source / relative, target / relative
        if source_path.is_symlink() or source_path.is_dir():
            raise CoreError(
                "METADATA_WORKSPACE_UNSAFE",
                "Workspace input contains a link or directory",
            )
        raw = (
            read_retained(source_path, MAX_FILE)
            if retained
            else source_path.read_bytes()
        )
        _require(
            len(raw) == row["size"] and sha256(raw) == row["sha256"],
            "METADATA_WORKSPACE_CONFLICT",
            "Workspace input bytes differ from its inventory",
        )
        _write_bytes(target_path, raw)


def _discard_owned_directory(path, expected_rows, check):
    """Remove an internal staging directory only after validating its files."""
    if path.is_symlink():
        raise CoreError(
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace staging path is unsafe",
        )
    if not path.exists():
        return
    if path.is_symlink() or not path.is_dir():
        raise CoreError(
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace staging path is unsafe",
        )
    actual = _inventory(path, check, allow_empty=True)
    expected = {row["path"]: row for row in expected_rows}
    _require(
        all(expected.get(row["path"]) == row for row in actual),
        "METADATA_WORKSPACE_CONFLICT",
        "Workspace staging contains foreign bytes",
    )
    _boundary(path)
    shutil.rmtree(path)


def _changed_paths(before_rows, after_rows):
    before = {row["path"]: row for row in before_rows}
    after = {row["path"]: row for row in after_rows}
    return sorted(
        set(before) ^ set(after)
        | {
            path
            for path in set(before) & set(after)
            if before[path]["sha256"] != after[path]["sha256"]
        }
    )


def _replace_owned_tree(
    root,
    source,
    rows,
    *,
    allowed_rows,
    check,
    retained=False,
    stage=None,
    cleanup=True,
):
    """Materialize one validated inventory into tree with restartable staging."""
    current = _inventory(_tree(root), check)
    allowed = {}
    for row in allowed_rows:
        allowed.setdefault(row["path"], set()).add((row["size"], row["sha256"]))
    _require(
        all(
            (row["size"], row["sha256"]) in allowed.get(row["path"], set())
            for row in current
        ),
        "METADATA_WORKSPACE_CONFLICT",
        "Workspace tree contains foreign bytes",
    )
    stage = stage if stage is not None else root / ".rentgen-recovery-stage"
    _discard_owned_directory(stage, rows, check)
    stage.mkdir()
    _copy_rows(source, stage, rows, check=check, retained=retained)
    target_paths = {row["path"] for row in rows}
    for relative in sorted(set(row["path"] for row in current) - target_paths):
        check()
        _publish_unlink(_tree(root) / relative)
    for row in rows:
        check()
        source_path, target_path = stage / row["path"], _tree(root) / row["path"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        _publish_replace(source_path, target_path)
    restored = _inventory(_tree(root), check)
    _require(
        restored == rows,
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Recovered workspace differs from its target inventory",
    )
    if cleanup:
        _discard_owned_directory(stage, rows, check)


def _cleanup_original_recovery(root, original_rows, candidate_rows, check):
    _discard_owned_directory(_backup(root), original_rows, check)
    _discard_owned_directory(_stage(root), candidate_rows, check)


def _validate_marker(ctx, operation_id, root, marker):
    _validate_rows(marker.get("original_inventory"))
    _require(
        set(marker)
        == {
            "schema",
            "project_id",
            "operation_id",
            "preview_operation_id",
            "preview_id",
            "source_root",
            "original_inventory",
            "original_digest",
            "created_at",
            "marker_id",
        }
        and marker["schema"] == SCHEMA
        and marker["project_id"] == ctx.project_id
        and marker["operation_id"] == operation_id
        and marker["source_root"] == str(ctx.source_root.resolve())
        and marker["original_digest"] == _digest(marker["original_inventory"]),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace marker does not match this operation",
    )
    validate_operation_id(marker["preview_operation_id"])
    _require(
        type(marker["preview_id"]) is str and len(marker["preview_id"]) == 64,
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace marker has an invalid preview id",
    )


def _load_root(ctx, operation_id, workspace_root):
    root = _workspace_root(workspace_root)
    _owned_paths(ctx, root)
    _require(root.is_dir(), "METADATA_WORKSPACE_NOT_FOUND", "Owned workspace is absent")
    marker = _read_sealed(_marker_path(root), "marker_id")
    _validate_marker(ctx, operation_id, root, marker)
    _require(
        _tree(root).is_dir(),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace tree is absent",
    )
    return root, marker


def _preflight_binding(ctx, operation_id):
    from . import metadata_apply as apply

    intent, result = apply._load(ctx, operation_id)
    _require(
        result["status"] == "unavailable",
        "METADATA_APPLY_STALE",
        "Only a fresh successful preflight can create a workspace",
    )
    preview = get_preview(ctx, intent["request"]["preview_operation_id"])
    _require(
        preview["preview_id"] == intent["request"]["expected_preview_id"],
        "METADATA_APPLY_CONFLICT",
        "Preview no longer matches apply intent",
    )
    _require(
        apply._head_matches(ctx, intent["request"]),
        "METADATA_APPLY_STALE",
        "Project head or source configuration changed",
    )
    return intent, preview


def create_workspace(ctx, operation_id, workspace_root):
    """Create an owned copy of the preflight original inventory."""
    _check(ctx)
    validate_operation_id(operation_id)
    root = _workspace_root(workspace_root)
    _owned_paths(ctx, root)
    _require(
        not root.exists() and root.parent.is_dir(),
        "METADATA_WORKSPACE_CONFLICT",
        "Workspace path must be a new child of an existing directory",
    )
    intent, preview = _preflight_binding(ctx, operation_id)
    expected = preview["preview"]["inventories"]["original"]

    actual = _inventory(ctx.source_root, lambda: _check(ctx))
    _require(
        actual == expected,
        "METADATA_APPLY_STALE",
        "Live source differs from the preflight",
    )
    root.mkdir()
    try:
        (root / "tree").mkdir()
        with _pin_inputs(ctx.source_root, actual):
            _copy_rows(ctx.source_root, _tree(root), actual, check=lambda: _check(ctx))
        marker = _seal(
            {
                "schema": SCHEMA,
                "project_id": ctx.project_id,
                "operation_id": operation_id,
                "preview_operation_id": intent["request"]["preview_operation_id"],
                "preview_id": preview["preview_id"],
                "source_root": str(ctx.source_root.resolve()),
                "original_inventory": actual,
                "original_digest": _digest(actual),
                "created_at": _now(),
            },
            "marker_id",
        )
        write_record(_marker_path(root), marker)
        _require(
            _inventory(_tree(root), lambda: _check(ctx)) == actual,
            "METADATA_WORKSPACE_CONFLICT",
            "Workspace copy failed inventory verification",
        )
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
    _check(ctx)
    return marker


def _candidate(ctx, marker):
    preview = get_preview(ctx, marker["preview_operation_id"])
    _require(
        preview["preview_id"] == marker["preview_id"],
        "METADATA_APPLY_CONFLICT",
        "Workspace preview differs from the marker",
    )
    rows = preview["preview"]["inventories"]["candidate"]
    candidate = preview_run_path(ctx, marker["preview_operation_id"]) / "candidate-xml"
    _require(
        candidate.is_dir(),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Candidate export is absent",
    )
    _require(
        _inventory(candidate, lambda: _check(ctx)) == rows,
        "METADATA_APPLY_CONFLICT",
        "Candidate export differs from the retained preview",
    )
    return candidate, rows


def _ensure_clean_phase(root):
    _require(
        not _state_path(root).with_name(_state_path(root).name + ".tmp").exists(),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace has an unresolved receipt replacement",
    )
    if not _state_path(root).exists():
        return
    state = _read_sealed(_state_path(root), "state_id")
    if state.get("phase") != "complete":
        raise CoreError(
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace has an unresolved write phase; inspect it before retry",
        )


def _receipt_matches(saved, expected, key):
    _require(
        type(saved.get("schema")) is int
        and type(saved.get("created_at")) is str
        and 1 <= len(saved["created_at"]) <= 64
        and saved == _seal({**expected, "created_at": saved["created_at"]}, key),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace receipt does not match its operation or inventories",
    )


def _workspace_binding(root, marker):
    return {"workspace_root": str(root), "marker_id": marker["marker_id"]}


def _has_workspace_binding(record):
    return "workspace_root" in record or "marker_id" in record


def _legacy_recovery_receipt(recovery):
    return _seal(
        {
            key: value
            for key, value in recovery.items()
            if key not in {"workspace_root", "marker_id", "recovery_id"}
        },
        "recovery_id",
    )


def _validate_state_receipt(record, common, original, candidate, receipts):
    phase = record.get("phase")
    pointers = {key for key in ("result_id", "undo_id", "recovery_id") if key in record}
    _require(
        type(phase) is str
        and phase in {"applying", "undoing", "complete"}
        and len(pointers) == (1 if phase == "complete" else 0),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace state has an unsupported phase or receipt reference",
    )
    undoing = phase == "undoing" or pointers == {"undo_id"}
    if not _has_workspace_binding(record):
        # Legacy phase records have no independent workspace authority. Only a
        # complete state's exact reference to a rooted result/undo is provable.
        _require(
            phase == "complete" and pointers in ({"result_id"}, {"undo_id"}),
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Legacy interrupted workspace state has no provable workspace binding",
        )
        common = {
            key: value
            for key, value in common.items()
            if key not in {"workspace_root", "marker_id"}
        }
    if undoing:
        _require(
            receipts["result"] is not None,
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Undo state has no applied receipt",
        )
    expected = {
        **common,
        "phase": phase,
        "before_digest": candidate if undoing else original,
        "after_digest": original if undoing else candidate,
    }
    for key in pointers:
        receipt = receipts[key.removesuffix("_id")]
        _require(
            receipt is not None,
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace state references an absent receipt",
        )
        expected[key] = receipt[key]
    _receipt_matches(record, expected, "state_id")


def _validated_receipts(
    ctx, operation_id, root, marker, *, receipt_reader=_read_sealed
):
    """Validate historical authority without requiring a fresh live project head.

    Interrupted writes may leave both old and pending state, or a durable result
    before its complete state. Validate each against the same retained intent
    and inventories; recovery still decides which transition can resume.
    """
    from . import metadata_apply as apply

    paths = {
        "state": (_state_path(root), "state_id"),
        "result": (_result_path(root), "result_id"),
        "undo": (_undo_path(root), "undo_id"),
        "recovery": (_recovery_path(root), "recovery_id"),
        "pending_state": (_state_path(root).with_suffix(".json.tmp"), "state_id"),
        "pending_recovery": (
            _recovery_path(root).with_suffix(".json.tmp"),
            "recovery_id",
        ),
    }
    receipts = {
        name: receipt_reader(path, key) if path.exists() else None
        for name, (path, key) in paths.items()
    }
    if not any(value is not None for value in receipts.values()):
        return receipts
    intent, preflight = apply._load(ctx, operation_id)
    preview = get_preview(ctx, marker["preview_operation_id"])
    original_rows = marker["original_inventory"]
    candidate_rows = preview["preview"]["inventories"]["candidate"]
    _require(
        preflight["status"] == "unavailable"
        and intent["request"]["preview_operation_id"] == marker["preview_operation_id"]
        and intent["request"]["expected_preview_id"] == marker["preview_id"]
        and intent["binding"] == apply._binding(preview)
        and preview["preview"]["inventories"]["original"] == original_rows,
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace receipts differ from the retained preflight or preview",
    )
    common = {
        "schema": SCHEMA,
        "project_id": ctx.project_id,
        "operation_id": operation_id,
        "preview_id": marker["preview_id"],
    }
    bound_common = {**common, **_workspace_binding(root, marker)}
    original, candidate = marker["original_digest"], _digest(candidate_rows)
    result = receipts["result"]
    if result is not None:
        _require(
            result.get("workspace_source_written") is True
            and result.get("live_source_written") is False
            and ("recovered" not in result or result["recovered"] is True)
            and (
                receipts["state"] is not None
                or receipts["pending_state"] is not None
                or (
                    result.get("recovered") is True
                    and receipts["recovery"] is not None
                    and receipts["recovery"].get("target") == "candidate"
                )
            ),
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Applied receipt has invalid write flags or no owning state",
        )
        _receipt_matches(
            result,
            {
                **common,
                "intent_id": intent["intent_id"],
                "status": "applied",
                "workspace_root": str(root),
                "before_digest": original,
                "after_digest": candidate,
                "changed_paths": _changed_paths(original_rows, candidate_rows),
                "workspace_source_written": True,
                "live_source_written": False,
                **({"recovered": True} if "recovered" in result else {}),
            },
            "result_id",
        )
    if receipts["undo"] is not None:
        _require(
            result is not None
            and type(receipts["undo"].get("schema")) is int
            and receipts["undo"].get("live_source_written") is False,
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Undo receipt has no applied authority or has invalid flags",
        )
        _undo_receipt(
            ctx,
            operation_id,
            root,
            marker,
            result,
            previous=receipts["undo"],
        )
    for name in ("recovery", "pending_recovery"):
        recovery = receipts[name]
        if recovery is None:
            continue
        target = recovery.get("target")
        _require(
            type(target) is str and target in {"original", "candidate"},
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace recovery target is unsupported",
        )
        recovery_common = bound_common
        if not _has_workspace_binding(recovery):
            # Final undo recovery is reproducible from its rooted undo receipt,
            # including the immutable timestamp. An unattached legacy recovery
            # cannot prove where it originated, even when its tree digest fits.
            undo = receipts["undo"]
            _require(
                undo is not None
                and target == "original"
                and recovery.get("created_at") == undo["created_at"],
                "METADATA_WORKSPACE_RECOVERY_REQUIRED",
                "Legacy recovery receipt has no provable workspace binding",
            )
            recovery_common = common
        _receipt_matches(
            recovery,
            {
                **recovery_common,
                "status": "recovered",
                "target": target,
                "restored_digest": original if target == "original" else candidate,
            },
            "recovery_id",
        )
    for name in ("state", "pending_state"):
        if receipts[name] is not None:
            _validate_state_receipt(
                receipts[name], bound_common, original, candidate, receipts
            )
    return receipts


def _has_interrupted_undo(ctx, operation_id, workspace_root):
    """Return whether a bound workspace is waiting for undo recovery.

    This is only an admission hint for the native adapter. The subsequent
    ``recover_workspace`` call reacquires the writer lock and validates the
    same receipts before changing anything.
    """
    _check(ctx)
    validate_operation_id(operation_id)
    root = _workspace_root(workspace_root)
    _owned_paths(ctx, root)
    _require(root.is_dir(), "METADATA_WORKSPACE_NOT_FOUND", "Owned workspace is absent")
    with _workspace_mutex(root):
        root, marker = _load_root(ctx, operation_id, root)
        receipts = _validated_receipts(ctx, operation_id, root, marker)
    return any(
        record is not None
        and (
            record.get("phase") == "undoing"
            or (record.get("phase") == "complete" and "undo_id" in record)
        )
        for record in (receipts["state"], receipts["pending_state"])
    )


@_workspace_operation
def apply_workspace(ctx, operation_id, workspace_root):
    """Apply a retained candidate to an owned workspace with file-level CAS."""
    _check(ctx)
    validate_operation_id(operation_id)
    root, marker = _load_root(ctx, operation_id, workspace_root)
    _ensure_clean_phase(root)
    recovery = (
        _read_sealed(_recovery_path(root), "recovery_id")
        if _recovery_path(root).exists()
        else None
    )
    if recovery is not None and not _result_path(root).exists():
        _require(
            recovery.get("target") == "original"
            and recovery.get("status") == "recovered"
            and recovery.get("project_id") == ctx.project_id
            and recovery.get("operation_id") == operation_id
            and recovery.get("preview_id") == marker["preview_id"],
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace recovery receipt is not an original recovery",
        )
    if _result_path(root).exists():
        previous = _read_sealed(_result_path(root), "result_id")
        _require(
            previous["status"] == "applied",
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace result has an unsupported status",
        )
        _require(
            _digest(_inventory(_tree(root), lambda: _check(ctx)))
            == previous["after_digest"],
            "METADATA_APPLY_CONFLICT",
            "Workspace changed after the applied receipt",
        )
        _check(ctx)
        return previous
    intent, preview = _preflight_binding(ctx, operation_id)
    _require(
        preview["preview_id"] == marker["preview_id"],
        "METADATA_APPLY_CONFLICT",
        "Workspace marker is bound to another preview",
    )
    candidate, candidate_rows = _candidate(ctx, marker)

    def check():
        _check(ctx)

    original_rows = marker["original_inventory"]
    before = _inventory(_tree(root), check)
    _require(
        before == original_rows,
        "METADATA_APPLY_STALE",
        "Workspace was changed before apply",
    )
    stage, backup = _stage(root), _backup(root)
    reapply_prepared = False
    if recovery is not None:
        # A crash after both new inventories were staged but before the new
        # applying state was durable leaves the old complete/original receipt.
        # Reuse only the two fully validated owned directories; any partial
        # combination remains fail-closed for manual recovery.
        if stage.exists() or backup.exists():
            _require(
                stage.is_dir()
                and not stage.is_symlink()
                and backup.is_dir()
                and not backup.is_symlink(),
                "METADATA_WORKSPACE_RECOVERY_REQUIRED",
                "Workspace reapply staging is incomplete",
            )
            _require(
                _inventory(backup, check) == original_rows
                and _inventory(stage, check) == candidate_rows,
                "METADATA_WORKSPACE_RECOVERY_REQUIRED",
                "Workspace reapply staging differs from its inventories",
            )
            reapply_prepared = True
        else:
            _cleanup_original_recovery(root, original_rows, candidate_rows, check)
    if not reapply_prepared:
        _require(
            not stage.exists() and not backup.exists(),
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace staging or backup already exists",
        )
        stage.mkdir()
        backup.mkdir()
    try:
        if not reapply_prepared:
            _copy_rows(_tree(root), backup, original_rows, check=check)
            _copy_rows(candidate, stage, candidate_rows, check=check, retained=True)
        state = _seal(
            {
                "schema": SCHEMA,
                "project_id": ctx.project_id,
                "operation_id": operation_id,
                "preview_id": marker["preview_id"],
                **_workspace_binding(root, marker),
                "phase": "applying",
                "before_digest": _digest(original_rows),
                "after_digest": _digest(candidate_rows),
                "created_at": _now(),
            },
            "state_id",
        )
        _write_or_replace_record(_state_path(root), state)
        # The new applying journal is durable before the old recovery receipt
        # is removed.  A crash before this point leaves a retryable complete
        # state; a crash after it is handled by normal applying recovery.
        if recovery is not None and _recovery_path(root).exists():
            _publish_unlink(_recovery_path(root))
        before_paths = {row["path"] for row in original_rows}
        after_paths = {row["path"] for row in candidate_rows}
        for row in candidate_rows:
            check()
            source, target = stage / row["path"], _tree(root) / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            _publish_replace(source, target)
        for relative in sorted(before_paths - after_paths):
            check()
            _publish_unlink(_tree(root) / relative)
        after = _inventory(_tree(root), check)
        _require(
            after == candidate_rows,
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Applied workspace differs from candidate",
        )
        result = _seal(
            {
                "schema": SCHEMA,
                "project_id": ctx.project_id,
                "operation_id": operation_id,
                "preview_id": marker["preview_id"],
                "intent_id": intent["intent_id"],
                "status": "applied",
                "workspace_root": str(root),
                "before_digest": _digest(original_rows),
                "after_digest": _digest(candidate_rows),
                "changed_paths": _changed_paths(original_rows, candidate_rows),
                "workspace_source_written": True,
                "live_source_written": False,
                "created_at": _now(),
            },
            "result_id",
        )
        write_record(_result_path(root), result)
        complete = _seal(
            {
                **{key: value for key, value in state.items() if key != "state_id"},
                "phase": "complete",
                "result_id": result["result_id"],
            },
            "state_id",
        )
        _replace_record(_state_path(root), complete)
        return result
    except BaseException:
        raise


@_workspace_operation
def recover_workspace(ctx, operation_id, workspace_root, *, target):
    """Recover an interrupted apply to an explicitly selected target inventory.

    Recovery never consults the live source.  ``original`` uses the sealed
    apply backup; ``candidate`` uses the retained preview export.  A foreign
    file in the workspace or either staging directory stops the operation.
    """
    _check(ctx)
    validate_operation_id(operation_id)
    if target not in {"original", "candidate"}:
        raise CoreError(
            "METADATA_WORKSPACE_INVALID",
            "Recovery target must be original or candidate",
        )
    root, marker = _load_root(ctx, operation_id, workspace_root)
    state = (
        _read_sealed(_state_path(root), "state_id")
        if _state_path(root).exists()
        else None
    )
    temporary = _state_path(root).with_name(_state_path(root).name + ".tmp")
    pending = _read_sealed(temporary, "state_id") if temporary.exists() else None
    if (
        (state is not None and state.get("phase") == "undoing")
        or (pending is not None and pending.get("phase") == "undoing")
        or _undo_path(root).exists()
    ):
        return _recover_undo(ctx, operation_id, root, marker, state, pending, target)
    recovery = (
        _read_sealed(_recovery_path(root), "recovery_id")
        if _recovery_path(root).exists()
        else None
    )
    if recovery is not None:
        stale_reapply = (
            state is not None
            and state.get("phase") == "applying"
            and recovery.get("target") == "original"
            and target == "candidate"
            and state.get("before_digest") == marker["original_digest"]
        )
        candidate_digest = _digest(
            get_preview(ctx, marker["preview_operation_id"])["preview"]["inventories"][
                "candidate"
            ]
        )
        _require(
            set(recovery)
            == {
                "schema",
                "project_id",
                "operation_id",
                "preview_id",
                "workspace_root",
                "marker_id",
                "status",
                "target",
                "restored_digest",
                "created_at",
                "recovery_id",
            }
            and recovery["schema"] == SCHEMA
            and recovery["project_id"] == ctx.project_id
            and recovery["operation_id"] == operation_id
            and recovery["preview_id"] == marker["preview_id"]
            and recovery["status"] == "recovered"
            and recovery["target"] in {"original", "candidate"}
            and (recovery["target"] == target or stale_reapply)
            and recovery["restored_digest"]
            == (
                marker["original_digest"]
                if recovery["target"] == "original"
                else candidate_digest
            ),
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace recovery receipt is not bound to this operation",
        )
        if stale_reapply:
            recovery = None
    if state is not None and state.get("phase") == "complete":
        if (
            target == "candidate"
            and recovery is not None
            and recovery.get("target") == "candidate"
            and state.get("result_id")
            and _result_path(root).exists()
        ):
            result = _read_sealed(_result_path(root), "result_id")
            _, candidate_rows = _candidate(ctx, marker)
            _require(
                result["result_id"] == state["result_id"]
                and result.get("status") == "applied"
                and _digest(_inventory(_tree(root), lambda: _check(ctx)))
                == _digest(candidate_rows),
                "METADATA_WORKSPACE_CONFLICT",
                "Recovered candidate workspace changed",
            )
            _check(ctx)
            return recovery
        _require(
            recovery is not None
            and recovery.get("target") == target
            and state.get("recovery_id") == recovery["recovery_id"]
            and "result_id" not in state,
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace is already complete or recovered to another target",
        )
        if target == "original":
            _, candidate_rows = _candidate(ctx, marker)
            _require(
                _digest(_inventory(_tree(root), lambda: _check(ctx)))
                == marker["original_digest"],
                "METADATA_WORKSPACE_CONFLICT",
                "Recovered original workspace changed",
            )
            _cleanup_original_recovery(
                root, marker["original_inventory"], candidate_rows, lambda: _check(ctx)
            )
        _check(ctx)
        return recovery
    existing_result = (
        _read_sealed(_result_path(root), "result_id")
        if _result_path(root).exists()
        else None
    )
    if existing_result is not None:
        _require(
            target == "candidate",
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "An applied candidate receipt exists; recover to original through undo",
        )
        _require(
            existing_result.get("status") == "applied"
            and existing_result.get("project_id") == ctx.project_id
            and existing_result.get("operation_id") == operation_id
            and existing_result.get("preview_id") == marker["preview_id"],
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace result is not bound to this operation",
        )
        _, candidate_rows = _candidate(ctx, marker)
        current = _inventory(_tree(root), lambda: _check(ctx))
        _require(
            current == candidate_rows
            and _digest(current) == existing_result.get("after_digest"),
            "METADATA_WORKSPACE_CONFLICT",
            "Workspace result exists but the candidate tree differs",
        )
        if pending is not None:
            receipts = _validated_receipts(ctx, operation_id, root, marker)
            _require(
                receipts["state"] == state
                and receipts["result"] == existing_result
                and receipts["pending_state"] == pending
                and pending.get("phase") == "complete"
                and pending.get("result_id") == existing_result["result_id"]
                and all(
                    pending.get(key) == value
                    for key, value in _workspace_binding(root, marker).items()
                ),
                "METADATA_WORKSPACE_RECOVERY_REQUIRED",
                "Pending apply completion differs from its local applied receipt",
            )
        if recovery is not None:
            _require(
                recovery.get("target") == "candidate",
                "METADATA_WORKSPACE_RECOVERY_REQUIRED",
                "Workspace is already recovered to another target",
            )
        else:
            recovery = _seal(
                {
                    "schema": SCHEMA,
                    "project_id": ctx.project_id,
                    "operation_id": operation_id,
                    "preview_id": marker["preview_id"],
                    **_workspace_binding(root, marker),
                    "status": "recovered",
                    "target": "candidate",
                    "restored_digest": _digest(candidate_rows),
                    "created_at": _now(),
                },
                "recovery_id",
            )
            write_record(_recovery_path(root), recovery)
        if pending is not None:
            # The complete temporary record survived fsync but not os.replace.
            # Retain its exact identity; the workspace lock covers validation
            # and promotion, and the recovery receipt makes another crash retryable.
            _require(
                _read_sealed(temporary, "state_id") == pending,
                "METADATA_WORKSPACE_RECOVERY_REQUIRED",
                "Pending apply completion changed before publication",
            )
            _publish_replace(temporary, _state_path(root))
        else:
            _write_or_replace_record(
                _state_path(root),
                _seal(
                    {
                        "schema": SCHEMA,
                        "project_id": ctx.project_id,
                        "operation_id": operation_id,
                        "preview_id": marker["preview_id"],
                        **_workspace_binding(root, marker),
                        "phase": "complete",
                        "before_digest": _digest(marker["original_inventory"]),
                        "after_digest": _digest(candidate_rows),
                        "created_at": _now(),
                        "result_id": existing_result["result_id"],
                    },
                    "state_id",
                ),
            )
        _check(ctx)
        return recovery
    if state is not None:
        _require(
            state.get("phase") == "applying",
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace has an unsupported interrupted phase",
        )
    original_rows = marker["original_inventory"]
    backup = _backup(root)
    _require(
        backup.is_dir() and not backup.is_symlink(),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Apply backup is absent",
    )
    backup_rows = _inventory(backup, lambda: _check(ctx))
    _require(
        backup_rows == original_rows,
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Apply backup does not match the original inventory",
    )
    candidate, candidate_rows = _candidate(ctx, marker)
    if target == "original":
        source, rows, retained = backup, original_rows, False
    else:
        source, rows, retained = candidate, candidate_rows, True
    allowed_rows = original_rows + candidate_rows
    _replace_owned_tree(
        root,
        source,
        rows,
        allowed_rows=allowed_rows,
        check=lambda: _check(ctx),
        retained=retained,
    )
    if target == "candidate":
        _discard_owned_directory(_stage(root), candidate_rows, lambda: _check(ctx))
    if recovery is None:
        # A reapply crash may leave the previous original receipt in place.
        # Remove that stale name before create-only publication; a further
        # interruption is still recoverable from the applying state and the
        # validated backup/candidate sources.
        if _recovery_path(root).exists():
            _publish_unlink(_recovery_path(root))
        recovery = _seal(
            {
                "schema": SCHEMA,
                "project_id": ctx.project_id,
                "operation_id": operation_id,
                "preview_id": marker["preview_id"],
                **_workspace_binding(root, marker),
                "status": "recovered",
                "target": target,
                "restored_digest": _digest(rows),
                "created_at": _now(),
            },
            "recovery_id",
        )
        write_record(_recovery_path(root), recovery)
    if target == "candidate":
        from . import metadata_apply as apply

        intent, previous = apply._load(ctx, operation_id)
        _require(
            previous["status"] == "unavailable",
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Apply receipt already exists for this operation",
        )
        result = _seal(
            {
                "schema": SCHEMA,
                "project_id": ctx.project_id,
                "operation_id": operation_id,
                "preview_id": marker["preview_id"],
                "intent_id": intent["intent_id"],
                "status": "applied",
                "workspace_root": str(root),
                "before_digest": _digest(original_rows),
                "after_digest": _digest(candidate_rows),
                "changed_paths": _changed_paths(original_rows, candidate_rows),
                "workspace_source_written": True,
                "live_source_written": False,
                "recovered": True,
                "created_at": _now(),
            },
            "result_id",
        )
        write_record(_result_path(root), result)
        result_id = result["result_id"]
    else:
        result_id = None
    state_value = _seal(
        {
            "schema": SCHEMA,
            "project_id": ctx.project_id,
            "operation_id": operation_id,
            "preview_id": marker["preview_id"],
            **_workspace_binding(root, marker),
            "phase": "complete",
            "before_digest": _digest(original_rows),
            "after_digest": _digest(candidate_rows),
            "created_at": _now(),
            **(
                {"result_id": result_id}
                if result_id is not None
                else {"recovery_id": recovery["recovery_id"]}
            ),
        },
        "state_id",
    )
    _write_or_replace_record(_state_path(root), state_value)
    if target == "original":
        _cleanup_original_recovery(
            root, original_rows, candidate_rows, lambda: _check(ctx)
        )
    _check(ctx)
    return recovery


def _undo_receipt(ctx, operation_id, root, marker, result, *, previous=None):
    value = {
        "schema": SCHEMA,
        "project_id": ctx.project_id,
        "operation_id": operation_id,
        "preview_id": marker["preview_id"],
        "result_id": result["result_id"],
        "status": "undone",
        "workspace_root": str(root),
        "restored_digest": marker["original_digest"],
        "live_source_written": False,
    }
    if _undo_path(root).exists():
        if previous is None:
            previous = _read_sealed(_undo_path(root), "undo_id")
        _require(
            set(previous) == set(value) | {"created_at", "undo_id"}
            and type(previous.get("created_at")) is str
            and {
                key: item
                for key, item in previous.items()
                if key not in {"created_at", "undo_id"}
            }
            == value,
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Undo receipt is not bound to this operation",
        )
        return previous
    return _seal({**value, "created_at": _now()}, "undo_id")


def _complete_undo(root, state, undo, check):
    if not _undo_path(root).exists():
        write_record(_undo_path(root), undo)
    _replace_record(
        _state_path(root),
        _seal(
            {
                **{key: value for key, value in state.items() if key != "state_id"},
                "phase": "complete",
                "undo_id": undo["undo_id"],
            },
            "state_id",
        ),
    )
    check()


def _recover_undo(ctx, operation_id, root, marker, state, pending, target):
    _require(
        target == "original",
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Interrupted undo can only be completed to original",
    )
    result = _read_sealed(_result_path(root), "result_id")
    _, candidate_rows = _candidate(ctx, marker)
    _require(
        result.get("status") == "applied"
        and result.get("project_id") == ctx.project_id
        and result.get("operation_id") == operation_id
        and result.get("preview_id") == marker["preview_id"]
        and result.get("before_digest") == marker["original_digest"]
        and result.get("after_digest") == _digest(candidate_rows),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Applied receipt is not bound to this undo",
    )
    undo = _undo_receipt(ctx, operation_id, root, marker, result)
    # The immutable undo timestamp makes recovery publication restartable.
    recovery = _seal(
        {
            "schema": SCHEMA,
            "project_id": ctx.project_id,
            "operation_id": operation_id,
            "preview_id": marker["preview_id"],
            **_workspace_binding(root, marker),
            "status": "recovered",
            "target": "original",
            "restored_digest": marker["original_digest"],
            "created_at": undo["created_at"],
        },
        "recovery_id",
    )
    previous_recovery = None
    if _recovery_path(root).exists():
        previous_recovery = _read_sealed(_recovery_path(root), "recovery_id")
        if not _has_workspace_binding(previous_recovery):
            legacy = _legacy_recovery_receipt(recovery)
            _require(
                previous_recovery == legacy,
                "METADATA_WORKSPACE_RECOVERY_REQUIRED",
                "Legacy recovery differs from the rooted undo receipt",
            )
            recovery = legacy
        _require(
            set(previous_recovery) == set(recovery)
            and all(
                previous_recovery[key] == recovery[key]
                for key in (
                    "schema",
                    "project_id",
                    "operation_id",
                    "preview_id",
                    "status",
                )
            )
            and previous_recovery["target"] in {"original", "candidate"}
            and previous_recovery["restored_digest"]
            == (
                marker["original_digest"]
                if previous_recovery["target"] == "original"
                else result["after_digest"]
            ),
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Recovery receipt is not bound to this operation",
        )
    recovery_temp = _recovery_path(root).with_name(_recovery_path(root).name + ".tmp")
    if recovery_temp.exists():
        temporary_recovery = _read_sealed(recovery_temp, "recovery_id")
        if not _has_workspace_binding(temporary_recovery):
            recovery = _legacy_recovery_receipt(recovery)
        _require(
            temporary_recovery == recovery,
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Pending recovery receipt differs from the confirmed undo",
        )
    for record in (state, pending):
        if record is None:
            continue
        original_phase = record.get("phase") == "complete" and record.get("result_id")
        fields = {
            "schema",
            "project_id",
            "operation_id",
            "preview_id",
            "phase",
            "before_digest",
            "after_digest",
            "created_at",
            "state_id",
        }
        if record.get("phase") == "complete":
            fields.add("result_id" if original_phase else "undo_id")
        if _has_workspace_binding(record):
            fields.update(_workspace_binding(root, marker))
        else:
            _require(
                record.get("phase") == "complete",
                "METADATA_WORKSPACE_RECOVERY_REQUIRED",
                "Legacy interrupted undo state has no workspace binding",
            )
        _require(
            set(record) == fields
            and type(record.get("created_at")) is str
            and record.get("schema") == SCHEMA
            and record.get("project_id") == ctx.project_id
            and record.get("operation_id") == operation_id
            and record.get("preview_id") == marker["preview_id"]
            and all(
                record.get(key) == value
                for key, value in _workspace_binding(root, marker).items()
                if key in fields
            )
            and record.get("phase") in {"undoing", "complete"}
            and record.get("before_digest")
            == (marker["original_digest"] if original_phase else result["after_digest"])
            and record.get("after_digest")
            == (result["after_digest"] if original_phase else marker["original_digest"])
            and (not original_phase or record["result_id"] == result["result_id"])
            and ("undo_id" not in record or record["undo_id"] == undo["undo_id"]),
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Undo state is not bound to this operation",
        )

    def check():
        _check(ctx)

    original_rows = marker["original_inventory"]
    backup = _verified_backup(root, original_rows, check)
    if _undo_path(root).exists():
        _require(
            _inventory(_tree(root), check) == original_rows,
            "METADATA_UNDO_CONFLICT",
            "Workspace changed after the undo receipt",
        )
        _discard_owned_directory(_undo_stage(root), original_rows, check)
    else:
        _replace_owned_tree(
            root,
            backup,
            original_rows,
            allowed_rows=original_rows + candidate_rows,
            check=check,
            retained=True,
            stage=_undo_stage(root),
            cleanup=False,
        )
        write_record(_undo_path(root), undo)
    # A fully validated temporary state may be superseded only after the exact
    # original tree and its durable undo receipt are established.
    if pending is not None:
        _publish_unlink(_state_path(root).with_name(_state_path(root).name + ".tmp"))
    state = _seal(
        {
            "schema": SCHEMA,
            "project_id": ctx.project_id,
            "operation_id": operation_id,
            "preview_id": marker["preview_id"],
            **_workspace_binding(root, marker),
            "phase": "undoing",
            "before_digest": result["after_digest"],
            "after_digest": marker["original_digest"],
            "created_at": undo["created_at"],
        },
        "state_id",
    )
    _complete_undo(root, state, undo, check)
    _discard_owned_directory(_undo_stage(root), original_rows, check)
    if recovery_temp.exists():
        _publish_replace(recovery_temp, _recovery_path(root))
    elif previous_recovery != recovery:
        _write_or_replace_record(_recovery_path(root), recovery)
    check()
    return recovery


@_workspace_operation
def undo_workspace(ctx, operation_id, workspace_root):
    """Restore the exact original workspace only when candidate CAS still holds."""
    _check(ctx)
    validate_operation_id(operation_id)
    root, marker = _load_root(ctx, operation_id, workspace_root)
    _ensure_clean_phase(root)
    if _undo_path(root).exists():
        result = _read_sealed(_result_path(root), "result_id")
        previous = _undo_receipt(ctx, operation_id, root, marker, result)
        _require(
            previous["status"] == "undone",
            "METADATA_WORKSPACE_RECOVERY_REQUIRED",
            "Workspace undo receipt has an unsupported status",
        )
        _require(
            _digest(_inventory(_tree(root), lambda: _check(ctx)))
            == marker["original_digest"],
            "METADATA_UNDO_CONFLICT",
            "Workspace changed after the undo receipt",
        )
        _check(ctx)
        return previous
    result = _read_sealed(_result_path(root), "result_id")
    _require(
        result["status"] == "applied",
        "METADATA_UNDO_UNAVAILABLE",
        "Workspace has no applied receipt",
    )
    candidate, candidate_rows = _candidate(ctx, marker)
    del candidate
    current = _inventory(_tree(root), lambda: _check(ctx))
    _require(
        _digest(current) == result["after_digest"] and current == candidate_rows,
        "METADATA_UNDO_CONFLICT",
        "Workspace changed after apply; undo refuses to overwrite it",
    )
    original_rows = marker["original_inventory"]
    backup = _verified_backup(root, original_rows, lambda: _check(ctx))
    state = _seal(
        {
            "schema": SCHEMA,
            "project_id": ctx.project_id,
            "operation_id": operation_id,
            "preview_id": marker["preview_id"],
            **_workspace_binding(root, marker),
            "phase": "undoing",
            "before_digest": result["after_digest"],
            "after_digest": marker["original_digest"],
            "created_at": _now(),
        },
        "state_id",
    )
    _replace_record(_state_path(root), state)
    _replace_owned_tree(
        root,
        backup,
        original_rows,
        allowed_rows=candidate_rows,
        check=lambda: _check(ctx),
        retained=True,
        stage=_undo_stage(root),
        cleanup=False,
    )
    undo = _undo_receipt(ctx, operation_id, root, marker, result)
    _complete_undo(root, state, undo, lambda: _check(ctx))
    _discard_owned_directory(_undo_stage(root), original_rows, lambda: _check(ctx))
    _check(ctx)
    return undo


def get_workspace_status(ctx, operation_id, workspace_root):
    _check(ctx)
    validate_operation_id(operation_id)
    root = _workspace_root(workspace_root)
    _owned_paths(ctx, root)
    _require(root.is_dir(), "METADATA_WORKSPACE_NOT_FOUND", "Owned workspace is absent")
    with _workspace_mutex(root):
        root, marker = _load_root(ctx, operation_id, root)
        receipts = _validated_receipts(ctx, operation_id, root, marker)
    _check(ctx)
    return {
        "marker": marker,
        **{name: receipts[name] for name in ("state", "result", "undo", "recovery")},
    }
