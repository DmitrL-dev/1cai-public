"""Bounded, read-only three-way planning for source bytes.

The first update slice works on canonical repository-relative paths. It emits a
dry-run plan and hashes only; it never writes a tree or claims object/UUID
merge semantics that need a native 1C/EDT adapter.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .source_paths import collision_key, validate_file_paths, validate_source_path


_ACTIONS = ("unchanged", "same_change", "keep_current", "take_upstream", "conflict")
_MAX_CONFLICT_PATHS = 256


@dataclass(frozen=True)
class MergeItem:
    path: str
    action: str
    base_sha256: str | None
    current_sha256: str | None
    upstream_sha256: str | None
    base_size_bytes: int | None
    current_size_bytes: int | None
    upstream_size_bytes: int | None


def _limits(max_files, max_file_bytes, max_total_bytes):
    if (
        type(max_files) is not int
        or not 1 <= max_files <= 100_000
        or type(max_file_bytes) is not int
        or not 1 <= max_file_bytes <= 64 * 1024 * 1024
        or type(max_total_bytes) is not int
        or not 1 <= max_total_bytes <= 1024 * 1024 * 1024
    ):
        raise CoreError("THREE_WAY_LIMIT", "Three-way limits are out of bounds")


def _tree(tree, label, *, max_files, max_file_bytes, max_total_bytes):
    if not isinstance(tree, Mapping):
        raise CoreError("THREE_WAY_INVALID", f"{label} tree must be a mapping")
    if len(tree) > max_files:
        raise CoreError("THREE_WAY_LIMIT", f"{label} file limit exceeded")
    try:
        validate_file_paths(tuple(tree))
    except CoreError as exc:
        raise CoreError("THREE_WAY_INVALID", f"Invalid {label} paths") from exc
    result, total = {}, 0
    for path, raw in tree.items():
        try:
            validate_source_path(path)
        except CoreError as exc:
            raise CoreError("THREE_WAY_INVALID", f"Invalid {label} path") from exc
        if type(raw) is not bytes:
            raise CoreError("THREE_WAY_INVALID", f"{label} content must be bytes")
        if len(raw) > max_file_bytes or total + len(raw) > max_total_bytes:
            raise CoreError("THREE_WAY_LIMIT", f"{label} byte limit exceeded")
        identity = collision_key(path)
        result[identity] = (path, raw)
        total += len(raw)
    return result


def _digest(tree):
    return sha256(
        canonical_bytes(
            [
                {
                    "path": path,
                    "sha256": sha256(raw),
                    "size_bytes": len(raw),
                }
                for _, (path, raw) in sorted(
                    tree.items(), key=lambda item: item[1][0].encode("utf-8")
                )
            ]
        )
    )


def _entry(tree, identity):
    item = tree.get(identity)
    return None if item is None else item[1]


def _action(base, current, upstream):
    if current == upstream:
        return "unchanged" if current == base else "same_change"
    if current == base:
        return "take_upstream"
    if upstream == base:
        return "keep_current"
    return "conflict"


def _prepare_trees(
    base,
    current,
    upstream,
    *,
    max_files,
    max_file_bytes,
    max_total_bytes,
):
    _limits(max_files, max_file_bytes, max_total_bytes)
    return {
        label: _tree(
            value,
            label,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )
        for label, value in (
            ("base", base),
            ("current", current),
            ("upstream", upstream),
        )
    }


def _plan_from_trees(trees, *, max_files):
    identities = set().union(*(tree.keys() for tree in trees.values()))
    if len(identities) > max_files:
        raise CoreError("THREE_WAY_LIMIT", "Union file limit exceeded")
    rows = []
    for identity in identities:
        names = {tree[identity][0] for tree in trees.values() if identity in tree}
        if len(names) != 1:
            raise CoreError(
                "THREE_WAY_INVALID", "Path casing differs across input trees"
            )
        path = next(iter(names))
        values = tuple(
            _entry(trees[label], identity) for label in ("base", "current", "upstream")
        )
        action = _action(*values)
        rows.append(
            MergeItem(
                path,
                action,
                None if values[0] is None else sha256(values[0]),
                None if values[1] is None else sha256(values[1]),
                None if values[2] is None else sha256(values[2]),
                None if values[0] is None else len(values[0]),
                None if values[1] is None else len(values[1]),
                None if values[2] is None else len(values[2]),
            )
        )
    rows.sort(key=lambda item: item.path.encode("utf-8"))
    counts = {action: 0 for action in _ACTIONS}
    for row in rows:
        counts[row.action] += 1
    return {
        "schema": 1,
        "scope": "path-bytes-v1",
        "base_digest": _digest(trees["base"]),
        "current_digest": _digest(trees["current"]),
        "upstream_digest": _digest(trees["upstream"]),
        "counts": counts,
        "changes": [asdict(row) for row in rows],
    }


def plan_three_way(
    base,
    current,
    upstream,
    *,
    max_files=10_000,
    max_file_bytes=16 * 1024 * 1024,
    max_total_bytes=64 * 1024 * 1024,
):
    """Return a deterministic dry-run plan for base/current/upstream bytes."""
    trees = _prepare_trees(
        base,
        current,
        upstream,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    return _plan_from_trees(trees, max_files=max_files)


def materialize_three_way(
    base,
    current,
    upstream,
    *,
    max_files=10_000,
    max_file_bytes=16 * 1024 * 1024,
    max_total_bytes=64 * 1024 * 1024,
):
    """Build an in-memory candidate from unambiguous path-level decisions.

    The function is deliberately separate from :func:`plan_three_way`: it never
    returns a partial candidate. Any conflict fails closed before a candidate is
    exposed, while non-conflicting additions, deletions and edits are selected
    from the already validated input trees. No filesystem or live 1C source is
    touched.
    """
    trees = _prepare_trees(
        base,
        current,
        upstream,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    plan = _plan_from_trees(trees, max_files=max_files)
    conflicts = [row["path"] for row in plan["changes"] if row["action"] == "conflict"]
    if conflicts:
        details = {
            "conflicting_paths": conflicts[:_MAX_CONFLICT_PATHS],
            "conflict_count": len(conflicts),
        }
        if len(conflicts) > _MAX_CONFLICT_PATHS:
            details["paths_truncated"] = True
        raise CoreError(
            "THREE_WAY_CONFLICT",
            "Three-way merge has unresolved path conflicts",
            details=details,
        )

    source_by_action = {
        "unchanged": "current",
        "same_change": "current",
        "keep_current": "current",
        "take_upstream": "upstream",
    }
    candidate = {}
    for row in plan["changes"]:
        source = source_by_action[row["action"]]
        item = trees[source].get(collision_key(row["path"]))
        if item is not None:
            candidate[row["path"]] = item[1]

    normalized = _tree(
        candidate,
        "candidate",
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    return {
        "schema": 1,
        "scope": "path-bytes-v1",
        "status": "ready",
        "base_digest": plan["base_digest"],
        "current_digest": plan["current_digest"],
        "upstream_digest": plan["upstream_digest"],
        "candidate_digest": _digest(normalized),
        "candidate": candidate,
    }
