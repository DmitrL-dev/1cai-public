"""Bounded exact line alignment of two caller-verified byte strings.

This module owns no file, ZIP, path, hash, permission or selection authority.
The caller must bind both byte strings to the selected entries and revalidate
before disclosure. ``None`` means an absent file, never an empty file.

A complete result is an exact text-line alignment, not a semantic comparison,
rename inference, patch, or claim of merge safety. BOM and newline evidence is
explicit. Every unavailable result has no rows; the original source viewers
remain the caller's fallback. No incomplete alignment is published.
"""
from array import array

SOURCE_BYTES = 256 * 1024
LINES_PER_SIDE = 4096
OUTPUT_ROWS = 2 * LINES_PER_SIDE
DP_CELLS = 1_000_000
CHECK_INTERVAL = 256
_EOL = {"\n": "LF", "\r": "CR", "\r\n": "CRLF", "": "none"}


def _side(raw, check):
    if raw is not None and type(raw) is not bytes:
        raise TypeError("Line diff sources must be bytes or None")
    evidence = {"present": raw is not None, "size_bytes": len(raw) if raw is not None else None,
                "bom": None, "line_count": None, "newlines": None, "final_newline": None}
    if raw is None:
        return evidence, [], None
    if len(raw) > SOURCE_BYTES:
        return evidence, [], "SOURCE_TOO_LARGE"
    evidence["bom"] = raw.startswith(b"\xef\xbb\xbf")
    check()
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        return evidence, [], "SOURCE_ENCODING_UNSUPPORTED"
    check()
    tokens, counts = [], {"LF": 0, "CRLF": 0, "CR": 0}
    start = index = total = 0
    # Do not use splitlines: Unicode line separators are ordinary source text.
    while index < len(text):
        if index % CHECK_INTERVAL == 0:
            check()
        char = text[index]
        if ord(char) < 32 and char not in "\r\n\t":
            return evidence, [], "SOURCE_ENCODING_UNSUPPORTED"
        if char not in "\r\n":
            index += 1
            continue
        end = index
        terminator = char
        index += 1
        if char == "\r" and index < len(text) and text[index] == "\n":
            # A consumed LF must not skip a checkpoint boundary.
            if index % CHECK_INTERVAL == 0:
                check()
            terminator += "\n"
            index += 1
        counts[_EOL[terminator]] += 1
        total += 1
        if total <= LINES_PER_SIDE:
            tokens.append((text[start:end], _EOL[terminator]))
        start = index
    if start < len(text):
        total += 1
        if total <= LINES_PER_SIDE:
            tokens.append((text[start:], "none"))
    evidence.update(line_count=total, newlines=counts,
                    final_newline=bool(text) and text[-1] in "\r\n")
    check()
    return evidence, tokens, "LINE_LIMIT" if total > LINES_PER_SIDE else None


def bounded_line_diff(before, after, *, check=None):
    """Return complete exact rows or an explicit row-free unavailable result.

    ``check()`` is called throughout and must raise to cancel or enforce the
    caller's time/authority budget; exceptions propagate unchanged. The largest
    uninterrupted decode/hash/equality operation is bounded by SOURCE_BYTES.
    DP work is capped at DP_CELLS unsigned-short slots (2,000,000 bytes on the
    supported Python runtimes); row count is capped at OUTPUT_ROWS. Other
    storage is linear in the bounded input text and line/output counts. The
    DP limit is not a total process-memory claim: Python object overhead varies.
    Exact common prefix/suffix anchors take priority; remaining LCS ties
    deterministically choose deletion before insertion.
    """
    if check is None:
        check = lambda: None
    check()
    left_evidence, left, left_error = _side(before, check)
    right_evidence, right, right_error = _side(after, check)
    result = {"status": "unavailable", "reason": left_error or right_error,
              "before": left_evidence, "after": right_evidence, "rows": [],
              "limits": {"source_bytes": SOURCE_BYTES, "lines_per_side": LINES_PER_SIDE,
                         "output_rows": OUTPUT_ROWS, "dp_cells": DP_CELLS}}
    if result["reason"]:
        check()
        return result

    # Intern once. The quadratic loop compares integer IDs, not long strings.
    interned = {}
    ids = []
    for tokens in (left, right):
        side_ids = []
        for index, token in enumerate(tokens):
            if index % CHECK_INTERVAL == 0:
                check()
            side_ids.append(interned.setdefault(token, len(interned)))
        ids.append(side_ids)
    a, b = ids
    prefix = 0
    while prefix < min(len(a), len(b)) and a[prefix] == b[prefix]:
        if prefix % CHECK_INTERVAL == 0:
            check()
        prefix += 1
    suffix = 0
    while (suffix < min(len(a), len(b)) - prefix
           and a[len(a) - suffix - 1] == b[len(b) - suffix - 1]):
        if suffix % CHECK_INTERVAL == 0:
            check()
        suffix += 1
    n, m = len(a) - prefix - suffix, len(b) - prefix - suffix
    cells = (n + 1) * (m + 1) if n and m else 0
    if cells > DP_CELLS:
        result["reason"] = "WORK_LIMIT"
        check()
        return result
    check()
    width = m + 1
    table = array("H", [0]) * cells
    work = 0
    for i in range(n - 1, -1, -1):
        base, next_base = i * width, (i + 1) * width
        for j in range(m - 1, -1, -1):
            if work % CHECK_INTERVAL == 0:
                check()
            work += 1
            table[base + j] = (table[next_base + j + 1] + 1
                               if a[prefix + i] == b[prefix + j]
                               else max(table[next_base + j], table[base + j + 1]))
    rows = []

    def emit(kind, li, ri):
        if len(rows) % CHECK_INTERVAL == 0:
            check()
        text, eol = left[li] if li is not None else right[ri]
        rows.append({"kind": kind, "before_line": None if li is None else li + 1,
                     "after_line": None if ri is None else ri + 1, "text": text, "eol": eol})

    for index in range(prefix):
        emit("equal", index, index)
    i = j = 0
    while i < n or j < m:
        if i < n and j < m and a[prefix + i] == b[prefix + j]:
            emit("equal", prefix + i, prefix + j)
            i += 1
            j += 1
        elif i < n and (j == m or table[(i + 1) * width + j] >= table[i * width + j + 1]):
            # Deletion-first ties in the middle, after prefix/suffix anchoring.
            emit("delete", prefix + i, None)
            i += 1
        else:
            emit("insert", None, prefix + j)
            j += 1
    for index in range(suffix):
        emit("equal", len(a) - suffix + index, len(b) - suffix + index)
    check()
    result.update(status="complete", reason=None, rows=rows)
    return result
