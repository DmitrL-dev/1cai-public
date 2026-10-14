"""Bounded, read-only inventory of three explicitly submitted ZIP manifests.

Inputs come from three completed RustInputSession.entries calls. They are
validated again here, but this module neither opens archives nor reads bytes.
Equality means matching raw SHA-256 and decoded size evidence at the exact path;
it does not establish byte equality, semantic equivalence, or common ancestry.
The caller supplies a fresh authorization/cancellation checkpoint for each call.
No project authorization decision, source bytes, or merge candidate is retained.
"""
import re
import time
import unicodedata

from .errors import CoreError
from .source_paths import validate_source_path
from .three_way import _action

ACTIONS = ("unchanged", "same_change", "keep_current", "take_upstream", "conflict")
FILTERS = frozenset(("all", "changes", *ACTIONS))
SIDES = ("base", "current", "upstream")
PAGE_LIMIT = 200
MAX_OFFSET = 12200
MAX_ENTRIES = 4096
MAX_FILE_BYTES = 4 * 1024**2
MAX_SIDE_BYTES = 32 * 1024**2
MAX_ENTRY_RECORDS = 12288
MAX_TOTAL_BYTES = 96 * 1024**2
MAX_ROWS = 12288
MAX_PATH_BYTES = 1024
CPU_SECONDS = 10
WALL_SECONDS = 45
CHECKPOINT_STEPS = 32
_ENTRY_FIELDS = frozenset({"entry_id", "path", "raw_sha256", "size_bytes"})
_ROW_FIELDS = frozenset({"path", "action", *SIDES})
_EVIDENCE_FIELDS = frozenset({"raw_sha256", "size_bytes"})
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def _fail(code="THREE_ZIP_INVENTORY_INVALID"):
    raise CoreError(code, "Three-ZIP path inventory could not complete the request")


class _Checkpoint:
    """Cooperative per-call budget; it is not an OS resource quota."""

    def __init__(self, checkpoint):
        if not callable(checkpoint):
            _fail()
        self.callback = checkpoint
        self.wall = time.monotonic()
        self.cpu = time.thread_time()
        self.steps = 0

    def _budget(self):
        if (time.monotonic() - self.wall >= WALL_SECONDS
                or time.thread_time() - self.cpu >= CPU_SECONDS):
            _fail("THREE_ZIP_INVENTORY_BUDGET_EXCEEDED")

    def __call__(self):
        # Boundaries and each batch consult current authority. There is no saved
        # allow/deny decision, connection reuse, or authority between API calls.
        self.callback()
        self.steps = 0
        self._budget()

    def step(self):
        self._budget()
        self.steps += 1
        if self.steps >= CHECKPOINT_STEPS:
            self()



def _path(value):
    if type(value) is not str or not 1 <= len(value) <= MAX_PATH_BYTES:
        _fail()
    try:
        if len(value.encode("utf-8")) > MAX_PATH_BYTES:
            _fail()
        validate_source_path(value)
    except (CoreError, UnicodeError) as exc:
        raise CoreError("THREE_ZIP_INVENTORY_INVALID", "Invalid inventory path") from exc
    return value


def _evidence(value):
    if type(value) is not dict or len(value) != 2 or value.keys() != _EVIDENCE_FIELDS:
        _fail()
    digest, size = value["raw_sha256"], value["size_bytes"]
    if type(digest) is not str or len(digest) != 64 or _HASH.fullmatch(digest) is None:
        _fail()
    if type(size) is not int or size < 0:
        _fail()
    if size > MAX_FILE_BYTES:
        _fail("THREE_ZIP_INVENTORY_LIMIT")
    return digest, size


def _as_evidence(value):
    return None if value is None else {"raw_sha256": value[0], "size_bytes": value[1]}


class _Paths:
    """Linear path storage, including for deeply nested adversarial paths."""

    def __init__(self, checkpoint):
        self.files = {}
        self.checkpoint = checkpoint

    def add(self, path):
        # Match Rust's canonical caseless alias key, keeping the exact path as
        # evidence. Normalization is used only for rejection, never output.
        key = unicodedata.normalize("NFC", unicodedata.normalize("NFD", path).casefold())
        if key in self.files and self.files[key] != path:
            _fail()
        self.files[key] = path
        if len(self.files) > MAX_ROWS:
            _fail("THREE_ZIP_INVENTORY_LIMIT")

    def validate(self):
        self.checkpoint()
        # NUL sorts before every allowed path character. Replacing separators
        # therefore implements component ordering without storing all prefixes.
        # Raw path sorting would let a! obscure the file/directory pair a, a/b.
        def order(item):
            self.checkpoint.step()
            return item[0].replace("/", "\0")
        ordered = sorted(self.files.items(), key=order)
        self.checkpoint()
        for index in range(1, len(ordered)):
            self.checkpoint.step()
            left_key, left = ordered[index - 1]
            right_key, right = ordered[index]
            if right_key.startswith(left_key + "/"):
                _fail()
            # Adjacent component-sorted paths witness each shared directory.
            # Parts are bounded by MAX_PATH_BYTES; no prefix inventory is kept.
            for lk, rk, lp, rp in zip(left_key.split("/"), right_key.split("/"),
                                      left.split("/"), right.split("/")):
                self.checkpoint.step()
                if lk != rk:
                    break
                if lp != rp:
                    _fail()


def _counts():
    return dict.fromkeys((*ACTIONS, "total", "files", "changes"), 0)


def classify_entries(base, current, upstream, *, checkpoint):
    """Return ``(rows, counts, coverage)`` from three verified Rust entry lists.

    Entries have exactly entry_id/path/raw_sha256/size_bytes. Each side's IDs
    must be contiguous from zero as guaranteed by RustInputSession.entries.
    ``checkpoint`` must raise when current authorization, cancellation or the
    caller's wider operation budget denies work. It is never cached or caught.
    It runs at most every 32 validation/path-component/classification steps and
    at initial/final boundaries; cheap local CPU/wall checks run at every step.
    Complete coverage describes only the submitted exact-path file inventory.
    """
    check = _Checkpoint(checkpoint)
    check()
    paths = _Paths(check)
    trees = []
    side_counts, side_bytes = {}, {}
    records = decoded_bytes = 0
    for label, entries in zip(SIDES, (base, current, upstream)):
        check()
        if type(entries) not in (list, tuple):
            _fail()
        if len(entries) > MAX_ENTRIES:
            _fail("THREE_ZIP_INVENTORY_LIMIT")
        tree, total = {}, 0
        for index, entry in enumerate(entries):
            check.step()
            if index >= MAX_ENTRIES:
                _fail("THREE_ZIP_INVENTORY_LIMIT")
            if (type(entry) is not dict or len(entry) != 4
                    or entry.keys() != _ENTRY_FIELDS):
                _fail()
            if type(entry["entry_id"]) is not int or entry["entry_id"] != index:
                _fail()
            path = _path(entry["path"])
            value = _evidence({"raw_sha256": entry["raw_sha256"], "size_bytes": entry["size_bytes"]})
            if path in tree:
                _fail()
            paths.add(path)
            tree[path] = value
            total += value[1]
            records += 1
            decoded_bytes += value[1]
            if (total > MAX_SIDE_BYTES or records > MAX_ENTRY_RECORDS
                    or decoded_bytes > MAX_TOTAL_BYTES):
                _fail("THREE_ZIP_INVENTORY_LIMIT")
        trees.append(tree)
        side_counts[label], side_bytes[label] = len(tree), total
    paths.validate()
    # Sorting is bounded to MAX_ROWS keys of at most MAX_PATH_BYTES UTF-8 bytes.
    check()
    def order(path):
        check.step()
        return path.encode("utf-8")
    ordered = sorted(paths.files.values(), key=order)
    check()
    counts, rows = _counts(), []
    for path in ordered:
        check.step()
        values = tuple(tree.get(path) for tree in trees)
        action = _action(*values)
        counts[action] += 1
        rows.append({"path": path, "action": action,
                     **{side: _as_evidence(value) for side, value in zip(SIDES, values)}})
    counts.update(total=len(rows), files=len(rows), changes=len(rows) - counts["unchanged"])
    coverage = {"scope": "exact_path_inventory", "comparison": "raw_sha256_and_size",
                "complete": True, "entry_records": records, "decoded_bytes": decoded_bytes,
                "union_paths": len(rows), "side_entries": side_counts, "side_decoded_bytes": side_bytes}
    check()
    return tuple(rows), counts, coverage


def page_entries(rows, offset, action, *, checkpoint):
    """Page classifier rows; counts/coverage remain those of the full inventory.

    The caller binds these results to its accepted manifests and separately
    enforces current page authority. No page capability is created here.
    Scan beyond the display cap to establish the exact filtered total and to
    observe cancellation/authorization/budget denial before returning anything.
    """
    check = _Checkpoint(checkpoint)
    check()
    if (type(offset) is not int or not 0 <= offset <= MAX_OFFSET or offset % PAGE_LIMIT
            or type(action) is not str or action not in FILTERS):
        _fail("INVALID_QUERY_OPTIONS")
    if type(rows) not in (tuple, list):
        _fail()
    if len(rows) > MAX_ROWS:
        _fail("THREE_ZIP_INVENTORY_LIMIT")
    selected, total, previous = [], 0, None
    for index, row in enumerate(rows):
        check.step()
        if index >= MAX_ROWS:
            _fail("THREE_ZIP_INVENTORY_LIMIT")
        if type(row) is not dict or len(row) != 5 or row.keys() != _ROW_FIELDS:
            _fail()
        path = _path(row["path"])
        encoded = path.encode("utf-8")
        if previous is not None and encoded <= previous:
            _fail()
        previous = encoded
        values = tuple(None if row[side] is None else _evidence(row[side]) for side in SIDES)
        if (all(value is None for value in values) or type(row["action"]) is not str
                or row["action"] != _action(*values)):
            _fail()
        if action == "all" or row["action"] == action or (action == "changes" and row["action"] != "unchanged"):
            if offset <= total < offset + PAGE_LIMIT:
                # Disclosure values are detached from the accepted cached rows.
                selected.append({"path": path, "action": row["action"],
                                 **{side: _as_evidence(value) for side, value in zip(SIDES, values)}})
            total += 1
    if offset and offset >= total:
        _fail("INVALID_QUERY_OPTIONS")
    page = {"offset": offset, "limit": PAGE_LIMIT, "total": total, "returned": len(selected),
            "has_previous": offset > 0, "has_next": offset + len(selected) < total}
    check()
    return {"action": action, "page": page, "rows": selected}
