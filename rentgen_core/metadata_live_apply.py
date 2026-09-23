"""Transactional writer for the supported Designer XML metadata proposal.

This module deliberately exposes a narrow capability.  It never invokes the
1C platform: a retained, already verified candidate is applied to the
registered Designer XML source tree with a journal and compare-and-swap undo.
Unsupported candidates fail closed before any source byte is changed.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

from . import metadata_apply as preflight
from . import metadata_runs
from ._windows_source_tree import pinned_directory, read_retained
from ._live_recovery_stage import prepare_recovery_stage
from .edt_inventory import exported_inventory
from .edt_profiles import parse_json
from .edt_execution import write_record
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .metadata_plans import validate_plan
from .snapshots import validate_operation_id
from .source_paths import validate_file_paths

SCHEMA = 1
MAX_CHANGED_FILES = 64
MAX_FILE_BYTES = 64 * 1024 * 1024
RECOVERY = "METADATA_LIVE_RECOVERY_REQUIRED"


def _require(condition, code, message):
    if not condition:
        raise CoreError(code, message)


def journal_path(ctx, operation_id):
    return (
        ctx.state.path.parent
        / "metadata-live-apply"
        / validate_operation_id(operation_id)
    )


def _seal(value, key):
    return {**value, key: sha256(canonical_bytes(value))}


def _read(path, key):
    try:
        value = parse_json(read_retained(Path(path), 8 * 1024 * 1024))
    except (CoreError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CoreError(
            RECOVERY, "Live apply journal is incomplete or unreadable"
        ) from exc
    _require(
        type(value) is dict and key in value, RECOVERY, "Live receipt is malformed"
    )
    _require(
        _seal({k: v for k, v in value.items() if k != key}, key) == value,
        RECOVERY,
        "Live receipt hash differs",
    )
    return value


def _lock_path(ctx):
    return ctx.state.path.parent / "metadata-live-apply.lock"


@contextmanager
def _project_lock(ctx):
    """Hold one OS lock for all live source writers of a project."""
    root = ctx.state.path.parent.resolve()
    _require(
        root.is_dir() and not root.is_symlink(),
        RECOVERY,
        "Live apply state root is unsafe",
    )
    lock = _lock_path(ctx)
    _require(not lock.is_symlink(), RECOVERY, "Live apply lock is a link")
    if not lock.exists():
        try:
            with lock.open("xb") as stream:
                stream.write(b"0")
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError:
            pass
    _require(lock.is_file(), RECOVERY, "Live apply lock is not a regular file")
    try:
        stream = lock.open("r+b")
    except OSError as exc:
        raise CoreError(RECOVERY, "Live apply lock could not be opened") from exc
    acquired = False
    try:
        _require(stream.seek(0) == 0, RECOVERY, "Live apply lock is invalid")
        if stream.read(1) != b"0":
            raise CoreError(RECOVERY, "Live apply lock is incomplete")
        stream.seek(0, os.SEEK_END)
        _require(stream.tell() == 1, RECOVERY, "Live apply lock is malformed")
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise CoreError(
                "METADATA_LIVE_APPLY_BUSY", "Another live metadata operation is active"
            ) from exc
        yield
    finally:
        try:
            if acquired:
                if os.name == "nt":
                    import msvcrt

                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def _check(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"project:read", "source:edit", "analysis:run"})


def _rows_map(rows):
    _require(type(rows) is list, RECOVERY, "Inventory is malformed")
    paths = []
    for row in rows:
        _require(
            type(row) is dict and type(row.get("path")) is str,
            RECOVERY,
            "Inventory row path is malformed",
        )
        paths.append(row["path"])
    validate_file_paths(paths)
    result = {}
    for row in rows:
        _require(
            type(row) is dict
            and set(row) == {"path", "size", "sha256"}
            and type(row["path"]) is str
            and type(row["size"]) is int
            and row["size"] >= 0
            and type(row["sha256"]) is str
            and preflight.HASH.fullmatch(row["sha256"]),
            RECOVERY,
            "Inventory row is malformed",
        )
        _require(row["path"] not in result, RECOVERY, "Inventory has duplicate paths")
        result[row["path"]] = row
    return result


def _candidate_delta(ctx, operation_id):
    intent, result = preflight._load(ctx, operation_id)
    _require(
        result["status"] == "unavailable",
        "METADATA_LIVE_APPLY_CONFLICT",
        "Live apply requires an unused preflight receipt",
    )
    request = intent["request"]
    preview = metadata_runs.get_preview(ctx, request["preview_operation_id"])
    _require(
        preview["preview_id"] == request["expected_preview_id"],
        "METADATA_LIVE_APPLY_CONFLICT",
        "Retained preview differs from the preflight",
    )
    _require(
        not ctx.state.path.parent.resolve().is_relative_to(ctx.source_root.resolve()),
        "METADATA_LIVE_APPLY_UNSUPPORTED",
        "Live journal must remain outside the source tree",
    )
    status, _ = preflight._evaluate(ctx, intent, preview)
    _require(
        status == "unavailable",
        "METADATA_LIVE_APPLY_STALE",
        "Live source or project head differs from the preflight",
    )
    with pinned_directory(metadata_runs.run_path(ctx, request["preview_operation_id"])):
        validate_plan(
            ctx,
            metadata_runs._request(
                ctx,
                metadata_runs.run_path(ctx, request["preview_operation_id"]),
                request["preview_operation_id"],
            )["plan"],
        )
    preview_body = preview["preview"]
    original = _rows_map(preview_body["inventories"]["original"])
    baseline = _rows_map(preview_body["inventories"]["baseline"])
    candidate = _rows_map(preview_body["inventories"]["candidate"])
    _require(
        set(candidate) <= set(original),
        "METADATA_LIVE_APPLY_UNSUPPORTED",
        "Live writer does not add source paths",
    )
    changed = sorted(
        path
        for path in candidate
        if original[path]["sha256"] != candidate[path]["sha256"]
    )
    _require(
        1 <= len(changed) <= MAX_CHANGED_FILES,
        "METADATA_LIVE_APPLY_UNSUPPORTED",
        "Candidate has no bounded file edit",
    )
    edit_changes = preview_body["edit"]["changes"]
    normalization_changes = preview_body["normalization"]["changes"]
    edit_paths = [item.get("path") for item in edit_changes]
    _require(
        len(edit_paths) == len(set(edit_paths)) and sorted(edit_paths) == changed,
        "METADATA_LIVE_APPLY_UNSUPPORTED",
        "Candidate edit paths are ambiguous or incomplete",
    )
    for item in normalization_changes:
        path = item.get("path")
        if item.get("kind") == "deleted":
            _require(
                path not in candidate
                and path in original
                and item.get("before") == original[path]
                and item.get("after") is None,
                "METADATA_LIVE_APPLY_UNSUPPORTED",
                "Normalization deletion is not fully accounted for",
            )
        else:
            _require(
                item.get("kind") == "modified"
                and path in original
                and path in baseline
                and path in candidate
                and path in edit_paths
                and item.get("before") == original[path]
                and item.get("after") == baseline[path],
                "METADATA_LIVE_APPLY_UNSUPPORTED",
                "Normalization change is not fully accounted for",
            )
    _require(
        all(
            item.get("kind") == "modified"
            and item.get("path") in baseline
            and item.get("path") in candidate
            and item.get("before") == baseline[item.get("path")]
            and item.get("after") == candidate[item.get("path")]
            for item in edit_changes
        ),
        "METADATA_LIVE_APPLY_UNSUPPORTED",
        "Only a fully accounted-for metadata edit is supported",
    )
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"project:read", "source:edit", "analysis:run"})
        layers = tx.get_snapshot_layers(ctx.snapshot.snapshot_id)
    _require(
        len(layers) == 1
        and layers[0].kind == "base"
        and layers[0].source_format == "designer_xml",
        "METADATA_LIVE_APPLY_UNSUPPORTED",
        "A single base Designer XML layer is required",
    )
    return intent, preview, original, candidate, changed


def _expected_rows(original, candidate, changed):
    return [candidate.get(path, original[path]) for path in sorted(original)]


def _source_rows(ctx):
    return exported_inventory(ctx.source_root, authorize=lambda: _check(ctx))


def _same_volume(ctx):
    try:
        source = ctx.source_root.stat().st_dev
        state = ctx.state.path.parent.stat().st_dev
        return source == state and (
            os.name != "nt"
            or os.path.normcase(ctx.source_root.drive)
            == os.path.normcase(ctx.state.path.parent.drive)
        )
    except OSError as exc:
        raise CoreError(RECOVERY, "Live source volume cannot be verified") from exc


def _write_bytes(path, raw):
    _require(len(raw) <= MAX_FILE_BYTES, RECOVERY, "Live source file exceeds limits")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _replace_record(path, value):
    temporary = Path(path).with_name(Path(path).name + ".tmp")
    if temporary.exists() or temporary.is_symlink():
        key = "state_id" if Path(path).name == "state.json" else "result_id"
        _require(
            _read(temporary, key) == value,
            RECOVERY,
            "Live receipt replacement has conflicting staging",
        )
    else:
        write_record(temporary, value)
    os.replace(temporary, path)


def _copy_row(source, target, row):
    raw = read_retained(source / row["path"], MAX_FILE_BYTES)
    _require(
        len(raw) == row["size"] and hashlib.sha256(raw).hexdigest() == row["sha256"],
        RECOVERY,
        "Staged source bytes differ from their inventory",
    )
    _write_bytes(target / row["path"], raw)


def _safe_target(path):
    _require(
        path.is_file() and not path.is_symlink(),
        RECOVERY,
        "Live target is not a regular file",
    )


def _intent(intent, original, candidate, changed):
    request = intent["request"]
    return _seal(
        {
            "schema": SCHEMA,
            "project_id": request["project_id"],
            "operation_id": request["operation_id"],
            "preview_id": request["expected_preview_id"],
            "preflight_intent_id": intent["intent_id"],
            "source_root": request["source_root"],
            "changed_paths": changed,
            "before_inventory": [original[path] for path in sorted(original)],
            "after_inventory": _expected_rows(original, candidate, changed),
        },
        "intent_id",
    )


def _state(journal, phase, **extra):
    return _seal({"schema": SCHEMA, "phase": phase, **extra}, "state_id")


def _read_intent(journal):
    value = _read(journal / "intent.json", "intent_id")
    _require(
        set(value)
        == {
            "schema",
            "project_id",
            "operation_id",
            "preview_id",
            "preflight_intent_id",
            "source_root",
            "changed_paths",
            "before_inventory",
            "after_inventory",
            "intent_id",
        }
        and value["schema"] == SCHEMA
        and type(value["project_id"]) is str
        and type(value["operation_id"]) is str
        and type(value["preview_id"]) is str
        and preflight.HASH.fullmatch(value["preview_id"])
        and type(value["source_root"]) is str
        and Path(value["source_root"]).is_absolute()
        and type(value["changed_paths"]) is list
        and all(type(path) is str for path in value["changed_paths"]),
        RECOVERY,
        "Live apply intent has an invalid schema",
    )
    before, after = _rows_map(value["before_inventory"]), _rows_map(
        value["after_inventory"]
    )
    _require(
        value["changed_paths"] == sorted(value["changed_paths"])
        and set(value["changed_paths"])
        == {path for path in before if before[path] != after.get(path)}
        and set(before) == set(after),
        RECOVERY,
        "Live apply intent inventories are inconsistent",
    )
    return value, before, after


def _read_state(journal, name="state.json"):
    path = journal / name
    if not path.exists() and not path.is_symlink():
        return None
    value = _read(path, "state_id")
    _require(
        set(value) >= {"schema", "phase", "state_id"}
        and value["schema"] == SCHEMA
        and value["phase"]
        in {"prepared", "applying", "complete", "undoing", "undone", "recovered"},
        RECOVERY,
        "Live apply state has an invalid schema",
    )
    return value


def _result(journal, name="result.json"):
    path = journal / name
    if not path.exists() and not path.is_symlink():
        return None
    value = _read(path, "result_id")
    _require(
        set(value)
        == {
            "schema",
            "project_id",
            "operation_id",
            "preview_id",
            "status",
            "changed_paths",
            "before_digest",
            "after_digest",
            "live_source_written",
            "result_id",
        }
        and value["schema"] == SCHEMA
        and value["status"] in {"applied", "undone", "recovered"}
        and type(value["live_source_written"]) is bool
        and value["live_source_written"] is True
        and type(value["project_id"]) is str
        and type(value["operation_id"]) is str
        and all(
            type(value[key]) is str and preflight.HASH.fullmatch(value[key])
            for key in ("preview_id", "before_digest", "after_digest")
        )
        and type(value["changed_paths"]) is list
        and all(type(path) is str for path in value["changed_paths"]),
        RECOVERY,
        "Live apply result has an invalid schema",
    )
    return value


def _validate_result_binding(result, intent, before, after):
    if result is None:
        return
    _require(
        result["project_id"] == intent["project_id"]
        and result["operation_id"] == intent["operation_id"]
        and result["preview_id"] == intent["preview_id"]
        and result["changed_paths"] == intent["changed_paths"]
        and result["before_digest"] == _digest(list(before.values()))
        and result["after_digest"] == _digest(list(after.values())),
        RECOVERY,
        "Live apply result is bound to another operation",
    )


def _digest(rows):
    return sha256(canonical_bytes(rows))


def _status_locked(ctx, operation_id):
    journal = journal_path(ctx, operation_id)
    _require(
        journal.is_dir() and not journal.is_symlink(),
        "METADATA_LIVE_APPLY_NOT_FOUND",
        "Live apply operation was not found",
    )
    intent, before, after = _read_intent(journal)
    result = _result(journal)
    state = _read_state(journal)
    if result is not None:
        _validate_result_binding(result, intent, before, after)
        _require(
            result["project_id"] == ctx.project_id
            and result["operation_id"] == operation_id,
            RECOVERY,
            "Live operation belongs to another project",
        )
        if state is not None:
            terminal_phase = {
                "applied": "complete",
                "undone": "undone",
                "recovered": "recovered",
            }[result["status"]]
            if state["phase"] == terminal_phase:
                _require(
                    state.get("result_id") == result["result_id"],
                    RECOVERY,
                    "Live terminal state differs from result",
                )
                return result
            _require(
                state["phase"] not in {"complete", "undone", "recovered"},
                RECOVERY,
                "Live terminal state differs from result",
            )
    return _seal(
        {
            "schema": SCHEMA,
            "project_id": ctx.project_id,
            "operation_id": operation_id,
            "preview_id": intent["preview_id"],
            "status": "OUTCOME_UNKNOWN",
            "changed_paths": intent["changed_paths"],
            "before_digest": _digest(list(before.values())),
            "after_digest": _digest(list(after.values())),
            "live_source_written": False,
            "phase": state["phase"] if state else "missing",
        },
        "result_id",
    )


def _finish_terminal(ctx, journal, operation_id, before, result):
    _require(
        _source_rows(ctx) == list(before.values()),
        "METADATA_LIVE_UNDO_CONFLICT",
        "Live source differs from the terminal receipt",
    )
    state = _read_state(journal)
    _require(
        state is not None and state["phase"] in {"undoing", result["status"]},
        RECOVERY,
        "Live terminal state differs from result",
    )
    if state["phase"] == result["status"]:
        _require(
            state.get("result_id") == result["result_id"],
            RECOVERY,
            "Live terminal state differs from result",
        )
        return result
    _replace_record(
        journal / "state.json",
        _state(
            journal,
            result["status"],
            operation_id=operation_id,
            result_id=result["result_id"],
        ),
    )
    return result


def _promote_pending_terminal(
    ctx, journal, operation_id, intent, before, after, result
):
    pending = _result(journal, "result.json.tmp")
    if pending is None:
        return None
    _validate_result_binding(pending, intent, before, after)
    state = _read_state(journal)
    _require(
        pending["status"] in {"undone", "recovered"}
        and (result is None or result["status"] == "applied")
        and state is not None
        and state["phase"] == "undoing",
        RECOVERY,
        "Live pending result conflicts with journal state",
    )
    _require(
        _source_rows(ctx) == list(before.values()),
        "METADATA_LIVE_UNDO_CONFLICT",
        "Live source differs from the pending terminal receipt",
    )
    os.replace(journal / "result.json.tmp", journal / "result.json")
    return _finish_terminal(ctx, journal, operation_id, before, pending)


def _promote_pending_state(ctx, journal, operation_id, before, after, result):
    pending = _read_state(journal, "state.json.tmp")
    if pending is None:
        return
    state = _read_state(journal)
    _require(
        pending.get("operation_id") == operation_id
        and (state is None or state.get("operation_id") == operation_id),
        RECOVERY,
        "Live pending state is bound to another operation",
    )
    phase = pending["phase"]
    expected_keys = {"schema", "phase", "operation_id", "state_id"}
    if phase in {"complete", "undone", "recovered"}:
        expected_keys.add("result_id")
    _require(set(pending) == expected_keys, RECOVERY, "Live pending state is malformed")
    if phase == "applying":
        valid = state is not None and state["phase"] == "prepared" and result is None
    elif phase == "complete":
        valid = (
            state is not None
            and state["phase"] == "applying"
            and result is not None
            and result["status"] == "applied"
            and pending["result_id"] == result["result_id"]
            and _source_rows(ctx) == list(after.values())
        )
    elif phase == "undoing":
        origin = state["phase"] if state is not None else "missing"
        valid = (
            origin in {"missing", "prepared", "applying", "complete", "undoing"}
            and (result is None or result["status"] == "applied")
            and (origin not in {"missing", "prepared"} or result is None)
            and (
                origin != "complete"
                or (
                    result is not None and state.get("result_id") == result["result_id"]
                )
            )
            and (origin != "undoing" or pending == state)
        )
    elif phase in {"undone", "recovered"}:
        valid = (
            state is not None
            and state["phase"] == "undoing"
            and result is not None
            and result["status"] == phase
            and pending["result_id"] == result["result_id"]
            and _source_rows(ctx) == list(before.values())
        )
    else:
        valid = False
    _require(valid, RECOVERY, "Live pending state conflicts with journal")
    os.replace(journal / "state.json.tmp", journal / "state.json")


def get_live_status(ctx, operation_id):
    _check(ctx)
    with _project_lock(ctx):
        _check(ctx)
        return _status_locked(ctx, operation_id)


def _new_journal(ctx, intent):
    path = journal_path(ctx, intent["operation_id"])
    parent = path.parent
    if parent.exists():
        _require(
            parent.is_dir() and not parent.is_symlink(),
            RECOVERY,
            "Live apply journal root is unsafe",
        )
    else:
        parent.mkdir()
    _require(
        not path.exists(),
        "METADATA_LIVE_APPLY_CONFLICT",
        "Operation ID is already used",
    )
    path.mkdir()
    write_record(path / "intent.json", intent)
    return path


def apply_live(ctx, operation_id):
    """Apply a supported retained candidate to the registered source tree."""
    _check(ctx)
    validate_operation_id(operation_id)
    with _project_lock(ctx):
        _check(ctx)
        journal = journal_path(ctx, operation_id)
        if journal.exists():
            existing = _status_locked(ctx, operation_id)
            if existing["status"] == "applied":
                _, _, _, after, _ = _load_for_mutation(ctx, operation_id)
                _require(
                    _source_rows(ctx) == list(after.values()),
                    "METADATA_LIVE_APPLY_CONFLICT",
                    "Live source changed after the applied receipt",
                )
                return existing
            raise CoreError(
                RECOVERY, "Existing live operation must be reconciled explicitly"
            )
        _require(
            _same_volume(ctx),
            "METADATA_LIVE_APPLY_UNSUPPORTED",
            "Live source and journal must be on one volume",
        )
        intent, preview, original, candidate, changed = _candidate_delta(
            ctx, operation_id
        )
        expected_current = list(original.values())
        actual = _source_rows(ctx)
        _require(
            actual == expected_current,
            "METADATA_LIVE_APPLY_STALE",
            "Live source differs from the retained preflight",
        )
        live_intent = _intent(intent, original, candidate, changed)
        journal = _new_journal(ctx, live_intent)
        backup, stage = journal / "backup", journal / "stage"
        backup.mkdir()
        stage.mkdir()
        try:
            for path in changed:
                _check(ctx)
                _copy_row(ctx.source_root, backup, original[path])
                candidate_path = metadata_runs.run_path(
                    ctx, intent["request"]["preview_operation_id"]
                )
                _copy_row(candidate_path / "candidate-xml", stage, candidate[path])
            write_record(
                journal / "state.json",
                _state(journal, "prepared", operation_id=operation_id),
            )
            _replace_record(
                journal / "state.json",
                _state(journal, "applying", operation_id=operation_id),
            )
            current_expected = expected_current
            for path in changed:
                _check(ctx)
                _require(
                    _source_rows(ctx) == current_expected,
                    "METADATA_LIVE_APPLY_STALE",
                    "Live source changed during publication",
                )
                target = ctx.source_root / path
                _safe_target(target)
                staged = stage / path
                _require(
                    staged.is_file() and not staged.is_symlink(),
                    RECOVERY,
                    "Candidate staging is incomplete",
                )
                os.replace(staged, target)
                current_map = {row["path"]: row for row in current_expected}
                current_map[path] = candidate[path]
                current_expected = [current_map[name] for name in sorted(current_map)]
            after = _source_rows(ctx)
            expected_after = _expected_rows(original, candidate, changed)
            _require(
                after == expected_after,
                RECOVERY,
                "Live source differs after publication; explicit recovery is required",
            )
            result = _seal(
                {
                    "schema": SCHEMA,
                    "project_id": ctx.project_id,
                    "operation_id": operation_id,
                    "preview_id": live_intent["preview_id"],
                    "status": "applied",
                    "changed_paths": changed,
                    "before_digest": _digest(expected_current),
                    "after_digest": _digest(expected_after),
                    "live_source_written": True,
                },
                "result_id",
            )
            write_record(journal / "result.json", result)
            _replace_record(
                journal / "state.json",
                _state(
                    journal,
                    "complete",
                    operation_id=operation_id,
                    result_id=result["result_id"],
                ),
            )
            return result
        except BaseException:
            raise


def _load_for_mutation(ctx, operation_id):
    journal = journal_path(ctx, operation_id)
    _require(
        journal.is_dir() and not journal.is_symlink(),
        "METADATA_LIVE_APPLY_NOT_FOUND",
        "Live apply operation was not found",
    )
    intent, before, after = _read_intent(journal)
    _require(
        intent["project_id"] == ctx.project_id
        and intent["operation_id"] == operation_id,
        RECOVERY,
        "Live operation belongs to another project",
    )
    _require(
        Path(intent["source_root"]).resolve() == ctx.source_root.resolve(),
        RECOVERY,
        "Live operation is bound to another source root",
    )
    result = _result(journal)
    _validate_result_binding(result, intent, before, after)
    return journal, intent, before, after, result


def undo_live(ctx, operation_id):
    _check(ctx)
    validate_operation_id(operation_id)
    with _project_lock(ctx):
        _check(ctx)
        journal, intent, before, after, result = _load_for_mutation(ctx, operation_id)
        _promote_pending_state(ctx, journal, operation_id, before, after, result)
        pending = _promote_pending_terminal(
            ctx, journal, operation_id, intent, before, after, result
        )
        if pending is not None:
            return pending
        if result is not None and result["status"] in {"undone", "recovered"}:
            return _finish_terminal(ctx, journal, operation_id, before, result)
        _require(
            result is not None and result["status"] == "applied",
            RECOVERY,
            "Only a confirmed live apply can be undone",
        )
        actual = _source_rows(ctx)
        _require(
            actual == list(after.values()),
            "METADATA_LIVE_UNDO_CONFLICT",
            "Live source changed after apply",
        )
        _require(
            _same_volume(ctx),
            "METADATA_LIVE_APPLY_UNSUPPORTED",
            "Live source and journal must be on one volume",
        )
        stage = journal / "undo-stage"
        _require(not stage.exists(), RECOVERY, "Undo staging already exists")
        stage.mkdir()
        for path in intent["changed_paths"]:
            _copy_row(journal / "backup", stage, before[path])
        _replace_record(
            journal / "state.json",
            _state(journal, "undoing", operation_id=operation_id),
        )
        try:
            current_expected = list(after.values())
            for path in intent["changed_paths"]:
                _check(ctx)
                _require(
                    _source_rows(ctx) == current_expected,
                    "METADATA_LIVE_UNDO_CONFLICT",
                    "Live source changed during undo",
                )
                target = ctx.source_root / path
                _safe_target(target)
                os.replace(stage / path, target)
                current_map = {row["path"]: row for row in current_expected}
                current_map[path] = before[path]
                current_expected = [current_map[name] for name in sorted(current_map)]
            _require(
                _source_rows(ctx) == list(before.values()),
                RECOVERY,
                "Undo result differs from original inventory",
            )
            undone = _seal(
                {
                    "schema": SCHEMA,
                    "project_id": ctx.project_id,
                    "operation_id": operation_id,
                    "preview_id": intent["preview_id"],
                    "status": "undone",
                    "changed_paths": intent["changed_paths"],
                    "before_digest": _digest(list(before.values())),
                    "after_digest": _digest(list(after.values())),
                    "live_source_written": True,
                },
                "result_id",
            )
            _replace_record(journal / "result.json", undone)
            _replace_record(
                journal / "state.json",
                _state(
                    journal,
                    "undone",
                    operation_id=operation_id,
                    result_id=undone["result_id"],
                ),
            )
            return undone
        except BaseException:
            raise


def recover_live(ctx, operation_id, *, target):
    """Recover an interrupted publication using only its sealed backup."""
    _check(ctx)
    validate_operation_id(operation_id)
    _require(
        target == "original",
        "METADATA_LIVE_RECOVERY_REQUIRED",
        "Only original recovery is supported",
    )
    with _project_lock(ctx):
        _check(ctx)
        journal, intent, before, after, result = _load_for_mutation(ctx, operation_id)
        _promote_pending_state(ctx, journal, operation_id, before, after, result)
        pending = _promote_pending_terminal(
            ctx, journal, operation_id, intent, before, after, result
        )
        if pending is not None:
            return pending
        if result is not None and result["status"] in {"undone", "recovered"}:
            return _finish_terminal(ctx, journal, operation_id, before, result)
        _require(
            result is None or result["status"] == "applied",
            RECOVERY,
            "Live operation cannot be recovered",
        )
        for path in intent["changed_paths"]:
            _require(
                (journal / "backup" / path).is_file(),
                RECOVERY,
                "Live backup is incomplete",
            )
        current = _source_rows(ctx)
        current_map = {row["path"]: row for row in current}
        for path in intent["changed_paths"]:
            row = current_map.get(path)
            _require(
                row is None or row == before.get(path) or row == after.get(path),
                "METADATA_LIVE_UNDO_CONFLICT",
                "Live source contains foreign bytes",
            )
        _require(
            _same_volume(ctx),
            "METADATA_LIVE_APPLY_UNSUPPORTED",
            "Live source and journal must be on one volume",
        )
        stage = prepare_recovery_stage(
            journal,
            intent["changed_paths"],
            before,
            copy_row=_copy_row,
            max_bytes=MAX_FILE_BYTES,
            code=RECOVERY,
        )
        _replace_record(
            journal / "state.json",
            _state(journal, "undoing", operation_id=operation_id),
        )
        for path in intent["changed_paths"]:
            _check(ctx)
            target_path = ctx.source_root / path
            current_row = current_map.get(path)
            if current_row == before[path]:
                continue
            _require(
                not target_path.is_symlink(),
                RECOVERY,
                "Recovery target is unsafe",
            )
            if target_path.exists():
                _safe_target(target_path)
            os.replace(stage / path, target_path)
        _require(
            _source_rows(ctx) == list(before.values()),
            RECOVERY,
            "Recovery does not restore original inventory",
        )
        recovered = _seal(
            {
                "schema": SCHEMA,
                "project_id": ctx.project_id,
                "operation_id": operation_id,
                "preview_id": intent["preview_id"],
                "status": "recovered",
                "changed_paths": intent["changed_paths"],
                "before_digest": _digest(list(before.values())),
                "after_digest": _digest(list(after.values())),
                "live_source_written": True,
            },
            "result_id",
        )
        _replace_record(journal / "result.json", recovered)
        _replace_record(
            journal / "state.json",
            _state(
                journal,
                "recovered",
                operation_id=operation_id,
                result_id=recovered["result_id"],
            ),
        )
        return recovered
