"""Durable read-only metadata apply preflight; live apply and undo are unavailable."""
from dataclasses import asdict
from pathlib import Path
import re

from ._windows_source_tree import pinned_directory, read_retained
from .context import SnapshotRef
from .edt_execution import write_record
from .edt_inventory import exported_inventory
from .edt_profiles import PERMISSIONS, parse_json
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .metadata_runs import get_preview
from .platform_check import _pin_inputs
from .snapshots import ProjectHead, validate_operation_id

HASH = re.compile(r"[0-9a-f]{64}")
STATUSES = {"unavailable", "stale", "revoked", "failed"}


def _check(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(PERMISSIONS)


def _require(condition, code, message):
    if not condition:
        raise CoreError(code, message)


def journal_path(ctx, operation_id):
    return (
        ctx.state.path.parent / "metadata-apply" / validate_operation_id(operation_id)
    )


def _seal(value, key):
    return {**value, key: sha256(canonical_bytes(value))}


def _read(path, key):
    try:
        value = parse_json(read_retained(path, 2 * 1024**2))
        valid = (
            type(value) is dict
            and key in value
            and _seal({k: v for k, v in value.items() if k != key}, key) == value
        )
        _require(valid, "METADATA_APPLY_RECOVERY_REQUIRED", "Journal hash differs")
        return value
    except (CoreError, OSError) as exc:
        raise CoreError(
            "METADATA_APPLY_RECOVERY_REQUIRED",
            "Journal is incomplete or changed; do not replay this operation ID",
        ) from exc


def _request(
    ctx, preview_operation_id, operation_id, expected_preview_id, expected_head
):
    validate_operation_id(preview_operation_id)
    validate_operation_id(operation_id)
    _require(
        type(expected_preview_id) is str
        and HASH.fullmatch(expected_preview_id)
        and isinstance(expected_head, ProjectHead)
        and expected_head.project_id == ctx.project_id
        and expected_head.snapshot is not None
        and expected_head.snapshot == ctx.snapshot,
        "METADATA_APPLY_INVALID",
        "Exact preview, selected snapshot and project head are required",
    )
    return {
        "schema": 1,
        "project_id": ctx.project_id,
        "operation_id": operation_id,
        "preview_operation_id": preview_operation_id,
        "expected_preview_id": expected_preview_id,
        "expected_head": asdict(expected_head),
        "source_root": str(ctx.source_root),
    }


def _binding(preview):
    return {
        "preview_id": preview["preview_id"],
        "plan_id": preview["plan_id"],
        "profile_id": preview["profile_id"],
        "inventory_digests": {
            name: sha256(canonical_bytes(rows))
            for name, rows in preview["preview"]["inventories"].items()
        },
    }


def _validate_intent(ctx, operation_id, intent):
    try:
        request, binding = intent["request"], intent["binding"]
        head_data = request["expected_head"]
        snapshot = SnapshotRef(**head_data["snapshot"])
        head = ProjectHead(**{**head_data, "snapshot": snapshot})
        validate_operation_id(request["preview_operation_id"])
        valid = (
            set(intent) == {"schema", "request", "binding", "intent_id"}
            and type(intent["schema"]) is int
            and intent["schema"] == 1
            and set(request)
            == {
                "schema",
                "project_id",
                "operation_id",
                "preview_operation_id",
                "expected_preview_id",
                "expected_head",
                "source_root",
            }
            and type(request["schema"]) is int
            and request["schema"] == 1
            and request["project_id"] == ctx.project_id
            and request["operation_id"] == operation_id
            and head.project_id == ctx.project_id
            and type(request["source_root"]) is str
            and Path(request["source_root"]).is_absolute()
            and type(binding) is dict
            and set(binding)
            == {"preview_id", "plan_id", "profile_id", "inventory_digests"}
            and all(
                type(binding[key]) is str and HASH.fullmatch(binding[key])
                for key in ("preview_id", "plan_id", "profile_id")
            )
            and request["expected_preview_id"] == binding["preview_id"]
            and type(binding["inventory_digests"]) is dict
            and set(binding["inventory_digests"])
            == {"original", "baseline", "candidate"}
            and all(
                type(value) is str and HASH.fullmatch(value)
                for value in binding["inventory_digests"].values()
            )
        )
        _require(valid, "METADATA_APPLY_RECOVERY_REQUIRED", "Invalid journal intent")
    except (CoreError, KeyError, TypeError, ValueError) as exc:
        raise CoreError(
            "METADATA_APPLY_RECOVERY_REQUIRED",
            "Journal intent has an invalid schema or context binding",
        ) from exc


def _load(ctx, operation_id):
    run = journal_path(ctx, operation_id)
    _require(run.exists(), "METADATA_APPLY_NOT_FOUND", "Apply preflight does not exist")
    with pinned_directory(run):
        intent = _read(run / "intent.json", "intent_id")
        _validate_intent(ctx, operation_id, intent)
        result = _read(run / "result.json", "result_id")
        _require(
            set(result)
            == {
                "schema",
                "project_id",
                "operation_id",
                "preview_id",
                "intent_id",
                "status",
                "reasons",
                "live_source_written",
                "result_id",
            }
            and type(result["schema"]) is int
            and result["schema"] == 1
            and result["project_id"] == ctx.project_id
            and result["operation_id"] == operation_id
            and result["intent_id"] == intent["intent_id"]
            and result["preview_id"] == intent["request"].get("expected_preview_id")
            and type(result["status"]) is str
            and result["status"] in STATUSES
            and type(result["reasons"]) is list
            and result["reasons"]
            and all(type(item) is str for item in result["reasons"])
            and result["live_source_written"] is False,
            "METADATA_APPLY_RECOVERY_REQUIRED",
            "Journal receipt is not a supported preflight result",
        )
    return intent, result


def get_apply_result(ctx, operation_id):
    """Read a historical preflight receipt, never a live-write receipt."""
    _check(ctx)
    _, result = _load(ctx, operation_id)
    _check(ctx)
    return result


def _head_matches(ctx, request):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(PERMISSIONS)
        head = tx.get_project_head()
        configuration = tx.get_source_configuration()
        layers = tx.get_snapshot_layers(
            request["expected_head"]["snapshot"]["snapshot_id"]
        )
    return (
        asdict(head) == request["expected_head"]
        and str(ctx.source_root) == request["source_root"]
        and len(configuration.layers) == len(layers) == 1
        and configuration.layers[0].root_relative_path == "."
        and all(
            getattr(configuration.layers[0], name) == getattr(layers[0], name)
            for name in ("layer_id", "ordinal", "kind", "source_format")
        )
    )


def _evaluate(ctx, intent, preview):
    request = intent["request"]
    _require(
        _binding(preview) == intent["binding"],
        "METADATA_APPLY_CONFLICT",
        "Retained preview differs from the journal binding",
    )
    if not _head_matches(ctx, request):
        return "stale", ["project_head_or_source_configuration_changed"]
    expected = preview["preview"]["inventories"]["original"]

    def check():
        _check(ctx)

    actual = exported_inventory(ctx.source_root, authorize=check)
    if actual != expected:
        return "stale", ["live_source_differs_from_snapshot"]
    with _pin_inputs(ctx.source_root, actual):
        if exported_inventory(ctx.source_root, authorize=check) != actual:
            return "stale", ["live_source_changed_during_preflight"]
        if not _head_matches(ctx, request):
            return "stale", ["project_head_or_source_configuration_changed"]
    _require(
        _binding(get_preview(ctx, request["preview_operation_id"]))
        == intent["binding"],
        "METADATA_APPLY_CONFLICT",
        "Retained preview changed during preflight",
    )
    return "unavailable", ["live_apply_not_implemented", "normalization_not_qualified"]


def _result(intent, status, reasons):
    request = intent["request"]
    return _seal(
        {
            "schema": 1,
            "project_id": request["project_id"],
            "operation_id": request["operation_id"],
            "preview_id": request["expected_preview_id"],
            "intent_id": intent["intent_id"],
            "status": status,
            "reasons": reasons,
            "live_source_written": False,
        },
        "result_id",
    )


def preflight_apply(
    ctx, preview_operation_id, operation_id, *, expected_preview_id, expected_head
):
    """Journal exact intent before inspecting live bytes; never alter the source."""
    _check(ctx)
    _require(
        not ctx.state.path.parent.is_relative_to(ctx.source_root),
        "METADATA_APPLY_UNSUPPORTED",
        "Preflight currently requires project state outside the live source tree",
    )
    request = _request(
        ctx, preview_operation_id, operation_id, expected_preview_id, expected_head
    )
    run = journal_path(ctx, operation_id)
    if run.exists():
        intent, result = _load(ctx, operation_id)
        _require(
            intent["request"] == request,
            "METADATA_APPLY_CONFLICT",
            "Operation ID is already bound to another request",
        )
        _check(ctx)
        return result
    preview = get_preview(ctx, preview_operation_id)
    _require(
        preview["preview_id"] == expected_preview_id,
        "METADATA_APPLY_CONFLICT",
        "Expected preview does not match the retained preview",
    )
    intent = _seal(
        {"schema": 1, "request": request, "binding": _binding(preview)}, "intent_id"
    )
    with pinned_directory(ctx.state.path.parent):
        run.parent.mkdir(exist_ok=True)
        with pinned_directory(run.parent):
            _check(ctx)
            try:
                run.mkdir()
            except FileExistsError as exc:
                raise CoreError(
                    "METADATA_APPLY_RECOVERY_REQUIRED",
                    "Another caller owns this operation ID; read its result",
                ) from exc
            with pinned_directory(run):
                write_record(run / "intent.json", intent)
                try:
                    status, reasons = _evaluate(ctx, intent, preview)
                    _check(ctx)
                except CoreError as exc:
                    status = "revoked" if exc.code == "PROJECT_FORBIDDEN" else "failed"
                    write_record(
                        run / "result.json", _result(intent, status, [exc.code])
                    )
                    raise
                result = _result(intent, status, reasons)
                write_record(run / "result.json", result)
    return result


def apply_metadata(ctx, operation_id):
    """Recheck preflight inputs, then refuse: no live writer is implemented."""
    _check(ctx)
    intent, _ = _load(ctx, operation_id)
    request = intent["request"]
    _require(
        ctx.snapshot is not None
        and asdict(ctx.snapshot) == request["expected_head"]["snapshot"],
        "METADATA_APPLY_STALE",
        "Selected snapshot differs from the preflight",
    )
    status, _ = _evaluate(
        ctx, intent, get_preview(ctx, request["preview_operation_id"])
    )
    _check(ctx)
    _require(status != "stale", "METADATA_APPLY_STALE", "Preflight inputs are stale")
    raise CoreError(
        "METADATA_LIVE_APPLY_UNAVAILABLE",
        "Live metadata apply has no qualified write and recovery protocol",
    )


def undo_metadata(ctx, operation_id):
    """A preflight receipt is not an apply receipt and cannot authorize undo."""
    get_apply_result(ctx, operation_id)
    raise CoreError(
        "METADATA_UNDO_UNAVAILABLE",
        "This operation has no live apply receipt or owned result to restore",
    )
