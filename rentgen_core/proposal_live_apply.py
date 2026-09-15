"""Bounded direct BSL proposal writer with sealed CAS recovery journals.

The writer accepts only an already validated :class:`Proposal` for one existing
base Designer XML source file.  It writes bytes atomically, records the full
source inventory before and after the operation, and never silently retries an
uncertain filesystem outcome.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path

from . import metadata_live_apply as _live
from .context import validate_project_id
from .errors import CoreError
from .edt_execution import write_record
from .edt_inventory import exported_inventory
from .manifests import canonical_bytes, sha256
from .proposals import Proposal, ProposalLimits, validate_proposal
from .snapshots import ProjectHead, get_project_head, validate_operation_id
from .source_configuration import get_source_configuration
from .source_paths import validate_file_paths, validate_source_path
from ._windows_source_tree import read_retained


SCHEMA = 1
RECOVERY = "PROPOSAL_LIVE_RECOVERY_REQUIRED"
MAX_FILE_BYTES = 64 * 1024 * 1024
LIMITS = ProposalLimits(1024 * 1024, 1024 * 1024, 1536 * 1024, 256 * 1024)


def _require(condition, code, message):
    if not condition:
        raise CoreError(code, message)


def journal_path(ctx, operation_id):
    return (
        ctx.state.path.parent
        / "proposal-live-apply"
        / validate_operation_id(operation_id)
    )


def _seal(value, key):
    return {**value, key: sha256(canonical_bytes(value))}


def _read(path, key):
    try:
        value = json.loads(read_retained(Path(path), 8 * 1024 * 1024).decode("utf-8"))
    except (CoreError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CoreError(
            RECOVERY, "Proposal live journal is incomplete or unreadable"
        ) from exc
    _require(
        type(value) is dict and key in value,
        RECOVERY,
        "Proposal live record is malformed",
    )
    _require(
        _seal({k: v for k, v in value.items() if k != key}, key) == value,
        RECOVERY,
        "Proposal live record hash differs",
    )
    return value


def _check(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"project:read", "source:edit", "analysis:run"})


@contextmanager
def _project_lock(ctx):
    # Keep one lock namespace for all direct source writers of a project.
    with _live._project_lock(ctx):
        yield


def _source_rows(ctx):
    return exported_inventory(ctx.source_root, authorize=lambda: _check(ctx))


def _digest(rows):
    return sha256(canonical_bytes(rows))


def _rows_map(rows):
    _require(type(rows) is list, RECOVERY, "Inventory is malformed")
    paths = []
    result = {}
    for row in rows:
        _require(
            type(row) is dict
            and set(row) == {"path", "size", "sha256"}
            and type(row["path"]) is str
            and type(row["size"]) is int
            and row["size"] >= 0
            and type(row["sha256"]) is str
            and _live.preflight.HASH.fullmatch(row["sha256"]),
            RECOVERY,
            "Inventory row is malformed",
        )
        paths.append(row["path"])
        _require(row["path"] not in result, RECOVERY, "Inventory has duplicate paths")
        result[row["path"]] = row
    validate_file_paths(paths)
    return result


def _write_bytes(path, raw):
    _require(
        type(raw) is bytes and len(raw) <= MAX_FILE_BYTES,
        RECOVERY,
        "Staged source file exceeds limits",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _replace_record(path, value):
    temporary = Path(path).with_name(Path(path).name + ".tmp")
    _require(
        not temporary.exists(),
        RECOVERY,
        "Proposal live receipt replacement has unresolved staging",
    )
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


def _validate_source_ref_document(value):
    try:
        project_id = validate_project_id(value["snapshot"]["project_id"])
        relative_path = validate_source_path(value["relative_path"])
    except (CoreError, KeyError, TypeError) as exc:
        raise CoreError(
            RECOVERY, "Proposal live source reference is malformed"
        ) from exc
    _require(
        type(value) is dict
        and set(value) == {"snapshot", "layer_id", "relative_path", "raw_sha256"}
        and type(value["snapshot"]) is dict
        and set(value["snapshot"]) == {"project_id", "snapshot_id", "manifest_hash"}
        and project_id == value["snapshot"]["project_id"]
        and type(value["snapshot"]["snapshot_id"]) is str
        and _live.preflight.HASH.fullmatch(value["snapshot"]["snapshot_id"])
        and value["snapshot"]["manifest_hash"] == value["snapshot"]["snapshot_id"]
        and value["layer_id"] == "base"
        and type(value["relative_path"]) is str
        and value["relative_path"].lower().endswith(".bsl")
        and relative_path == value["relative_path"]
        and type(value["raw_sha256"]) is str
        and _live.preflight.HASH.fullmatch(value["raw_sha256"]),
        RECOVERY,
        "Proposal live source reference is malformed",
    )


def _read_intent(journal):
    value = _read(journal / "intent.json", "intent_id")
    try:
        validate_project_id(value.get("project_id"))
        validate_operation_id(value.get("operation_id"))
    except (CoreError, TypeError, ValueError) as exc:
        raise CoreError(RECOVERY, "Proposal live intent identity is invalid") from exc
    _require(
        set(value)
        == {
            "schema",
            "project_id",
            "operation_id",
            "source_root",
            "layer_id",
            "source_ref",
            "proposal_content_id",
            "changed_paths",
            "before_inventory",
            "after_inventory",
            "before_digest",
            "after_digest",
            "intent_id",
        }
        and value["schema"] == SCHEMA
        and validate_project_id(value["project_id"]) == value["project_id"]
        and type(value["operation_id"]) is str
        and type(value["source_root"]) is str
        and Path(value["source_root"]).is_absolute()
        and type(value["layer_id"]) is str
        and value["layer_id"] == "base"
        and type(value["proposal_content_id"]) is str
        and _live.preflight.HASH.fullmatch(value["proposal_content_id"])
        and type(value["changed_paths"]) is list
        and all(type(path) is str for path in value["changed_paths"]),
        RECOVERY,
        "Proposal live intent has an invalid schema",
    )
    _validate_source_ref_document(value["source_ref"])
    _require(
        value["source_ref"]["snapshot"]["project_id"] == value["project_id"]
        and value["source_ref"]["layer_id"] == value["layer_id"]
        and len(value["changed_paths"]) == 1
        and value["changed_paths"][0].lower().endswith(".bsl"),
        RECOVERY,
        "Proposal live intent source binding is invalid",
    )
    before, after = _rows_map(value["before_inventory"]), _rows_map(
        value["after_inventory"]
    )
    _require(
        value["changed_paths"] == sorted(value["changed_paths"])
        and set(value["changed_paths"])
        == {path for path in before if before[path] != after.get(path)}
        and set(before) == set(after)
        and value["before_digest"] == _digest(list(before.values()))
        and value["after_digest"] == _digest(list(after.values())),
        RECOVERY,
        "Proposal live intent inventories are inconsistent",
    )
    return value, before, after


def _read_state(journal):
    if not (journal / "state.json").exists():
        return None
    value = _read(journal / "state.json", "state_id")
    _require(
        set(value) >= {"schema", "phase", "state_id"}
        and value["schema"] == SCHEMA
        and value["phase"]
        in {"prepared", "applying", "complete", "undoing", "undone", "recovered"},
        RECOVERY,
        "Proposal live state has an invalid schema",
    )
    return value


def _read_result(journal):
    if not (journal / "result.json").exists():
        return None
    value = _read(journal / "result.json", "result_id")
    _require(
        set(value)
        == {
            "schema",
            "project_id",
            "operation_id",
            "proposal_content_id",
            "source_ref",
            "status",
            "changed_paths",
            "before_digest",
            "after_digest",
            "live_source_written",
            "result_id",
        }
        and value["schema"] == SCHEMA
        and value["status"] in {"applied", "undone", "recovered"}
        and value["live_source_written"] is True
        and type(value["project_id"]) is str
        and type(value["operation_id"]) is str
        and type(value["proposal_content_id"]) is str
        and _live.preflight.HASH.fullmatch(value["proposal_content_id"])
        and type(value["source_ref"]) is dict
        and type(value["changed_paths"]) is list
        and all(type(path) is str for path in value["changed_paths"])
        and all(
            type(value[key]) is str and _live.preflight.HASH.fullmatch(value[key])
            for key in ("before_digest", "after_digest")
        ),
        RECOVERY,
        "Proposal live result has an invalid schema",
    )
    _validate_source_ref_document(value["source_ref"])
    _require(
        len(value["changed_paths"]) == 1
        and value["changed_paths"][0].lower().endswith(".bsl"),
        RECOVERY,
        "Proposal live result source binding is invalid",
    )
    return value


def _load_for_mutation(ctx, operation_id):
    journal = journal_path(ctx, operation_id)
    _require(
        journal.is_dir() and not journal.is_symlink(),
        "PROPOSAL_LIVE_NOT_FOUND",
        "Proposal live operation was not found",
    )
    intent, before, after = _read_intent(journal)
    _require(
        intent["project_id"] == ctx.project_id
        and intent["operation_id"] == operation_id,
        RECOVERY,
        "Proposal live operation belongs to another project",
    )
    _require(
        Path(intent["source_root"]).resolve() == ctx.source_root.resolve(),
        RECOVERY,
        "Proposal live operation is bound to another source root",
    )
    result = _read_result(journal)
    if result is not None:
        _require(
            result["project_id"] == intent["project_id"]
            and result["operation_id"] == operation_id
            and result["proposal_content_id"] == intent["proposal_content_id"]
            and result["source_ref"] == intent["source_ref"]
            and result["changed_paths"] == intent["changed_paths"]
            and result["before_digest"] == intent["before_digest"]
            and result["after_digest"] == intent["after_digest"],
            RECOVERY,
            "Proposal live result is bound to another operation",
        )
    return journal, intent, before, after, result


def _new_journal(ctx, intent):
    path = journal_path(ctx, intent["operation_id"])
    parent = path.parent
    if parent.exists():
        _require(
            parent.is_dir() and not parent.is_symlink(),
            RECOVERY,
            "Proposal live journal root is unsafe",
        )
    else:
        parent.mkdir()
    _require(
        not parent.resolve().is_relative_to(ctx.source_root.resolve()),
        "PROPOSAL_LIVE_UNSUPPORTED",
        "Live journal must remain outside the source tree",
    )
    _require(
        not path.exists(), "PROPOSAL_LIVE_CONFLICT", "Operation ID is already used"
    )
    path.mkdir()
    write_record(path / "intent.json", intent)
    return path


def _resolve_target(ctx, proposal):
    _require(
        type(proposal) is Proposal,
        "PROPOSAL_LIVE_UNSUPPORTED",
        "A validated source proposal is required",
    )
    validate_source_path(proposal.source_ref.relative_path)
    _require(
        proposal.source_ref.layer_id == "base",
        "PROPOSAL_LIVE_UNSUPPORTED",
        "Only the base source layer is supported",
    )
    _require(
        proposal.source_ref.relative_path.lower().endswith(".bsl"),
        "PROPOSAL_LIVE_UNSUPPORTED",
        "Only BSL source files are supported",
    )
    configuration = get_source_configuration(ctx)
    layers = {layer.layer_id: layer for layer in configuration.layers}
    layer = layers.get(proposal.source_ref.layer_id)
    _require(
        layer is not None and layer.source_format == "designer_xml",
        "PROPOSAL_LIVE_UNSUPPORTED",
        "A base Designer XML source layer is required",
    )
    target = (
        ctx.source_root / layer.root_relative_path / proposal.source_ref.relative_path
    )
    _require(
        target.absolute().is_relative_to(ctx.source_root.resolve()),
        "PROPOSAL_LIVE_UNSUPPORTED",
        "Source target escapes the registered root",
    )
    source_root = ctx.source_root.resolve()
    absolute = target.absolute()
    for ancestor in (absolute, *absolute.parents):
        if ancestor == source_root.parent:
            break
        _require(
            not ancestor.is_symlink(),
            "PROPOSAL_LIVE_UNSUPPORTED",
            "Source target traverses a link",
        )
        if ancestor == source_root:
            break
    return absolute


def _intent(ctx, operation_id, proposal, target, before, after):
    # The source reference is relative to its configured layer root; inventory paths
    # are relative to the registered root, so the intent uses the actual inventory path.
    changed = [target.relative_to(ctx.source_root).as_posix()]
    return _seal(
        {
            "schema": SCHEMA,
            "project_id": ctx.project_id,
            "operation_id": operation_id,
            "source_root": str(ctx.source_root.resolve()),
            "layer_id": proposal.source_ref.layer_id,
            "source_ref": {
                "snapshot": {
                    "project_id": proposal.source_ref.snapshot.project_id,
                    "snapshot_id": proposal.source_ref.snapshot.snapshot_id,
                    "manifest_hash": proposal.source_ref.snapshot.manifest_hash,
                },
                "layer_id": proposal.source_ref.layer_id,
                "relative_path": proposal.source_ref.relative_path,
                "raw_sha256": proposal.source_ref.raw_sha256,
            },
            "proposal_content_id": proposal.content_id,
            "changed_paths": changed,
            "before_inventory": before,
            "after_inventory": after,
            "before_digest": _digest(before),
            "after_digest": _digest(after),
        },
        "intent_id",
    )


def _status_locked(ctx, operation_id):
    journal, intent, before, after, result = _load_for_mutation(ctx, operation_id)
    if result is not None:
        return result
    state = _read_state(journal)
    return _seal(
        {
            "schema": SCHEMA,
            "project_id": ctx.project_id,
            "operation_id": operation_id,
            "proposal_content_id": intent["proposal_content_id"],
            "source_ref": intent["source_ref"],
            "status": "OUTCOME_UNKNOWN",
            "changed_paths": intent["changed_paths"],
            "before_digest": intent["before_digest"],
            "after_digest": intent["after_digest"],
            "live_source_written": False,
            "phase": state["phase"] if state else "missing",
        },
        "result_id",
    )


def get_live_status(ctx, operation_id):
    _check(ctx)
    with _project_lock(ctx):
        _check(ctx)
        return _status_locked(ctx, validate_operation_id(operation_id))


def apply_live(ctx, operation_id, proposal, *, expected_head):
    """Apply one validated BSL proposal with a compare-and-swap source check."""
    _check(ctx)
    validate_operation_id(operation_id)
    _require(
        type(expected_head) is ProjectHead and expected_head == get_project_head(ctx),
        "PROPOSAL_LIVE_STALE",
        "Project head differs from the proposal precondition",
    )
    validated = validate_proposal(ctx, proposal, limits=LIMITS)
    target = _resolve_target(ctx, validated)
    with _project_lock(ctx):
        _check(ctx)
        journal = journal_path(ctx, operation_id)
        if journal.exists():
            existing = _status_locked(ctx, operation_id)
            _, existing_intent, _, existing_after, _ = _load_for_mutation(
                ctx, operation_id
            )
            if (
                existing["status"] == "applied"
                and existing_intent["proposal_content_id"] == validated.content_id
                and _source_rows(ctx) == list(existing_after.values())
            ):
                return existing
            raise CoreError(
                RECOVERY,
                "Existing proposal live operation must be reconciled explicitly",
            )
        before_rows = _source_rows(ctx)
        before_map = _rows_map(before_rows)
        inventory_path = target.relative_to(ctx.source_root).as_posix()
        current = before_map.get(inventory_path)
        _require(
            current is not None and target.is_file() and not target.is_symlink(),
            "PROPOSAL_LIVE_STALE",
            "Live source file differs from the retained proposal",
        )
        _require(
            current["sha256"] == validated.source_ref.raw_sha256
            and current["size"] == validated.original_size_bytes,
            "PROPOSAL_LIVE_STALE",
            "Live source file differs from the retained proposal",
        )
        _require(
            validated.replacement_bytes != read_retained(target, MAX_FILE_BYTES),
            "PROPOSAL_LIVE_UNSUPPORTED",
            "No-op source proposals are not writable",
        )
        after_map = dict(before_map)
        after_map[inventory_path] = {
            "path": inventory_path,
            "size": len(validated.replacement_bytes),
            "sha256": hashlib.sha256(validated.replacement_bytes).hexdigest(),
        }
        after_rows = [after_map[name] for name in sorted(after_map)]
        intent = _intent(ctx, operation_id, validated, target, before_rows, after_rows)
        journal = _new_journal(ctx, intent)
        backup, stage = journal / "backup", journal / "stage"
        backup.mkdir()
        stage.mkdir()
        _copy_row(ctx.source_root, backup, current)
        _write_bytes(stage / inventory_path, validated.replacement_bytes)
        write_record(
            journal / "state.json",
            _seal(
                {"schema": SCHEMA, "phase": "prepared", "operation_id": operation_id},
                "state_id",
            ),
        )
        _replace_record(
            journal / "state.json",
            _seal(
                {"schema": SCHEMA, "phase": "applying", "operation_id": operation_id},
                "state_id",
            ),
        )
        _require(
            _source_rows(ctx) == before_rows,
            "PROPOSAL_LIVE_STALE",
            "Live source changed during publication",
        )
        _safe_target(target)
        os.replace(stage / inventory_path, target)
        _require(
            _source_rows(ctx) == after_rows,
            RECOVERY,
            "Live source differs after publication; explicit recovery is required",
        )
        result = _seal(
            {
                "schema": SCHEMA,
                "project_id": ctx.project_id,
                "operation_id": operation_id,
                "proposal_content_id": validated.content_id,
                "source_ref": intent["source_ref"],
                "status": "applied",
                "changed_paths": intent["changed_paths"],
                "before_digest": intent["before_digest"],
                "after_digest": intent["after_digest"],
                "live_source_written": True,
            },
            "result_id",
        )
        write_record(journal / "result.json", result)
        _replace_record(
            journal / "state.json",
            _seal(
                {
                    "schema": SCHEMA,
                    "phase": "complete",
                    "operation_id": operation_id,
                    "result_id": result["result_id"],
                },
                "state_id",
            ),
        )
        return result


def undo_live(ctx, operation_id):
    _check(ctx)
    validate_operation_id(operation_id)
    with _project_lock(ctx):
        _check(ctx)
        journal, intent, before, after, result = _load_for_mutation(ctx, operation_id)
        if result is not None and result["status"] in {"undone", "recovered"}:
            _require(
                _source_rows(ctx) == list(before.values()),
                "PROPOSAL_LIVE_UNDO_CONFLICT",
                "Live source differs from the terminal undo receipt",
            )
            return result
        _require(
            result is not None and result["status"] == "applied",
            RECOVERY,
            "Only a confirmed live apply can be undone",
        )
        _require(
            _source_rows(ctx) == list(after.values()),
            "PROPOSAL_LIVE_UNDO_CONFLICT",
            "Live source changed after apply",
        )
        stage = journal / "undo-stage"
        _require(not stage.exists(), RECOVERY, "Undo staging already exists")
        stage.mkdir()
        for path in intent["changed_paths"]:
            _copy_row(journal / "backup", stage, before[path])
        _replace_record(
            journal / "state.json",
            _seal(
                {"schema": SCHEMA, "phase": "undoing", "operation_id": operation_id},
                "state_id",
            ),
        )
        for path in intent["changed_paths"]:
            _check(ctx)
            _require(
                _source_rows(ctx) == list(after.values()),
                "PROPOSAL_LIVE_UNDO_CONFLICT",
                "Live source changed during undo",
            )
            target = ctx.source_root / path
            _safe_target(target)
            os.replace(stage / path, target)
        _require(
            _source_rows(ctx) == list(before.values()),
            RECOVERY,
            "Undo result differs from original inventory",
        )
        undone = {**result, "status": "undone"}
        undone = _seal(
            {k: v for k, v in undone.items() if k != "result_id"}, "result_id"
        )
        _replace_record(journal / "result.json", undone)
        _replace_record(
            journal / "state.json",
            _seal(
                {
                    "schema": SCHEMA,
                    "phase": "undone",
                    "operation_id": operation_id,
                    "result_id": undone["result_id"],
                },
                "state_id",
            ),
        )
        return undone


def recover_live(ctx, operation_id, *, target):
    _check(ctx)
    validate_operation_id(operation_id)
    _require(target == "original", RECOVERY, "Only original recovery is supported")
    with _project_lock(ctx):
        _check(ctx)
        journal, intent, before, after, result = _load_for_mutation(ctx, operation_id)
        if result is not None and result["status"] in {"undone", "recovered"}:
            _require(
                _source_rows(ctx) == list(before.values()),
                "PROPOSAL_LIVE_UNDO_CONFLICT",
                "Live source differs from the terminal recovery receipt",
            )
            return result
        _require(
            result is None or result["status"] == "applied",
            RECOVERY,
            "Proposal live operation cannot be recovered",
        )
        for path in intent["changed_paths"]:
            _require(
                (journal / "backup" / path).is_file(),
                RECOVERY,
                "Live backup is incomplete",
            )
        current = _source_rows(ctx)
        current_map = _rows_map(current)
        for path in before:
            if path not in intent["changed_paths"]:
                _require(
                    current_map.get(path) == before[path],
                    "PROPOSAL_LIVE_UNDO_CONFLICT",
                    "Live source contains foreign bytes",
                )
        for path in intent["changed_paths"]:
            current_row = current_map.get(path)
            _require(
                current_row is None
                or current_row == before[path]
                or current_row == after[path],
                "PROPOSAL_LIVE_UNDO_CONFLICT",
                "Live source contains foreign bytes",
            )
        stage = journal / "recovery-stage"
        _require(not stage.exists(), RECOVERY, "Recovery staging already exists")
        stage.mkdir()
        for path in intent["changed_paths"]:
            _copy_row(journal / "backup", stage, before[path])
        _replace_record(
            journal / "state.json",
            _seal(
                {"schema": SCHEMA, "phase": "undoing", "operation_id": operation_id},
                "state_id",
            ),
        )
        for path in intent["changed_paths"]:
            current_row = current_map.get(path)
            if current_row == before[path]:
                continue
            target_path = ctx.source_root / path
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
                "proposal_content_id": intent["proposal_content_id"],
                "source_ref": intent["source_ref"],
                "status": "recovered",
                "changed_paths": intent["changed_paths"],
                "before_digest": intent["before_digest"],
                "after_digest": intent["after_digest"],
                "live_source_written": True,
            },
            "result_id",
        )
        _replace_record(journal / "result.json", recovered)
        _replace_record(
            journal / "state.json",
            _seal(
                {
                    "schema": SCHEMA,
                    "phase": "recovered",
                    "operation_id": operation_id,
                    "result_id": recovered["result_id"],
                },
                "state_id",
            ),
        )
        return recovered
