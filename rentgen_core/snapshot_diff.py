"""Deterministic file changes between two authorized, verified retained snapshots."""
from dataclasses import asdict
import hashlib
import json
import re

from .errors import CoreError
from .resolver import require_snapshot
from .sources import SnapshotReadLimits


def compare_snapshots(before, after, *, limit=100, cursor=None):
    if before is None or after is None:
        raise CoreError(
            "CONTEXT_REQUIRED", "Two explicit project contexts are required"
        )
    if before.project_id != after.project_id or before.principal != after.principal:
        raise CoreError(
            "CONTEXT_PROJECT_MISMATCH", "Comparison requires one project and principal"
        )
    left_ref, right_ref = require_snapshot(before), require_snapshot(after)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise CoreError(
            "INVALID_QUERY_OPTIONS", "Comparison page size must be 1 to 100"
        )
    binding = hashlib.sha256(
        json.dumps(
            [before.project_id, asdict(left_ref), asdict(right_ref), limit],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    offset = 0
    if cursor is not None:
        match = (
            re.fullmatch(r"v1\.([0-9a-f]{64})\.([1-9][0-9]{0,4})", cursor)
            if isinstance(cursor, str)
            else None
        )
        if not match or match[1] != binding or int(match[2]) % limit:
            raise CoreError(
                "INVALID_DIFF_CURSOR", "Cursor does not match this comparison"
            )
        offset = int(match[2])
    limits = SnapshotReadLimits()
    with before.sources.read_session(limits=limits) as left, after.sources.read_session(
        limits=limits
    ) as right:

        def index(session):
            return {
                (entry.ref.layer_id, entry.ref.relative_path): entry
                for entry in session.entries()
            }

        old, new = index(left), index(right)
        counts = dict(added=0, removed=0, modified=0, unchanged=0)
        changes = []
        for position, key in enumerate(sorted(old.keys() | new.keys())):
            if position % 256 == 0:
                left.checkpoint()
                right.checkpoint()
            previous, current = old.get(key), new.get(key)
            if previous is None:
                kind = "added"
            elif current is None:
                kind = "removed"
            elif (previous.ref.raw_sha256, previous.size_bytes) == (
                current.ref.raw_sha256,
                current.size_bytes,
            ):
                kind = "unchanged"
            else:
                kind = "modified"
            counts[kind] += 1
            if kind != "unchanged":
                changes.append({"kind": kind, "before": previous, "after": current})
        if cursor is not None and offset >= len(changes):
            raise CoreError("INVALID_DIFF_CURSOR", "Cursor exceeds comparison changes")
        result = {
            "before_snapshot": left_ref,
            "after_snapshot": right_ref,
            "scope": "source_bytes_by_layer_and_path",
            "identity": "source_path_only",
            "counts": counts,
            "changes": changes[offset : offset + limit],
            "next_cursor": f"v1.{binding}.{offset + limit}"
            if offset + limit < len(changes)
            else None,
        }
        if (
            len(json.dumps(result, default=asdict, ensure_ascii=True).encode("ascii"))
            > 1048576
        ):
            raise CoreError(
                "DIFF_PAGE_LIMIT", "Comparison page exceeds 1 MiB; reduce --limit"
            )
        return result
