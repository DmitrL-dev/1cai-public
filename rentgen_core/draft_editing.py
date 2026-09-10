"""Edit and inspect complete saved candidates through bounded exact operations."""
import base64
from dataclasses import asdict
import hashlib

from . import drafts, proposals
from .errors import CoreError

MAX_EDIT_BYTES = 8192
MAX_EDITS = 16
MAX_CHUNK_BYTES = 65536


def validate_edits(edits):
    if type(edits) is not list or not 1 <= len(edits) <= MAX_EDITS:
        raise CoreError(
            "DRAFT_EDIT_INVALID", "Expected 1 to 16 exact text replacements"
        )
    for edit in edits:
        if type(edit) is not dict or set(edit) != {"old_text", "new_text"}:
            raise CoreError("DRAFT_EDIT_INVALID", "Expected old_text and new_text")
        for value in edit.values():
            try:
                valid = (
                    type(value) is str and len(value.encode("utf-8")) <= MAX_EDIT_BYTES
                )
            except UnicodeError:
                valid = False
            if not valid:
                raise CoreError(
                    "DRAFT_EDIT_INVALID",
                    "Replacement text is not a bounded UTF-8 string",
                )


def replace_text(raw, edits):
    """Locate every unique match in the original value; never use fuzzy matching."""
    validate_edits(edits)
    text, bom, _ = proposals._text(raw)
    ranges = []
    for edit in edits:
        old = edit["old_text"]
        if not old and (text or len(edits) != 1):
            raise CoreError(
                "DRAFT_EDIT_INVALID",
                "An empty match is allowed only as one insertion into an empty candidate",
            )
        start = text.find(old)
        if start == -1:
            raise CoreError(
                "DRAFT_EDIT_MISMATCH",
                "Exact text was not found in the selected revision",
            )
        if text.find(old, start + 1) != -1:
            raise CoreError(
                "DRAFT_EDIT_AMBIGUOUS",
                "Exact text occurs more than once; include more context",
            )
        ranges.append((start, start + len(old), edit["new_text"]))
    ranges.sort()
    pieces, previous = [], 0
    for start, end, replacement in ranges:
        if start < previous:
            raise CoreError("DRAFT_EDIT_OVERLAP", "Selected replacement spans overlap")
        pieces.extend((text[previous:start], replacement))
        previous = end
    pieces.append(text[previous:])
    result = (b"\xef\xbb\xbf" if bom else b"") + "".join(pieces).encode("utf-8")
    if len(result) > drafts._LIMITS.max_replacement_bytes:
        raise CoreError("PROPOSAL_LIMIT_EXCEEDED", "Complete candidate exceeds 1 MiB")
    return result


def _write_access(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        drafts._require(tx, write=True)


def _stored(ctx, draft_id, revision):
    drafts._revision(revision, minimum=1)
    value = drafts.get_draft(ctx, draft_id, revision=revision)
    proposal = proposals._decode_proposal(value["canonical_json"], drafts._LIMITS)
    return value, proposal


def _save(
    ctx, source_ref, candidate, *, draft_id, title, expected_revision, operation_id
):
    proposal = proposals.create_proposal(
        ctx, source_ref, candidate, limits=drafts._LIMITS
    )
    return drafts.save_draft(
        ctx,
        proposals._canonical(proposals._document(proposal)),
        draft_id=draft_id,
        title=title,
        expected_revision=expected_revision,
        operation_id=operation_id,
    )


def start_draft(ctx, source_ref, *, draft_id, title, operation_id):
    _write_access(ctx)
    drafts._uuid(draft_id)
    drafts._uuid(operation_id)
    drafts._title(title)
    original = proposals._original(ctx, source_ref, drafts._LIMITS)
    return _save(
        ctx,
        source_ref,
        original,
        draft_id=draft_id,
        title=title,
        expected_revision=0,
        operation_id=operation_id,
    )


def edit_draft(ctx, draft_id, *, expected_revision, operation_id, edits):
    _write_access(ctx)
    drafts._uuid(operation_id)
    validate_edits(edits)
    value, proposal = _stored(ctx, draft_id, expected_revision)
    proposals._ref(ctx, proposal.source_ref)
    candidate = replace_text(proposal.replacement_bytes, edits)
    return _save(
        ctx,
        proposal.source_ref,
        candidate,
        draft_id=draft_id,
        title=value["receipt"]["title"],
        expected_revision=expected_revision,
        operation_id=operation_id,
    )


def read_draft(ctx, draft_id, *, revision, offset=0, limit=8192, encoding="base64"):
    if (
        type(offset) is not int
        or not 0 <= offset <= 1048576
        or type(limit) is not int
        or not 1 <= limit <= MAX_CHUNK_BYTES
        or type(encoding) is not str
        or encoding not in {"base64", "utf-8"}
    ):
        raise CoreError(
            "DRAFT_READ_INVALID", "Expected bounded integer byte offset and limit"
        )
    value, proposal = _stored(ctx, draft_id, revision)
    raw = proposal.replacement_bytes
    if offset > len(raw):
        raise CoreError("DRAFT_READ_INVALID", "Offset is beyond the selected candidate")
    end = min(offset + limit, len(raw))
    if encoding == "utf-8":
        if offset < len(raw) and raw[offset] & 0xC0 == 0x80:
            raise CoreError(
                "DRAFT_READ_INVALID", "Offset must start at a UTF-8 character boundary"
            )
        while end < len(raw) and raw[end] & 0xC0 == 0x80:
            end -= 1
        if end == offset and offset < len(raw):
            raise CoreError(
                "DRAFT_READ_INVALID", "Limit must fit the next UTF-8 character"
            )
    part = raw[offset:end]
    if encoding == "utf-8":
        try:
            content = {"encoding": "utf-8", "text": part.decode("utf-8")}
        except UnicodeDecodeError as exc:
            raise CoreError(
                "DRAFT_READ_INVALID", "Stored candidate is not UTF-8"
            ) from exc
    else:
        content = {"base64": base64.b64encode(part).decode("ascii")}
    return {
        "receipt": value["receipt"],
        "source_ref": asdict(proposal.source_ref),
        "candidate_size_bytes": len(raw),
        "candidate_sha256": hashlib.sha256(raw).hexdigest(),
        "offset": offset,
        "size_bytes": len(part),
        **content,
        "chunk_sha256": hashlib.sha256(part).hexdigest(),
        "next_offset": end if end < len(raw) else None,
    }


def check_draft(ctx, draft_id, *, revision, adapter):
    from .diagnostics import diagnose_proposal_json

    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"project:read", "source:edit", "analysis:run"})
    value, _ = _stored(ctx, draft_id, revision)
    diagnostic = diagnose_proposal_json(
        ctx, value["canonical_json"], adapter, limits=drafts._LIMITS
    )
    return {
        "receipt": value["receipt"],
        "diagnostic": asdict(diagnostic),
        "tests": {"status": "not_run"},
        "apply": {"status": "unavailable"},
    }
