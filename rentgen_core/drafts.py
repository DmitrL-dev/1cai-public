"""Shared, versioned project drafts. Saving never applies a source change."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import unicodedata

from .access import canonical, principal_value
from .context import Principal, SnapshotRef
from .errors import CoreError
from . import proposals
from .sources import SourceRef
from .snapshots import validate_operation_id

_READ = {"project:read"}
_WRITE = _READ | {"source:edit"}
_LIMITS = proposals.ProposalLimits(1024**2, 1024**2, 1536 * 1024, 256 * 1024)
_ACTIONS = {"draft.saved", "draft.archived", "draft.restored"}


def _boundary(name, **values):
    """Failure injection seam; no production effects."""


def _invalid():
    return CoreError("DRAFT_INVALID", "Invalid draft metadata or pagination")


def _corrupt():
    return CoreError("STATE_CORRUPT", "Stored draft history is inconsistent")


def _uuid(value):
    try:
        return validate_operation_id(value)
    except CoreError as exc:
        raise _invalid() from exc


def _revision(value, *, minimum=0):
    if type(value) is not int or not minimum <= value < 2**63 - 1:
        raise _invalid()
    return value


def _title(value):
    try:
        valid = (
            type(value) is str
            and bool(value.strip())
            and len(value) <= 240
            and len(value.encode("utf-8")) <= 960
            and not any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value)
        )
    except UnicodeError:
        valid = False
    if not valid:
        raise _invalid()
    return value


def _bounded(value):
    encoded = canonical(value)
    if len(encoded.encode("utf-8")) > 65536:
        raise CoreError("DRAFT_LIMIT_EXCEEDED", "Draft receipt exceeds its size limit")
    return encoded


def _require(tx, *, write=False):
    tx.require_all(_WRITE if write else _READ)
    if tx._connection.execute("PRAGMA user_version").fetchone() != (4,):
        raise CoreError("WORKFLOW_SCHEMA_REQUIRED", "Draft history requires schema 4")


def _request(
    actor, action, draft_id, expected_revision, *, title=None, content_id=None
):
    value = {
        "action": action,
        "actor": principal_value(actor),
        "draft_id": _uuid(draft_id),
        "expected_revision": _revision(expected_revision),
    }
    if action == "draft.saved":
        value.update(title=_title(title), proposal_content_id=content_id)
    return value


def _result(
    project_id, operation_id, actor, recorded, request, source_ref, title, content_id
):
    return {
        "project_id": project_id,
        "operation_id": operation_id,
        "action": request["action"],
        "actor": principal_value(actor),
        "recorded_at": recorded,
        "outcome": "committed",
        "draft_id": request["draft_id"],
        "revision": request["expected_revision"] + 1,
        "status": "archived" if request["action"] == "draft.archived" else "active",
        "title": title,
        "proposal_content_id": content_id,
        "source_ref": asdict(source_ref),
    }


def _head(tx, draft_id):
    row = tx._connection.execute(
        "SELECT h.current_revision,(SELECT MAX(revision) FROM workflow_draft_revisions r "
        "WHERE r.project_id=h.project_id AND r.draft_id=h.draft_id) "
        "FROM workflow_draft_heads h WHERE h.project_id=? AND h.draft_id=?",
        (tx._project_id, draft_id),
    ).fetchone()
    if row is None:
        return None
    if type(row[0]) is not int or row[0] != row[1] or row[0] < 1:
        raise _corrupt()
    return row[0]


def _read_revision(tx, draft_id, revision):
    row = tx._connection.execute(
        "SELECT r.proposal_content_id,r.title,r.status,r.operation_id,"
        "a.action,a.action_version,a.actor_id,a.actor_authority,a.recorded_at,a.request_json,a.result_json,"
        "p.snapshot_id,p.layer_id,p.relative_path,p.raw_sha256 "
        "FROM workflow_draft_revisions r "
        "JOIN workflow_receipts a ON a.project_id=r.project_id AND a.operation_id=r.operation_id "
        "JOIN workflow_proposals p ON p.project_id=r.project_id AND p.content_id=r.proposal_content_id "
        "WHERE r.project_id=? AND r.draft_id=? AND r.revision=?",
        (tx._project_id, draft_id, revision),
    ).fetchone()
    if row is None:
        raise _corrupt()
    try:
        (
            content_id,
            title,
            status,
            operation,
            action,
            version,
            actor_id,
            authority,
            recorded,
            raw_request,
            raw_result,
            snapshot,
            layer,
            path,
            raw_hash,
        ) = row
        if action not in _ACTIONS or type(version) is not int or version != 1:
            raise ValueError("action")
        _uuid(operation)
        _revision(revision, minimum=1)
        _title(title)
        if (
            type(content_id) is not str
            or len(content_id) != 64
            or any(c not in "0123456789abcdef" for c in content_id)
        ):
            raise ValueError("content identity")
        if datetime.fromisoformat(recorded).tzinfo is None:
            raise ValueError("timestamp")
        actor = Principal(actor_id, authority)
        ref = SourceRef(
            SnapshotRef(tx._project_id, snapshot, snapshot), layer, path, raw_hash
        )
        request = _request(
            actor, action, draft_id, revision - 1, title=title, content_id=content_id
        )
        result = _result(
            tx._project_id, operation, actor, recorded, request, ref, title, content_id
        )
        if (
            status != result["status"]
            or _bounded(request) != raw_request
            or _bounded(result) != raw_result
        ):
            raise ValueError("receipt binding")
        if tx.get_snapshot(snapshot).snapshot != ref.snapshot:
            raise ValueError("snapshot binding")
    except (CoreError, TypeError, ValueError, UnicodeError) as exc:
        raise _corrupt() from exc
    return request, result


def _find_operation(tx, operation_id):
    row = tx._connection.execute(
        "SELECT a.action,r.draft_id,r.revision FROM workflow_receipts a "
        "LEFT JOIN workflow_draft_revisions r ON r.project_id=a.project_id AND r.operation_id=a.operation_id "
        "WHERE a.project_id=? AND a.operation_id=?",
        (tx._project_id, operation_id),
    ).fetchone()
    if row is None:
        return None
    if row[0] not in _ACTIONS:
        raise CoreError(
            "OPERATION_CONFLICT", "Operation belongs to another workflow action"
        )
    if row[1] is None or _head(tx, row[1]) is None:
        raise _corrupt()
    return _read_revision(tx, row[1], row[2])


def _stored_proposal(tx, receipt):
    row = tx._connection.execute(
        "SELECT canonical_json,candidate_sha256,candidate_size_bytes FROM workflow_proposals "
        "WHERE project_id=? AND content_id=?",
        (tx._project_id, receipt["proposal_content_id"]),
    ).fetchone()
    if row is None:
        raise _corrupt()
    try:
        proposal = proposals._decode_proposal(row[0], _LIMITS)
        if (
            proposal.content_id != receipt["proposal_content_id"]
            or asdict(proposal.source_ref) != receipt["source_ref"]
            or proposals._canonical(proposals._document(proposal)) != row[0]
            or hashlib.sha256(proposal.replacement_bytes).hexdigest() != row[1]
            or type(row[2]) is not int
            or len(proposal.replacement_bytes) != row[2]
        ):
            raise ValueError("stored proposal")
    except (CoreError, TypeError, ValueError) as exc:
        raise _corrupt() from exc
    return row[0]


def _insert_proposal(tx, proposal, canonical_json):
    ref = proposal.source_ref
    if tx.get_snapshot(
        ref.snapshot.snapshot_id
    ).snapshot != ref.snapshot or ref.layer_id not in {
        layer.layer_id for layer in tx.get_snapshot_layers(ref.snapshot.snapshot_id)
    }:
        raise CoreError(
            "SOURCE_REF_MISMATCH", "Draft must refer to a published project layer"
        )
    old = tx._connection.execute(
        "SELECT canonical_json FROM workflow_proposals WHERE project_id=? AND content_id=?",
        (tx._project_id, proposal.content_id),
    ).fetchone()
    if old is not None:
        if old[0] != canonical_json:
            raise _corrupt()
        return
    tx._connection.execute(
        "INSERT INTO workflow_proposals VALUES (?,?,?,?,?,?,?,?,?)",
        (
            tx._project_id,
            proposal.content_id,
            ref.snapshot.snapshot_id,
            ref.layer_id,
            ref.relative_path,
            ref.raw_sha256,
            hashlib.sha256(proposal.replacement_bytes).hexdigest(),
            len(proposal.replacement_bytes),
            canonical_json,
        ),
    )


def _commit(tx, request, operation_id, proposal=None, canonical_json=None):
    _require(tx, write=True)
    found = _find_operation(tx, operation_id)
    if found is not None:
        if found[0] != request:
            raise CoreError(
                "OPERATION_CONFLICT", "Operation has different draft inputs or actor"
            )
        _stored_proposal(tx, found[1])
        return found[1]
    draft_id = request["draft_id"]
    head = _head(tx, draft_id)
    if (head or 0) != request["expected_revision"]:
        raise CoreError(
            "DRAFT_CONFLICT",
            "Draft changed; reload before saving",
            details={"current_revision": head or 0},
        )
    previous = None if head is None else _read_revision(tx, draft_id, head)[1]
    if previous is not None:
        _stored_proposal(tx, previous)
    action = request["action"]
    if action == "draft.saved":
        if previous is not None:
            if previous["status"] == "archived":
                raise CoreError(
                    "DRAFT_ARCHIVED", "Restore the archived draft before editing"
                )
            if asdict(proposal.source_ref) != previous["source_ref"]:
                raise CoreError(
                    "DRAFT_SOURCE_MISMATCH",
                    "Ordinary saves must retain the exact source reference",
                )
        title, content_id, ref = (
            request["title"],
            proposal.content_id,
            proposal.source_ref,
        )
    else:
        if previous is None:
            raise CoreError("DRAFT_NOT_FOUND", "Draft does not exist")
        required = "active" if action == "draft.archived" else "archived"
        if previous["status"] != required:
            raise CoreError(
                "DRAFT_STATUS_CONFLICT", "Draft is not in the required state"
            )
        title, content_id = previous["title"], previous["proposal_content_id"]
        source = previous["source_ref"]
        ref = SourceRef(
            SnapshotRef(**source["snapshot"]),
            source["layer_id"],
            source["relative_path"],
            source["raw_sha256"],
        )
    result = _result(
        tx._project_id,
        operation_id,
        tx._principal,
        datetime.now(timezone.utc).isoformat(),
        request,
        ref,
        title,
        content_id,
    )
    request_json, result_json = _bounded(request), _bounded(result)
    with tx._atomic_operation():
        if proposal is not None:
            _insert_proposal(tx, proposal, canonical_json)
        tx._connection.execute(
            "INSERT INTO workflow_receipts VALUES (?,?,?,?,?,?,?,?,?)",
            (
                tx._project_id,
                operation_id,
                action,
                1,
                tx._principal.id,
                tx._principal.authority,
                result["recorded_at"],
                request_json,
                result_json,
            ),
        )
        if head is None:
            tx._connection.execute(
                "INSERT INTO workflow_draft_heads VALUES (?,?,?)",
                (tx._project_id, draft_id, result["revision"]),
            )
        else:
            changed = tx._connection.execute(
                "UPDATE workflow_draft_heads SET current_revision=? WHERE project_id=? AND draft_id=? AND current_revision=?",
                (result["revision"], tx._project_id, draft_id, head),
            ).rowcount
            if changed != 1:
                raise CoreError("DRAFT_CONFLICT", "Concurrent draft revision changed")
        tx._connection.execute(
            "INSERT INTO workflow_draft_revisions VALUES (?,?,?,?,?,?,?)",
            (
                tx._project_id,
                draft_id,
                result["revision"],
                content_id,
                title,
                result["status"],
                operation_id,
            ),
        )
        _stored_proposal(tx, _read_revision(tx, draft_id, result["revision"])[1])
    return result


def _change(ctx, request, operation_id, proposal=None, canonical_json=None):
    _uuid(operation_id)
    _boundary("before_state_transaction", state=ctx.state)
    try:
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            result = _commit(tx, request, operation_id, proposal, canonical_json)
            _boundary("before_commit", state=ctx.state)
        _boundary("after_commit", state=ctx.state)
        return result
    except (Exception, KeyboardInterrupt) as exc:
        if isinstance(exc, CoreError) and exc.code not in {
            "STATE_BUSY",
            "STATE_UNAVAILABLE",
        }:
            raise
        try:
            with ctx.state.transaction(ctx.principal) as tx:
                _require(tx, write=True)
                found = _find_operation(tx, operation_id)
                if found is not None:
                    if found[0] != request:
                        raise CoreError(
                            "OPERATION_CONFLICT",
                            "Operation has different draft inputs or actor",
                        )
                    _stored_proposal(tx, found[1])
                    return found[1]
        except Exception as read_error:
            if isinstance(read_error, CoreError) and read_error.code in {
                "PROJECT_FORBIDDEN",
                "STATE_CORRUPT",
                "OPERATION_CONFLICT",
            }:
                raise
            raise CoreError(
                "DRAFT_OUTCOME_UNKNOWN",
                "Retain the original operation ID to reconcile this save",
                details={"operation_id": operation_id},
            ) from read_error
        if isinstance(exc, KeyboardInterrupt):
            raise CoreError(
                "OPERATION_INTERRUPTED",
                "No draft commit receipt confirmed",
                details={"operation_id": operation_id},
            ) from exc
        raise


def save_draft(ctx, raw_proposal, *, draft_id, title, expected_revision, operation_id):
    with ctx.state.transaction(ctx.principal) as tx:
        _require(tx, write=True)
    _uuid(operation_id)
    _uuid(draft_id)
    _title(title)
    _revision(expected_revision)
    # Close retained source handles before opening the write unit of work.
    proposal = proposals.parse_proposal(ctx, raw_proposal, limits=_LIMITS)
    canonical_json = proposals._canonical(proposals._document(proposal))
    request = _request(
        ctx.principal,
        "draft.saved",
        draft_id,
        expected_revision,
        title=title,
        content_id=proposal.content_id,
    )
    return _change(ctx, request, operation_id, proposal, canonical_json)


def _status_change(ctx, draft_id, action, expected_revision, operation_id):
    with ctx.state.transaction(ctx.principal) as tx:
        _require(tx, write=True)
    request = _request(ctx.principal, action, draft_id, expected_revision)
    return _change(ctx, request, operation_id)


def archive_draft(ctx, draft_id, *, expected_revision, operation_id):
    return _status_change(
        ctx, draft_id, "draft.archived", expected_revision, operation_id
    )


def restore_draft(ctx, draft_id, *, expected_revision, operation_id):
    return _status_change(
        ctx, draft_id, "draft.restored", expected_revision, operation_id
    )


def get_draft(ctx, draft_id, *, revision=None):
    with ctx.state.transaction(ctx.principal) as tx:
        _require(tx)
        _uuid(draft_id)
        head = _head(tx, draft_id)
        if head is None:
            raise CoreError("DRAFT_NOT_FOUND", "Draft does not exist")
        revision = head if revision is None else _revision(revision, minimum=1)
        if revision > head:
            raise CoreError("DRAFT_NOT_FOUND", "Draft version does not exist")
        receipt = _read_revision(tx, draft_id, revision)[1]
        return {"receipt": receipt, "canonical_json": _stored_proposal(tx, receipt)}


def get_draft_receipt(ctx, operation_id):
    with ctx.state.transaction(ctx.principal) as tx:
        _require(tx)
        found = _find_operation(tx, _uuid(operation_id))
        if found is None:
            return None
        _stored_proposal(tx, found[1])
        return found[1]


def _limit(value):
    if type(value) is not int or not 1 <= value <= 25:
        raise _invalid()
    return value


def list_drafts(ctx, *, limit=20, after_draft_id=None, status="active"):
    with ctx.state.transaction(ctx.principal) as tx:
        _require(tx)
        _limit(limit)
        after = "" if after_draft_id is None else _uuid(after_draft_id)
        if status not in ("active", "archived"):
            raise _invalid()
        rows = tx._connection.execute(
            "SELECT h.draft_id,h.current_revision FROM workflow_draft_heads h "
            "LEFT JOIN workflow_draft_revisions r ON r.project_id=h.project_id AND r.draft_id=h.draft_id AND r.revision=h.current_revision "
            "WHERE h.project_id=? AND h.draft_id>? AND (r.status=? OR r.status IS NULL) ORDER BY h.draft_id LIMIT ?",
            (tx._project_id, after, status, limit + 1),
        ).fetchall()
        items = []
        for draft_id, revision in rows[:limit]:
            if _head(tx, draft_id) != revision:
                raise _corrupt()
            items.append(_read_revision(tx, draft_id, revision)[1])
        return {
            "items": items,
            "next_after": rows[limit - 1][0] if len(rows) > limit else None,
        }


def draft_history(ctx, draft_id, *, limit=20, before_revision=None):
    with ctx.state.transaction(ctx.principal) as tx:
        _require(tx)
        _uuid(draft_id)
        _limit(limit)
        head = _head(tx, draft_id)
        if head is None:
            raise CoreError("DRAFT_NOT_FOUND", "Draft does not exist")
        before = (
            head + 1
            if before_revision is None
            else _revision(before_revision, minimum=1)
        )
        rows = tx._connection.execute(
            "SELECT revision FROM workflow_draft_revisions WHERE project_id=? AND draft_id=? AND revision<? ORDER BY revision DESC LIMIT ?",
            (tx._project_id, draft_id, before, limit + 1),
        ).fetchall()
        top = min(head, before - 1)
        if [row[0] for row in rows] != list(range(top, max(0, top - limit - 1), -1)):
            raise _corrupt()
        items = [_read_revision(tx, draft_id, row[0])[1] for row in rows[:limit]]
        return {
            "items": items,
            "next_before": rows[limit - 1][0] if len(rows) > limit else None,
        }
