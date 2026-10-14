"""Bounded literal occurrences in one server-selected Rust-verified module.

An input reference is an equality constraint, not authority to choose a source.
The caller must resolve it from the current server-owned source selection and
revalidate that selection and permissions before disclosing the result.
"""
import re
import time

from .errors import CoreError
from .rust_input import RustInputSession
from .source_paths import validate_source_path
from .source_search import SOURCE_FILE_LIMIT, SNIPPET_CHARS, validate_source_query
from .submitted_export import GUI_PAGE_LIMIT, _authorize

SCAN_CHARS = 32768
MAX_OCCURRENCE_OFFSET = (SOURCE_FILE_LIMIT // GUI_PAGE_LIMIT) * GUI_PAGE_LIMIT
CPU_SECONDS = 10
WALL_SECONDS = 45
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def validate_occurrence_offset(offset):
    if (type(offset) is not int or not 0 <= offset <= MAX_OCCURRENCE_OFFSET
            or offset % GUI_PAGE_LIMIT):
        raise CoreError("INVALID_QUERY_OPTIONS", "Occurrence page offset must be bounded and aligned")


def _reference(reference, archive_sha256):
    if type(reference) is not dict or set(reference) != {"input_sha256", "relative_path", "raw_sha256"}:
        raise CoreError("SOURCE_NOT_AVAILABLE", "Selected module reference is not available")
    reference = dict(reference)
    if any(type(reference[key]) is not str or _HASH.fullmatch(reference[key]) is None
           for key in ("input_sha256", "raw_sha256")) or reference["input_sha256"] != archive_sha256:
        raise CoreError("SOURCE_NOT_AVAILABLE", "Selected module reference is not available")
    path = reference["relative_path"]
    try:
        if (type(path) is not str or not 1 <= len(path.encode("utf-8")) <= 1024
                or not path.lower().endswith((".bsl", ".os", ".bsp"))):
            raise ValueError
        validate_source_path(path)
    except (CoreError, ValueError, TypeError, UnicodeError):
        raise CoreError("SOURCE_NOT_AVAILABLE", "Selected module reference is not available") from None
    return reference


def _excerpt(text, index, line_start):
    # Only inspect this bounded window, even for a very long single line.
    start = max(line_start, index - 128)
    end = min(len(text), start + SNIPPET_CHARS)
    for newline in ("\r", "\n"):
        found = text.find(newline, start, end)
        if found >= 0:
            end = found
    return {"excerpt": text[start:end], "truncated_before": start > line_start,
            "truncated_after": end < len(text) and text[end] not in "\r\n"}


def _scan(text, query, offset, checkpoint):
    """Linear traversal with bounded literal comparisons; retain one page only.

Each start position is visited, so overlapping hits and misses have the same
bounded checkpoint interval. A comparison reads at most the validated query's
256 UTF-8 bytes; excerpts inspect at most 512 codepoints, for at most 200 hits.
"""
    rows, total = [], 0
    line, line_start, previous_cr = 1, 0, False
    for chunk in range(0, len(text), SCAN_CHARS):
        checkpoint()
        for index in range(chunk, min(len(text), chunk + SCAN_CHARS)):
            char = text[index]
            if ord(char) < 32 and char not in "\r\n\t":
                raise CoreError("SOURCE_ENCODING_UNSUPPORTED", "Selected module encoding is not supported")
            if text.startswith(query, index):
                total += 1
                if total > offset and len(rows) < GUI_PAGE_LIMIT:
                    rows.append({"line": line, "column": index - line_start + 1,
                                 "offset": index, **_excerpt(text, index, line_start)})
            if char == "\r":
                line += 1
                line_start = index + 1
            elif char == "\n":
                if not previous_cr:
                    line += 1
                line_start = index + 1
            previous_cr = char == "\r"
    checkpoint()
    return rows, total


def search_source_occurrences(ctx, *, archive, archive_sha256, input_core, input_core_sha256,
                              reference, query, offset=0, cancelled=None):
    """Search one current server-selected module; never accepts a live locator."""
    _authorize(ctx)
    wall, cpu = time.monotonic(), time.thread_time()

    def checkpoint():
        _authorize(ctx)
        if cancelled is not None and cancelled():
            raise CoreError("CANCELLED", "Source occurrence search was cancelled")
        if time.monotonic() - wall >= WALL_SECONDS or time.thread_time() - cpu >= CPU_SECONDS:
            raise CoreError("SOURCE_SEARCH_BUDGET_EXCEEDED", "Source search did not complete within its scan budget")

    try:
        validate_source_query(query)
        validate_occurrence_offset(offset)
        selected = _reference(reference, archive_sha256)
        checkpoint()
        with RustInputSession(input_core, input_core_sha256, authorize=checkpoint) as session:
            manifest = session.open_import(archive, archive_sha256)
            entries = session.entries(manifest)
            entry = None
            for index, candidate in enumerate(entries):
                if index % 32 == 0:
                    checkpoint()
                if candidate["path"] == selected["relative_path"]:
                    entry = candidate
                    break
            if (entry is None or entry["raw_sha256"] != selected["raw_sha256"]
                    or manifest["input_sha256"] != selected["input_sha256"]):
                raise CoreError("SOURCE_NOT_AVAILABLE", "Selected module reference is not available")
            if entry["size_bytes"] > SOURCE_FILE_LIMIT:
                raise CoreError("SOURCE_TOO_LARGE", "Selected module exceeds the source preview limit")
            raw = session.read_entry(entry)
            checkpoint()
            try:
                text = raw.decode("utf-8-sig", errors="strict")
            except UnicodeError:
                raise CoreError("SOURCE_ENCODING_UNSUPPORTED", "Selected module encoding is not supported") from None
            rows, total = _scan(text, query, offset, checkpoint)
        checkpoint()
        if offset and offset >= total:
            raise CoreError("INVALID_QUERY_OPTIONS", "Occurrence page offset is beyond matching occurrences")
        return {"input_ref": selected, "size_bytes": len(raw), "query": query,
                "analysis": "literal_occurrences",
                "conventions": {"line_base": 1, "column_base": 1,
                                "column_unit": "unicode_codepoint", "newlines": "CRLF_CR_LF",
                                "bom": "excluded", "overlap": True, "case_sensitive": True,
                                "normalization": "none"},
                "occurrences": rows, "coverage": {"complete": True, "characters_scanned": len(text)},
                "page": {"offset": offset, "limit": GUI_PAGE_LIMIT, "total": total,
                         "returned": len(rows), "has_previous": offset > 0,
                         "has_next": offset + len(rows) < total}}
    finally:
        _authorize(ctx)
