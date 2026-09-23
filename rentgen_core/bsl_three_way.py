"""Bounded byte-preserving text merge; no BSL parser or platform side effects."""

from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha256

from .errors import CoreError


_MAX_BYTES = 16 * 1024 * 1024
_MAX_LINES = 200_000
_MAX_LINE_BYTES = 1024 * 1024
_MAX_DIFF_CELLS = 4_000_000
_MAX_EVIDENCE = 256
_BOM = b"\xef\xbb\xbf"


def _error(code, reason, **details):
    return CoreError(
        "BSL_THREE_WAY_" + code,
        "BSL three-way materialization rejected",
        details={"reason": reason, **details},
    )


@dataclass(frozen=True)
class _Document:
    lines: tuple[bytes, ...]
    bom: bytes
    newline: str


@dataclass(frozen=True)
class _Edit:
    start: int
    end: int
    replacement: tuple[bytes, ...]
    source: str
    branch_start: int
    branch_end: int

    def evidence(self):
        return {
            "source": self.source,
            "kind": (
                "insert"
                if self.start == self.end
                else "replace"
                if self.replacement
                else "delete"
            ),
            "base_range": [self.start, self.end],
            self.source + "_range": [self.branch_start, self.branch_end],
        }


def _document(raw, max_lines, *, candidate=False):
    prefix = "candidate_" if candidate else ""
    bom = _BOM if raw.startswith(_BOM) else b""
    body = raw[len(bom) :]
    line_count = body.count(b"\n") + int(bool(body) and not body.endswith(b"\n"))
    if line_count > max_lines:
        raise _error("LIMIT", prefix + "line_limit", line_count=line_count)
    if b"\x00" in body:
        raise _error("INVALID", "nul_byte")
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        raise _error("INVALID", "invalid_utf8") from None
    pieces = body.split(b"\n")
    lines = tuple(line + b"\n" for line in pieces[:-1])
    if pieces[-1]:
        lines += (pieces[-1],)
    if any(len(line) > _MAX_LINE_BYTES for line in lines):
        raise _error("LIMIT", prefix + "line_byte_limit")
    crlf = body.count(b"\r\n")
    lf = body.count(b"\n")
    if body.count(b"\r") != crlf:
        newline = "unsupported"
    elif crlf and crlf != lf:
        newline = "mixed"
    elif crlf:
        newline = "crlf"
    elif lf:
        newline = "lf"
    else:
        newline = "none"
    return _Document(lines, bom, newline)


def _edits(base, branch, source):
    # Trim equal margins before bounding the complete remaining matching area.
    # Disabling autojunk prevents its popularity heuristic hiding BSL lines.
    start = 0
    while start < min(len(base), len(branch)) and base[start] == branch[start]:
        start += 1
    base_end, branch_end = len(base), len(branch)
    while (
        base_end > start
        and branch_end > start
        and base[base_end - 1] == branch[branch_end - 1]
    ):
        base_end -= 1
        branch_end -= 1
    if (base_end - start) * (branch_end - start) > _MAX_DIFF_CELLS:
        raise _error(
            "LIMIT",
            "diff_work_limit",
            hunks=[
                {
                    "base_range": [start, base_end],
                    source + "_range": [start, branch_end],
                }
            ],
        )
    matcher = SequenceMatcher(
        None, base[start:base_end], branch[start:branch_end], autojunk=False
    )
    return [
        _Edit(
            start + i,
            start + j,
            branch[start + k : start + end],
            source,
            start + k,
            start + end,
        )
        for tag, i, j, k, end in matcher.get_opcodes()
        if tag != "equal"
    ]


def _combine(current, upstream):
    merged = []
    i = j = 0
    while i < len(current) and j < len(upstream):
        ours, theirs = current[i], upstream[j]
        if (
            ours.start == theirs.start
            and ours.end == theirs.end
            and ours.replacement == theirs.replacement
            and ours.start != ours.end
        ):
            row = ours.evidence()
            row.update(
                source="both",
                upstream_range=[theirs.branch_start, theirs.branch_end],
            )
            merged.append((ours, row))
            i += 1
            j += 1
        elif ours.end < theirs.start:
            merged.append((ours, ours.evidence()))
            i += 1
        elif theirs.end < ours.start:
            merged.append((theirs, theirs.evidence()))
            j += 1
        else:
            same_anchor = ours.start == ours.end == theirs.start == theirs.end
            raise _error(
                "CONFLICT",
                "same_anchor_insertions" if same_anchor else "overlapping_edits",
                hunks=[ours.evidence(), theirs.evidence()],
                conflict_count=1,
            )
    merged.extend((edit, edit.evidence()) for edit in current[i:])
    merged.extend((edit, edit.evidence()) for edit in upstream[j:])
    return merged


def _result(inputs, documents, candidate, candidate_document, rows, mode):
    return {
        "schema": 1,
        "scope": "bsl-text-v1",
        "status": "ready",
        "mode": mode,
        **{label + "_digest": sha256(raw).hexdigest() for label, raw in inputs.items()},
        "candidate_digest": sha256(candidate).hexdigest(),
        "candidate": candidate,
        "merged_hunks": rows[:_MAX_EVIDENCE],
        "counts": {
            **{
                label + "_lines": len(document.lines)
                for label, document in documents.items()
            },
            "candidate_lines": len(candidate_document.lines),
            "merged_hunks": len(rows),
            "merged_hunks_omitted": max(0, len(rows) - _MAX_EVIDENCE),
        },
    }


def materialize_bsl_three_way(
    base: bytes,
    current: bytes,
    upstream: bytes,
    *,
    max_bytes: int = _MAX_BYTES,
    max_lines: int = _MAX_LINES,
) -> dict:
    """Return complete immutable candidate bytes or raise a payload-free error.

    Line intervals in evidence are zero-based and half-open; insertions use an
    empty base interval. Limits may be lowered, but not raised above defaults.
    Exact selections preserve complete branch bytes. Composite merges require
    matching BOM/newline styles and reject overlapping or touching branch edits.
    Owner identity, module path binding and native BSL validation belong to the
    caller; this primitive never reads/writes files or invokes 1C/EDT.
    """
    if (
        type(max_bytes) is not int
        or not 1 <= max_bytes <= _MAX_BYTES
        or type(max_lines) is not int
        or not 1 <= max_lines <= _MAX_LINES
    ):
        raise _error("LIMIT", "invalid_limits")
    inputs = {"base": base, "current": current, "upstream": upstream}
    # Bound every input before decoding any of them, including exact selections.
    for raw in inputs.values():
        if type(raw) is not bytes:
            raise _error("INVALID", "bytes_required")
        if len(raw) > max_bytes:
            raise _error("LIMIT", "byte_limit", byte_count=len(raw))
    documents = {label: _document(raw, max_lines) for label, raw in inputs.items()}
    selection = None
    if current == upstream:
        selection = "current"
        mode = "unchanged" if current == base else "same_change"
    elif current == base:
        selection, mode = "upstream", "take_upstream"
    elif upstream == base:
        selection, mode = "current", "keep_current"
    if selection is not None:
        rows = []
        if mode != "unchanged":
            rows = [
                {
                    "source": "both" if mode == "same_change" else selection,
                    "kind": "exact_selection",
                    **{
                        label + "_range": [0, len(document.lines)]
                        for label, document in documents.items()
                    },
                }
            ]
        return _result(
            inputs, documents, inputs[selection], documents[selection], rows, mode
        )

    styles = {document.newline for document in documents.values()}
    if "unsupported" in styles:
        raise _error("INVALID", "unsupported_newlines")
    if "mixed" in styles:
        raise _error("INVALID", "mixed_newlines")
    if len(styles - {"none"}) > 1:
        raise _error("INVALID", "newline_style_changed")
    if len({document.bom for document in documents.values()}) > 1:
        raise _error("INVALID", "bom_changed")

    base_document = documents["base"]
    merged = _combine(
        _edits(base_document.lines, documents["current"].lines, "current"),
        _edits(base_document.lines, documents["upstream"].lines, "upstream"),
    )
    parts = []
    cursor = 0
    for edit, _ in merged:
        parts.extend(base_document.lines[cursor : edit.start])
        parts.extend(edit.replacement)
        cursor = edit.end
    parts.extend(base_document.lines[cursor:])
    candidate_size = len(base_document.bom) + sum(map(len, parts))
    if candidate_size > max_bytes:
        raise _error("LIMIT", "candidate_byte_limit", byte_count=candidate_size)
    candidate = base_document.bom + b"".join(parts)
    candidate_document = _document(candidate, max_lines, candidate=True)
    return _result(
        inputs,
        documents,
        candidate,
        candidate_document,
        [row for _, row in merged],
        "merged",
    )
