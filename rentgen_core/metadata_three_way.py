"""Conservative UUID-aware three-way planning for Designer XML objects."""

from dataclasses import asdict, dataclass
import re
import xml.etree.ElementTree as ET

from .errors import CoreError
from .manifests import sha256
from .three_way import _action, plan_three_way


_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z",
    re.IGNORECASE,
)
_ROOT = "MetaDataObject"
_PROPERTIES = "Properties"
_NAME = "Name"
_MAX_OBJECTS = 100_000


@dataclass(frozen=True)
class ObjectMergeItem:
    object_type: str
    object_uuid: str
    action: str
    base_path: str | None
    current_path: str | None
    upstream_path: str | None
    base_name: str | None
    current_name: str | None
    upstream_name: str | None
    base_sha256: str | None
    current_sha256: str | None
    upstream_sha256: str | None
    base_size_bytes: int | None
    current_size_bytes: int | None
    upstream_size_bytes: int | None


def _object(value, path):
    if not path.lower().endswith(".xml"):
        return None
    try:
        root = ET.fromstring(value)
    except (ET.ParseError, ValueError, UnicodeError) as exc:
        raise CoreError(
            "THREE_WAY_METADATA_INVALID", f"Invalid metadata XML: {path}"
        ) from exc
    if root.tag.rsplit("}", 1)[-1] != _ROOT:
        return None
    candidates = [
        child
        for child in root
        if child.tag.rsplit("}", 1)[-1] not in {_PROPERTIES, "ChildObjects"}
    ]
    if len(candidates) != 1:
        return None
    node = candidates[0]
    object_type = node.tag.rsplit("}", 1)[-1]
    identity = node.get("uuid")
    if identity is None:
        return None
    if _UUID.fullmatch(identity) is None:
        raise CoreError("THREE_WAY_METADATA_INVALID", f"Invalid metadata UUID: {path}")
    names = [
        child.text
        for child in node.iter()
        if child.tag.rsplit("}", 1)[-1] == _NAME and child.text
    ]
    if len(names) != 1:
        raise CoreError(
            "THREE_WAY_METADATA_INVALID", f"Metadata name is ambiguous: {path}"
        )
    return object_type, identity.lower(), names[0]


def _records(tree, label):
    result = {}
    unsupported = []
    for path, value in sorted(tree.items(), key=lambda item: item[0].encode("utf-8")):
        item = _object(value, path)
        if item is None:
            unsupported.append(path)
            continue
        object_type, identity, name = item
        key = (object_type, identity)
        if key in result:
            raise CoreError(
                "THREE_WAY_METADATA_INVALID",
                f"Duplicate metadata UUID in {label}: {identity}",
            )
        result[key] = {
            "path": path,
            "name": name,
            "raw": value,
        }
        if len(result) > _MAX_OBJECTS:
            raise CoreError("THREE_WAY_LIMIT", "Metadata object limit exceeded")
    return result, unsupported


def _merge_action(base, current, upstream):
    content = _action(
        None if base is None else base["raw"],
        None if current is None else current["raw"],
        None if upstream is None else upstream["raw"],
    )
    paths = _action(
        None if base is None else base["path"],
        None if current is None else current["path"],
        None if upstream is None else upstream["path"],
    )
    if "conflict" in {content, paths}:
        return "conflict"
    if "same_change" in {content, paths}:
        return "same_change"
    if content == "unchanged":
        return paths
    if paths == "unchanged":
        return content
    if content == paths:
        return content
    return "conflict"


def _digest(value):
    return None if value is None else sha256(value)


def plan_metadata_three_way(
    base,
    current,
    upstream,
    *,
    max_files=10_000,
    max_file_bytes=16 * 1024 * 1024,
    max_total_bytes=64 * 1024 * 1024,
):
    """Return UUID-aware metadata actions while leaving all trees untouched."""
    path_plan = plan_three_way(
        base,
        current,
        upstream,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    trees = {"base": base, "current": current, "upstream": upstream}
    records = {}
    unsupported = set()
    for label, tree in trees.items():
        found, skipped = _records(tree, label)
        records[label] = found
        unsupported.update(skipped)
    identities = set().union(*(value.keys() for value in records.values()))
    if len(identities) > min(max_files, _MAX_OBJECTS):
        raise CoreError("THREE_WAY_LIMIT", "Metadata object union limit exceeded")
    rows = []
    for object_type, identity in identities:
        values = tuple(records[label].get((object_type, identity)) for label in records)
        rows.append(
            ObjectMergeItem(
                object_type=object_type,
                object_uuid=identity,
                action=_merge_action(*values),
                base_path=None if values[0] is None else values[0]["path"],
                current_path=None if values[1] is None else values[1]["path"],
                upstream_path=None if values[2] is None else values[2]["path"],
                base_name=None if values[0] is None else values[0]["name"],
                current_name=None if values[1] is None else values[1]["name"],
                upstream_name=None if values[2] is None else values[2]["name"],
                base_sha256=_digest(None if values[0] is None else values[0]["raw"]),
                current_sha256=_digest(None if values[1] is None else values[1]["raw"]),
                upstream_sha256=_digest(
                    None if values[2] is None else values[2]["raw"]
                ),
                base_size_bytes=None if values[0] is None else len(values[0]["raw"]),
                current_size_bytes=None if values[1] is None else len(values[1]["raw"]),
                upstream_size_bytes=None
                if values[2] is None
                else len(values[2]["raw"]),
            )
        )
    rows.sort(key=lambda item: (item.object_type, item.object_uuid))
    counts = {
        action: 0
        for action in (
            "unchanged",
            "same_change",
            "keep_current",
            "take_upstream",
            "conflict",
        )
    }
    for row in rows:
        counts[row.action] += 1
    return {
        "schema": 1,
        "scope": "metadata-object-v1",
        "coverage": "partial",
        "base_digest": path_plan["base_digest"],
        "current_digest": path_plan["current_digest"],
        "upstream_digest": path_plan["upstream_digest"],
        "counts": counts,
        "objects": [asdict(row) for row in rows],
        "unsupported_files": sorted(unsupported, key=lambda path: path.encode("utf-8")),
    }
