"""Ephemeral single-source proposals; no writes, execution, approval or receipt.

Transport code must use render_proposal().canonical_json for the public object,
not a generic dataclass serializer (Proposal contains exact replacement bytes).
Constructing/deserializing a DTO conveys no authority: every use case validates
the retained original and reauthorizes before releasing success or failure.
CLI/MCP input-file authorization must precede reading their payload, separately.
"""

import base64
import binascii
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
import difflib
import hashlib
import json

from .context import SnapshotRef
from .errors import CoreError
from .resolver import require_snapshot
from .sources import SnapshotReadLimits, SourceRef

_PERMISSIONS = frozenset({"project:read", "source:edit"})
_DOMAIN = "rentgen.source-proposal"
_BOM = b"\xef\xbb\xbf"


def _invalid():
    return CoreError("PROPOSAL_INVALID", "Invalid source proposal")


def _limit():
    return CoreError("PROPOSAL_LIMIT_EXCEEDED", "Proposal exceeds the selected limits")


def _encoding():
    return CoreError(
        "PROPOSAL_ENCODING_UNSUPPORTED", "Proposal byte policy is unsupported"
    )


@dataclass(frozen=True)
class ProposalLimits:
    max_original_bytes: int
    max_replacement_bytes: int
    max_canonical_bytes: int
    max_diff_bytes: int

    def __post_init__(self):
        values = (
            self.max_original_bytes,
            self.max_replacement_bytes,
            self.max_canonical_bytes,
            self.max_diff_bytes,
        )
        if any(
            type(value) is not int or not 1 <= value <= maximum
            for value, maximum in zip(
                values, (1024**2, 1024**2, 1536 * 1024, 256 * 1024)
            )
        ):
            raise CoreError(
                "PROPOSAL_LIMIT_INVALID",
                "Explicit bounded integer proposal limits required",
            )


@dataclass(frozen=True)
class BytePolicy:
    encoding: str
    bom: bool
    newline: str
    original_final_newline: bool
    replacement_final_newline: bool


@dataclass(frozen=True)
class Proposal:
    source_ref: SourceRef
    original_size_bytes: int
    replacement_bytes: bytes
    policy: BytePolicy
    content_id: str


@dataclass(frozen=True)
class ProposalDiff:
    status: str
    text: str | None
    reason: str | None


@dataclass(frozen=True)
class ProposalPresentation:
    canonical_json: bytes
    diff: ProposalDiff


def _authorize(ctx):
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Project context is required")
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(_PERMISSIONS)


@contextmanager
def _authorized(ctx):
    _authorize(ctx)
    try:
        yield
    finally:
        try:
            _authorize(ctx)
        except BaseException as exc:
            # Never reveal the earlier source/parser exception after revocation.
            raise exc from None


@contextmanager
def _additional_authorized(authorize):
    if authorize is not None:
        authorize()
    try:
        yield
    finally:
        if authorize is not None:
            try:
                authorize()
            except BaseException as exc:
                raise exc from None


def _limits(value):
    if type(value) is not ProposalLimits:
        raise CoreError("PROPOSAL_LIMIT_INVALID", "Typed proposal limits required")
    value.__post_init__()
    return value


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _unsigned(proposal):
    return {
        "domain": _DOMAIN,
        "schema_version": 1,
        "source_ref": asdict(proposal.source_ref),
        "original": {
            "size_bytes": proposal.original_size_bytes,
            "raw_sha256": proposal.source_ref.raw_sha256,
        },
        "replacement": {
            "size_bytes": len(proposal.replacement_bytes),
            "raw_sha256": _hash(proposal.replacement_bytes),
            "base64": base64.b64encode(proposal.replacement_bytes).decode("ascii"),
        },
        "policy": asdict(proposal.policy),
    }


def _document(proposal):
    return {**_unsigned(proposal), "content_id": proposal.content_id}


def _ref(ctx, ref):
    snapshot = require_snapshot(ctx)
    if type(ref) is not SourceRef or ref.snapshot != snapshot:
        raise CoreError(
            "SOURCE_REF_MISMATCH", "Source reference belongs to another snapshot"
        )
    ref.__post_init__()
    if not ref.relative_path.lower().endswith((".bsl", ".os")):
        raise CoreError(
            "PROPOSAL_SOURCE_UNSUPPORTED",
            "Only existing BSL or OneScript files are supported",
        )
    if ctx.sources is None or ctx.sources.snapshot != snapshot:
        raise CoreError("SOURCE_REF_MISMATCH", "Retained source capability is required")


def _original(ctx, ref, limits, *, authorize=None):
    _ref(ctx, ref)
    _authorize(ctx)
    if authorize is not None:
        authorize()
    # Full snapshot validation is bounded independently from the one-file buffer.
    with ctx.sources.read_session(limits=SnapshotReadLimits()) as session:
        entry = next(
            (
                item
                for item in session.entries()
                if item.ref.layer_id == ref.layer_id
                and item.ref.relative_path == ref.relative_path
            ),
            None,
        )
        if entry is None:
            raise CoreError("SOURCE_NOT_FOUND", "Source is absent from this snapshot")
        if entry.ref != ref:
            raise CoreError(
                "SOURCE_REF_MISMATCH", "Source reference hash does not match"
            )
        if entry.size_bytes > limits.max_original_bytes:
            raise _limit()
        _authorize(ctx)
        if authorize is not None:
            authorize()
        raw = session.read_source(ref)
        if (
            type(raw) is not bytes
            or len(raw) != entry.size_bytes
            or _hash(raw) != ref.raw_sha256
        ):
            raise CoreError("SNAPSHOT_CORRUPT", "Retained source digest mismatch")
    if authorize is not None:
        authorize()
    return raw


def _text(raw):
    if type(raw) is not bytes:
        raise _invalid()
    bom = raw.startswith(_BOM)
    try:
        text = (raw[len(_BOM) :] if bom else raw).decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _encoding() from exc
    remaining = text.replace("\r\n", "")
    if "\r" in remaining or ("\r\n" in text and "\n" in remaining):
        raise _encoding()
    newline = "crlf" if "\r\n" in text else "lf" if "\n" in text else None
    return text, bom, newline


def _policy(original, replacement):
    before, before_bom, before_style = _text(original)
    after, after_bom, after_style = _text(replacement)
    style = before_style or "lf"
    if before_bom != after_bom or (after_style is not None and after_style != style):
        raise _encoding()
    return BytePolicy(
        "utf-8", before_bom, style, before.endswith("\n"), after.endswith("\n")
    )


def _build(ctx, ref, replacement_bytes, limits, *, authorize=None):
    _ref(ctx, ref)
    if type(replacement_bytes) is not bytes:
        raise _invalid()
    if len(replacement_bytes) > limits.max_replacement_bytes:
        raise _limit()
    original = _original(ctx, ref, limits, authorize=authorize)
    proposal = Proposal(
        ref, len(original), replacement_bytes, _policy(original, replacement_bytes), ""
    )
    proposal = replace(proposal, content_id=_hash(_canonical(_unsigned(proposal))))
    if len(_canonical(_document(proposal))) > limits.max_canonical_bytes:
        raise _limit()
    return proposal, original


def validate_proposal(ctx, proposal, *, limits, authorize=None):
    """Trusted additional permission gate; one retained read and no diff work.

    Only immutable validated proposal bytes leave this helper. The original
    buffer and every retained read handle are released before the caller runs
    a diagnostic process. Existing proposal public permission policy is intact.
    """
    with _authorized(ctx), _additional_authorized(authorize):
        limits = _limits(limits)
        if type(proposal) is not Proposal or type(proposal.policy) is not BytePolicy:
            raise _invalid()
        validated, _ = _build(
            ctx,
            proposal.source_ref,
            proposal.replacement_bytes,
            limits,
            authorize=authorize,
        )
        if proposal != validated or _canonical(_document(proposal)) != _canonical(
            _document(validated)
        ):
            raise _invalid()
        return validated


def create_proposal(ctx, source_ref, replacement_bytes, *, limits):
    """Validate retained bytes and create an ephemeral immutable candidate value."""
    with _authorized(ctx):
        proposal, _ = _build(ctx, source_ref, replacement_bytes, _limits(limits))
        return proposal


def _fields(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise _invalid()
    return value


def _strict_object(items):
    value = {}
    for key, item in items:
        if key in value:
            raise _invalid()
        value[key] = item
    return value


def _json(raw, limits):
    if type(raw) is not bytes:
        raise _invalid()
    if len(raw) > limits.max_canonical_bytes:
        raise _limit()
    # Bound nesting/container growth before json allocates caller-selected trees.
    depth = separators = 0
    quoted = escaped = False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (123, 91):
            depth += 1
            if depth > 8:
                raise _invalid()
        elif char in (125, 93):
            depth -= 1
        elif char in (44, 58):
            separators += 1
            if separators > 128:
                raise _invalid()
    try:
        return json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_strict_object,
            parse_constant=lambda value: (_ for _ in ()).throw(_invalid()),
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise _invalid() from exc


def _decode_proposal(raw, limits):
    """Decode a self-consistent value; this is NOT retained-source validation."""
    value = _fields(
        _json(raw, limits),
        (
            "domain",
            "schema_version",
            "source_ref",
            "original",
            "replacement",
            "policy",
            "content_id",
        ),
    )
    if (
        value["domain"] != _DOMAIN
        or type(value["schema_version"]) is not int
        or value["schema_version"] != 1
    ):
        raise _invalid()
    source = _fields(
        value["source_ref"], ("snapshot", "layer_id", "relative_path", "raw_sha256")
    )
    snapshot = _fields(
        source["snapshot"], ("project_id", "snapshot_id", "manifest_hash")
    )
    original = _fields(value["original"], ("size_bytes", "raw_sha256"))
    replacement = _fields(value["replacement"], ("size_bytes", "raw_sha256", "base64"))
    policy = _fields(
        value["policy"],
        (
            "encoding",
            "bom",
            "newline",
            "original_final_newline",
            "replacement_final_newline",
        ),
    )
    if any(
        type(item["size_bytes"]) is not int or item["size_bytes"] < 0
        for item in (original, replacement)
    ):
        raise _invalid()
    if any(
        type(policy[key]) is not bool
        for key in ("bom", "original_final_newline", "replacement_final_newline")
    ):
        raise _invalid()
    if (
        original["size_bytes"] > limits.max_original_bytes
        or replacement["size_bytes"] > limits.max_replacement_bytes
    ):
        raise _limit()
    encoded = replacement["base64"]
    if type(encoded) is not str:
        raise _invalid()
    if len(encoded) > 4 * ((limits.max_replacement_bytes + 2) // 3):
        raise _limit()
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise _invalid() from exc
    if base64.b64encode(decoded).decode("ascii") != encoded:
        raise _invalid()
    try:
        ref = SourceRef(
            SnapshotRef(**snapshot),
            source["layer_id"],
            source["relative_path"],
            source["raw_sha256"],
        )
    except (TypeError, ValueError) as exc:
        raise _invalid() from exc
    text, bom, newline = _text(decoded)
    if (
        policy["encoding"] != "utf-8"
        or policy["newline"] not in ("lf", "crlf")
        or policy["bom"] != bom
        or (newline is not None and policy["newline"] != newline)
        or policy["replacement_final_newline"] != text.endswith("\n")
        or not ref.relative_path.lower().endswith((".bsl", ".os"))
    ):
        raise _invalid()
    proposal = Proposal(ref, original["size_bytes"], decoded, BytePolicy(**policy), "")
    proposal = replace(proposal, content_id=_hash(_canonical(_unsigned(proposal))))
    if _canonical(value) != _canonical(_document(proposal)):
        raise _invalid()
    return proposal


def _parse(ctx, raw, limits, *, authorize=None):
    decoded = _decode_proposal(raw, limits)
    proposal, original_bytes = _build(
        ctx, decoded.source_ref, decoded.replacement_bytes, limits, authorize=authorize
    )
    if _canonical(_document(decoded)) != _canonical(_document(proposal)):
        raise _invalid()
    return proposal, original_bytes


def parse_proposal(ctx, raw_json, *, limits, authorize=None):
    """Parse a bounded JSON object representation, then revalidate retained input.

    Whitespace/key order may differ for MCP object round trips. Unknown/duplicate
    fields, ambiguous numbers and noncanonical base64 are always rejected.
    """
    with _authorized(ctx), _additional_authorized(authorize):
        return _parse(ctx, raw_json, _limits(limits), authorize=authorize)[0]


def _omitted(reason, limits):
    result = ProposalDiff("omitted_limit", None, reason)
    if len(_canonical(asdict(result))) > limits.max_diff_bytes:
        raise _limit()
    return result


def _diff(proposal, original, limits):
    before, _, _ = _text(original)
    after, _, _ = _text(proposal.replacement_bytes)
    if len(original) > 65536 or len(proposal.replacement_bytes) > 65536:
        return _omitted("input_bytes", limits)

    def lines(text):
        parts = text.split("\n")
        return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])

    before_lines, after_lines = lines(before), lines(after)
    if (
        max(len(before_lines), len(after_lines)) > 2048
        or len(before_lines) * len(after_lines) > 250000
    ):
        return _omitted("line_work", limits)
    locator = proposal.source_ref.layer_id + "/" + proposal.source_ref.relative_path
    pieces = []
    for line in difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile="original/" + locator,
        tofile="candidate/" + locator,
        lineterm="\n",
    ):
        if not line.endswith("\n"):
            line += "\n\\ No newline at end of file\n"
        pieces.append(line)
    result = ProposalDiff("complete", "".join(pieces), None)
    if len(_canonical(asdict(result))) > limits.max_diff_bytes:
        return _omitted("display_bytes", limits)
    return result


def render_proposal(ctx, proposal, *, limits):
    """Return the explicit canonical projection and a complete or omitted diff."""
    with _authorized(ctx):
        limits = _limits(limits)
        if type(proposal) is not Proposal or type(proposal.policy) is not BytePolicy:
            raise _invalid()
        validated, original = _build(
            ctx, proposal.source_ref, proposal.replacement_bytes, limits
        )
        # Compare canonical bytes too: bool and int are equal in ordinary Python DTOs.
        if proposal != validated or _canonical(_document(proposal)) != _canonical(
            _document(validated)
        ):
            raise _invalid()
        return ProposalPresentation(
            _canonical(_document(validated)), _diff(validated, original, limits)
        )


def create_proposal_presentation(ctx, source_ref, replacement_bytes, *, limits):
    """Create and render with one retained read session and final reauthorization."""
    with _authorized(ctx):
        limits = _limits(limits)
        proposal, original = _build(ctx, source_ref, replacement_bytes, limits)
        return ProposalPresentation(
            _canonical(_document(proposal)), _diff(proposal, original, limits)
        )


def parse_proposal_presentation(ctx, raw_json, *, limits):
    """Revalidate transport JSON and render with one retained read session."""
    with _authorized(ctx):
        limits = _limits(limits)
        proposal, original = _parse(ctx, raw_json, limits)
        return ProposalPresentation(
            _canonical(_document(proposal)), _diff(proposal, original, limits)
        )
