"""Bounded, literal first-match-per-file search over Rust-verified module bytes.

No regex, semantic analysis, extraction, or live-source authority is involved.
"""
import time

from .errors import CoreError
from .rust_input import RustInputSession
from .submitted_export import GUI_PAGE_LIMIT, _authorize, validate_gui_offset

SOURCE_FILE_LIMIT = 256 * 1024
SCAN_BYTE_LIMIT = 32 * 1024**2
SCAN_CHARS = 32768
SNIPPET_CHARS = 512
CPU_SECONDS = 10
WALL_SECONDS = 45


def validate_source_query(query):
    try:
        valid = (type(query) is str and 1 <= len(query.encode("utf-8")) <= 256
                 and not any(ord(char) < 32 and char != "\t" for char in query))
    except UnicodeError:
        valid = False
    if not valid:
        raise CoreError("INVALID_QUERY_OPTIONS", "Source search requires a bounded single-line literal")


class _Budget:
    def __init__(self):
        self.wall = time.monotonic()
        self.cpu = time.thread_time()

    def check(self):
        # Cooperative checks, not an OS quota; child CPU is not thread CPU.
        if time.monotonic() - self.wall >= WALL_SECONDS or time.thread_time() - self.cpu >= CPU_SECONDS:
            raise CoreError("SOURCE_SEARCH_BUDGET_EXCEEDED", "Source search did not complete within its scan budget")

    def measured(self):
        return {"wall_ms": round((time.monotonic() - self.wall) * 1000, 3),
                "thread_cpu_ms": round((time.thread_time() - self.cpu) * 1000, 3)}


def _first_match(text, query, checkpoint):
    """Bound each Python search/control scan, retaining no occurrence list."""
    for offset in range(0, len(text), SCAN_CHARS):
        checkpoint()
        if any(ord(char) < 32 and char not in "\r\n\t" for char in text[offset:offset + SCAN_CHARS]):
            return None, "controls"
    for offset in range(0, len(text), SCAN_CHARS):
        checkpoint()
        chunk = text[offset:offset + SCAN_CHARS + len(query) - 1]
        found = chunk.find(query)
        if found >= 0:
            return offset + found, None
    return None, None


def _excerpt(text, index, query):
    # Only CRLF/CR/LF are line separators; BOM was removed by utf-8-sig.
    before = text[:index]
    line = 1 + before.count("\n") + before.count("\r") - before.count("\r\n")
    line_start = max(text.rfind("\n", 0, index), text.rfind("\r", 0, index)) + 1
    ends = [end for end in (text.find("\n", index), text.find("\r", index)) if end >= 0]
    line_end = min(ends) if ends else len(text)
    start = max(line_start, index - 128)
    end = min(line_end, start + SNIPPET_CHARS)
    assert index + len(query) <= end
    return {"line": line, "excerpt": text[start:end],
            "truncated_before": start > line_start, "truncated_after": end < line_end}


def search_source_files(ctx, *, archive, archive_sha256, input_core, input_core_sha256,
                        query, prefix=None, offset=0, limit=GUI_PAGE_LIMIT, cancelled=None):
    _authorize(ctx)
    validate_source_query(query)
    validate_gui_offset(offset)
    if type(limit) is not int or limit != GUI_PAGE_LIMIT:
        raise CoreError("INVALID_QUERY_OPTIONS", "Source pages contain at most the fixed page limit")
    if prefix is not None and (type(prefix) is not str or not prefix.endswith("/")
            or prefix.startswith("/") or any(part in {"", ".", ".."} for part in prefix[:-1].split("/"))):
        raise CoreError("INVALID_QUERY_OPTIONS", "Source scope requires a server-resolved directory")
    budget = _Budget()

    def checkpoint():
        _authorize(ctx)
        if cancelled is not None and cancelled():
            raise CoreError("CANCELLED", "Source search was cancelled")
        budget.check()

    hits, total, matched, byte_count = [], 0, 0, 0
    coverage = {"in_scope": 0, "searched": 0, "skipped_oversized": 0,
                "skipped_invalid_utf8": 0, "skipped_controls": 0}
    try:
        with RustInputSession(input_core, input_core_sha256, authorize=checkpoint) as session:
            manifest = session.open_import(archive, archive_sha256)
            entries = session.entries(manifest)
            for entry in sorted(entries, key=lambda item: item["path"].encode("utf-8")):
                raw = text = None
                checkpoint()
                path = entry["path"]
                if not path.lower().endswith((".bsl", ".os", ".bsp")):
                    continue
                total += 1
                if prefix is not None and not path.startswith(prefix):
                    continue
                coverage["in_scope"] += 1
                if entry["size_bytes"] > SOURCE_FILE_LIMIT:
                    coverage["skipped_oversized"] += 1
                    continue
                if byte_count + entry["size_bytes"] > SCAN_BYTE_LIMIT:
                    raise CoreError("SOURCE_SEARCH_BUDGET_EXCEEDED", "Source byte scan did not complete")
                raw = session.read_entry(entry)  # Every 32KiB protocol chunk is authorized and hash-checked.
                byte_count += len(raw)
                checkpoint()
                try:
                    text = raw.decode("utf-8-sig", errors="strict")
                except UnicodeError:
                    coverage["skipped_invalid_utf8"] += 1
                    continue
                index, skipped = _first_match(text, query, checkpoint)
                if skipped:
                    coverage["skipped_controls"] += 1
                    continue
                coverage["searched"] += 1
                if index is None:
                    continue
                matched += 1
                if matched > offset and len(hits) < limit:
                    hits.append({"input_ref": {"input_sha256": archive_sha256, "relative_path": path,
                                               "raw_sha256": entry["raw_sha256"]},
                                 "size_bytes": entry["size_bytes"], "analysis": "literal_first_match",
                                 "first_match": _excerpt(text, index, query)})
                # No complete decoded file survives into another iteration or result.
                del raw, text
        checkpoint()
        if offset and offset >= matched:
            raise CoreError("INVALID_QUERY_OPTIONS", "Source page offset is beyond matching files")
        coverage["complete"] = coverage["searched"] == coverage["in_scope"]
        return {"input": manifest, "counts": {"modules": total}, "modules": hits,
                "matching_modules": matched, "modules_truncated": matched > len(hits),
                "source_coverage": coverage, "scan": {**budget.measured(), "bytes_read": byte_count},
                "page": {"offset": offset, "limit": limit, "total": matched, "returned": len(hits),
                         "has_previous": offset > 0, "has_next": offset + len(hits) < matched}}
    finally:
        _authorize(ctx)
