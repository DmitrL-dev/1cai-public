"""Owned workspace writer for a snapshot-bound metadata candidate.

The writer mutates only a directory explicitly created by Rentgen.  It never
writes the registered project source root or a 1C infobase.  Each mutation is
CAS-bound to the original/candidate inventories and leaves a receipt that can
be replayed for reading, not for silently retrying a partial write.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil

from ._windows_source_tree import read_retained
from .edt_inventory import exported_inventory
from .edt_profiles import PERMISSIONS, parse_json
from .edt_execution import write_record
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


def _backup(root):
    return root / ".rentgen-backup"


def _stage(root):
    return root / ".rentgen-stage"


def _seal(value, key):
    return {**value, key: sha256(canonical_bytes(value))}


def _read_sealed(path, key):
    try:
        value = parse_json(read_retained(path, MAX_RECORD))
        valid = (
            type(value) is dict
            and key in value
            and _seal({k: v for k, v in value.items() if k != key}, key) == value
        )
        _require(valid, "METADATA_WORKSPACE_RECOVERY_REQUIRED", "Receipt hash differs")
        return value
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


def _inventory(root, check):
    rows = exported_inventory(root, authorize=check)
    _require(
        1 <= len(rows) <= MAX_FILES,
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
    os.replace(temporary, path)


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


def apply_workspace(ctx, operation_id, workspace_root):
    """Apply a retained candidate to an owned workspace with file-level CAS."""
    _check(ctx)
    validate_operation_id(operation_id)
    root, marker = _load_root(ctx, operation_id, workspace_root)
    _ensure_clean_phase(root)
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
    _require(
        not stage.exists() and not backup.exists(),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Workspace staging or backup already exists",
    )
    stage.mkdir()
    backup.mkdir()
    try:
        _copy_rows(_tree(root), backup, original_rows, check=check)
        _copy_rows(candidate, stage, candidate_rows, check=check, retained=True)
        state = _seal(
            {
                "schema": SCHEMA,
                "project_id": ctx.project_id,
                "operation_id": operation_id,
                "preview_id": marker["preview_id"],
                "phase": "applying",
                "before_digest": _digest(original_rows),
                "after_digest": _digest(candidate_rows),
                "created_at": _now(),
            },
            "state_id",
        )
        write_record(_state_path(root), state)
        before_paths = {row["path"] for row in original_rows}
        after_paths = {row["path"] for row in candidate_rows}
        for row in candidate_rows:
            check()
            source, target = stage / row["path"], _tree(root) / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
        for relative in sorted(before_paths - after_paths):
            check()
            (_tree(root) / relative).unlink()
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
                "changed_paths": sorted(
                    before_paths ^ after_paths
                    | {
                        row["path"]
                        for row in candidate_rows
                        if row["path"] in before_paths
                        and next(
                            item
                            for item in original_rows
                            if item["path"] == row["path"]
                        )["sha256"]
                        != row["sha256"]
                    }
                ),
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


def undo_workspace(ctx, operation_id, workspace_root):
    """Restore the exact original workspace only when candidate CAS still holds."""
    _check(ctx)
    validate_operation_id(operation_id)
    root, marker = _load_root(ctx, operation_id, workspace_root)
    _ensure_clean_phase(root)
    if _undo_path(root).exists():
        previous = _read_sealed(_undo_path(root), "undo_id")
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
    backup = _backup(root)
    _require(
        backup.is_dir(),
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Apply backup is absent",
    )
    state = _seal(
        {
            "schema": SCHEMA,
            "project_id": ctx.project_id,
            "operation_id": operation_id,
            "preview_id": marker["preview_id"],
            "phase": "undoing",
            "before_digest": result["after_digest"],
            "after_digest": marker["original_digest"],
            "created_at": _now(),
        },
        "state_id",
    )
    _replace_record(_state_path(root), state)
    current_paths = {row["path"] for row in current}
    original_rows = marker["original_inventory"]
    original_paths = {row["path"] for row in original_rows}
    for relative in sorted(current_paths - original_paths):
        (_tree(root) / relative).unlink()
    for row in original_rows:
        _check(ctx)
        source, target = backup / row["path"], _tree(root) / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
    restored = _inventory(_tree(root), lambda: _check(ctx))
    _require(
        restored == original_rows,
        "METADATA_WORKSPACE_RECOVERY_REQUIRED",
        "Undo result differs from original",
    )
    undo = _seal(
        {
            "schema": SCHEMA,
            "project_id": ctx.project_id,
            "operation_id": operation_id,
            "preview_id": marker["preview_id"],
            "result_id": result["result_id"],
            "status": "undone",
            "workspace_root": str(root),
            "restored_digest": marker["original_digest"],
            "live_source_written": False,
            "created_at": _now(),
        },
        "undo_id",
    )
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
    _check(ctx)
    return undo


def get_workspace_status(ctx, operation_id, workspace_root):
    _check(ctx)
    validate_operation_id(operation_id)
    root, marker = _load_root(ctx, operation_id, workspace_root)
    state = (
        _read_sealed(_state_path(root), "state_id")
        if _state_path(root).exists()
        else None
    )
    result = (
        _read_sealed(_result_path(root), "result_id")
        if _result_path(root).exists()
        else None
    )
    undo = (
        _read_sealed(_undo_path(root), "undo_id") if _undo_path(root).exists() else None
    )
    _check(ctx)
    return {"marker": marker, "state": state, "result": result, "undo": undo}
