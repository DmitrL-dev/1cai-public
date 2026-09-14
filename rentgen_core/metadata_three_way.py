"""Conservative UUID-aware planning and qualified Designer property merging."""

from dataclasses import asdict, dataclass
import copy
import re
import xml.etree.ElementTree as ET
from xml.parsers import expat

from .errors import CoreError
from .manifests import sha256
from .source_paths import collision_key
from .three_way import (
    _action,
    _digest as _tree_digest,
    _plan_from_trees,
    _prepare_trees,
    _tree,
)


_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z",
    re.IGNORECASE,
)
_ROOT = "MetaDataObject"
_PROPERTIES = "Properties"
_NAME = "Name"
_MAX_OBJECTS = 100_000
_UNSAFE_DECLARATION = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_MD_NS = "http://v8.1c.ru/8.3/MDClasses"
_FORM_ROOT = "{http://v8.1c.ru/8.3/xcf/logform}Form"
_DCS_ROOT = "{http://v8.1c.ru/8.1/data-composition-system/schema}DataCompositionSchema"
_EXTENSION_PROPERTIES = frozenset(
    {"ObjectBelonging", "ExtendedConfigurationObject", "ConfigurationExtensionPurpose"}
)
_MODULE_OWNERS = {
    "ext/module.bsl": {"CommonModule"},
    "ext/form/module.bsl": {"Form", "CommonForm"},
    "ext/objectmodule.bsl": {
        "Catalog",
        "Document",
        "Report",
        "DataProcessor",
        "ExternalReport",
        "ExternalDataProcessor",
        "ChartOfAccounts",
        "ChartOfCharacteristicTypes",
        "ChartOfCalculationTypes",
        "BusinessProcess",
        "Task",
        "ExchangePlan",
    },
    "ext/managermodule.bsl": {
        "Catalog",
        "Document",
        "Report",
        "DataProcessor",
        "ChartOfAccounts",
        "ChartOfCharacteristicTypes",
        "ChartOfCalculationTypes",
        "BusinessProcess",
        "Task",
        "ExchangePlan",
        "InformationRegister",
        "AccumulationRegister",
        "AccountingRegister",
        "CalculationRegister",
    },
    "ext/recordsetmodule.bsl": {
        "InformationRegister",
        "AccumulationRegister",
        "AccountingRegister",
        "CalculationRegister",
    },
    "ext/commandmodule.bsl": {"Command", "CommonCommand"},
}


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
    property_mergeability: str
    property_changes: list["PropertyMergeItem"]


@dataclass(frozen=True)
class PropertyMergeItem:
    property_name: str
    action: str
    base_sha256: str | None
    current_sha256: str | None
    upstream_sha256: str | None
    base_size_bytes: int | None
    current_size_bytes: int | None
    upstream_size_bytes: int | None


def _property_fingerprint(element):
    raw = ET.tostring(element, encoding="utf-8", short_empty_elements=True)
    return sha256(raw), len(raw)


def _unscoped_fingerprint(node):
    scoped = copy.deepcopy(node)
    for child in list(scoped):
        if child.tag.rsplit("}", 1)[-1] == _PROPERTIES:
            scoped.remove(child)
    raw = ET.tostring(scoped, encoding="utf-8", short_empty_elements=True)
    return sha256(raw), len(raw)


def _object(value, path):
    if not path.lower().endswith(".xml"):
        return None
    # Scan ASCII declarations even in UTF-16/32 before ElementTree can expand them.
    if _UNSAFE_DECLARATION.search(value.replace(b"\x00", b"")):
        raise CoreError(
            "THREE_WAY_METADATA_INVALID",
            f"DTD and ENTITY declarations are forbidden: {path}",
        )
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
    properties_nodes = [
        child for child in node if child.tag.rsplit("}", 1)[-1] == _PROPERTIES
    ]
    names = [
        child.text
        for properties_node in properties_nodes
        for child in properties_node
        if child.tag.rsplit("}", 1)[-1] == _NAME and child.text
    ]
    if len(names) != 1:
        raise CoreError(
            "THREE_WAY_METADATA_INVALID", f"Metadata name is ambiguous: {path}"
        )
    properties = None
    if len(properties_nodes) == 1:
        properties = {}
        for child in properties_nodes[0]:
            property_name = child.tag.rsplit("}", 1)[-1]
            if property_name in properties:
                raise CoreError(
                    "THREE_WAY_METADATA_INVALID",
                    f"Metadata property is ambiguous: {path}:{property_name}",
                )
            properties[property_name] = _property_fingerprint(child)
    return (
        object_type,
        identity.lower(),
        names[0],
        properties,
        _unscoped_fingerprint(node),
        node,
    )


def _records(tree, label):
    result = {}
    unsupported = []
    for path, value in sorted(tree.items(), key=lambda item: item[0].encode("utf-8")):
        item = _object(value, path)
        if item is None:
            unsupported.append(path)
            continue
        object_type, identity, name, properties, unscoped, node = item
        key = (object_type, identity)
        if key in result:
            raise CoreError(
                "THREE_WAY_METADATA_INVALID",
                f"Duplicate metadata UUID in {label}: {identity}",
            )
        result[key] = {
            "path": path,
            "name": name,
            "properties": properties,
            "unscoped": unscoped,
            "raw": value,
            "node": node,
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


def _property_action(base, current, upstream):
    return _action(
        None if base is None else base[0],
        None if current is None else current[0],
        None if upstream is None else upstream[0],
    )


def _property_changes(values):
    if any(value is None or value["properties"] is None for value in values):
        return "not_available", []
    properties = set().union(*(value["properties"] for value in values))
    changes = []
    actions = set()
    for property_name in sorted(properties, key=lambda value: value.encode("utf-8")):
        fingerprints = tuple(value["properties"].get(property_name) for value in values)
        action = _property_action(*fingerprints)
        if action == "unchanged":
            continue
        actions.add(action)
        changes.append(
            PropertyMergeItem(
                property_name=property_name,
                action=action,
                base_sha256=None if fingerprints[0] is None else fingerprints[0][0],
                current_sha256=None if fingerprints[1] is None else fingerprints[1][0],
                upstream_sha256=None if fingerprints[2] is None else fingerprints[2][0],
                base_size_bytes=None if fingerprints[0] is None else fingerprints[0][1],
                current_size_bytes=None
                if fingerprints[1] is None
                else fingerprints[1][1],
                upstream_size_bytes=None
                if fingerprints[2] is None
                else fingerprints[2][1],
            )
        )
    if not actions:
        return "unchanged", changes
    if "conflict" in actions:
        return "overlap_conflict", changes
    if "keep_current" in actions and "take_upstream" in actions:
        return "disjoint_changes", changes
    if actions == {"same_change"}:
        return "same_change", changes
    if actions == {"keep_current"}:
        return "keep_current", changes
    if actions == {"take_upstream"}:
        return "take_upstream", changes
    return "mixed_changes", changes


def _unscoped_action(values):
    return _action(
        None if values[0] is None else values[0]["unscoped"],
        None if values[1] is None else values[1]["unscoped"],
        None if values[2] is None else values[2]["unscoped"],
    )


def _direct_property(node, name):
    return node.find(f"{{{_MD_NS}}}Properties/{{{_MD_NS}}}{name}")


def _companion_kind(path):
    path = "/" + path.casefold()
    if path.endswith(".bsl"):
        return "bsl"
    if path.endswith("/ext/form.xml"):
        return "form"
    if path.endswith("/ext/template.xml"):
        return "data_composition_schema"
    return None


def _companion_reason(kind, scope, raw, owner):
    if owner is None:
        return "owner_not_found"
    object_type, record = owner
    node = record["node"]
    if node.tag != f"{{{_MD_NS}}}{object_type}":
        return "owner_namespace_unsupported"
    if kind == "bsl":
        scope_key = scope.casefold()
        if scope_key not in _MODULE_OWNERS:
            return "scope_unsupported"
        if object_type not in _MODULE_OWNERS[scope_key]:
            return "owner_type_unsupported"
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return "bsl_encoding_unsupported"
        if "\x00" in text:
            return "bsl_encoding_unsupported"
    else:
        expected_types = (
            {"Form", "CommonForm"} if kind == "form" else {"Template", "CommonTemplate"}
        )
        if object_type not in expected_types:
            return "owner_type_unsupported"
        # XML has already passed the bounded, declaration-free parser in _records.
        root = ET.fromstring(raw)
        expected_root = _FORM_ROOT if kind == "form" else _DCS_ROOT
        if root.tag != expected_root:
            return "xml_shape_unsupported"
        if kind == "data_composition_schema":
            template_type = _direct_property(node, "TemplateType")
            if template_type is None or template_type.text != "DataCompositionSchema":
                return "template_type_unsupported"
    return None


def _semantic_records(tree, records):
    owners = {
        collision_key(record["path"]): (key, record) for key, record in records.items()
    }
    result = {}
    for path, raw in tree.items():
        kind = _companion_kind(path)
        if kind is None:
            continue
        parts = path.split("/")
        ext_index = next(
            (
                index
                for index in range(len(parts) - 2, 0, -1)
                if parts[index].casefold() == "ext"
            ),
            None,
        )
        scope = path if ext_index is None else "/".join(parts[ext_index:])
        owner = (
            None
            if ext_index is None
            else owners.get(collision_key("/".join(parts[:ext_index]) + ".xml"))
        )
        identity = ("", "") if owner is None else owner[0]
        reason = _companion_reason(
            kind, scope, raw, None if owner is None else (identity[0], owner[1])
        )
        key = (*identity, collision_key(path if owner is None else scope))
        result[key] = {
            "path": path,
            "scope": path if owner is None else scope,
            "raw": raw,
            "kind": kind,
            "reason": reason,
        }
    for identity, record in records.items():
        declarations = [
            element
            for name in sorted(_EXTENSION_PROPERTIES)
            if (element := _direct_property(record["node"], name)) is not None
        ]
        if declarations:
            result[(*identity, "properties/extension")] = {
                "path": record["path"],
                "scope": "Properties/Extension",
                "raw": b"".join(
                    ET.tostring(element, encoding="utf-8") for element in declarations
                ),
                "kind": "extension",
                "reason": "extension_ownership_unverified",
            }
    return result


def _semantic_plan(trees, records):
    versions = [
        _semantic_records(tree, records[label]) for label, tree in trees.items()
    ]
    identities = set().union(*(version.keys() for version in versions))
    path_owners = {}
    for version in versions:
        for key, value in version.items():
            path_owners.setdefault(value["path"], set()).add(key[:2])
    rows = []
    for object_type, identity, scope in sorted(identities):
        values = [version.get((object_type, identity, scope)) for version in versions]
        existing = [value for value in values if value is not None]
        action = _merge_action(*values)
        reasons = sorted({value["reason"] for value in existing if value["reason"]})
        if identity:
            bindings = set().union(*(path_owners[value["path"]] for value in existing))
            if len(bindings - {("", "")}) > 1:
                reasons = ["owner_identity_changed"]
            elif ("", "") in bindings:
                reasons = ["owner_binding_incomplete"]
        if reasons:
            status, reason = "unsupported", reasons[0]
        elif action == "conflict":
            status, reason = "conflict", "atomic_overlap"
        else:
            status, reason = "supported", "atomic_scope_only"
        row = {
            "object_type": object_type or None,
            "object_uuid": identity or None,
            "kind": existing[0]["kind"],
            "scope": existing[0]["scope"],
            "granularity": "atomic_bytes",
            "action": action,
            "status": status,
            "reason": reason,
        }
        for label, value in zip(trees, values):
            row[label + "_path"] = None if value is None else value["path"]
            row[label + "_sha256"] = None if value is None else sha256(value["raw"])
            row[label + "_size_bytes"] = None if value is None else len(value["raw"])
        rows.append(row)
    return {"schema": 1, "mode": "read_only", "coverage": "partial", "scopes": rows}


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
    snapshots = _prepare_trees(
        base,
        current,
        upstream,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    return _metadata_plan(snapshots, max_files=max_files)[0]


def _metadata_plan(snapshots, *, max_files):
    path_plan = _plan_from_trees(snapshots, max_files=max_files)
    trees = {label: dict(tree.values()) for label, tree in snapshots.items()}
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
        property_mergeability, property_changes = _property_changes(values)
        if (
            property_mergeability != "not_available"
            and _unscoped_action(values) != "unchanged"
        ):
            property_mergeability = "unscoped_content"
        elif property_mergeability == "unchanged":
            content_action = _action(
                None if values[0] is None else values[0]["raw"],
                None if values[1] is None else values[1]["raw"],
                None if values[2] is None else values[2]["raw"],
            )
            path_action = _action(
                None if values[0] is None else values[0]["path"],
                None if values[1] is None else values[1]["path"],
                None if values[2] is None else values[2]["path"],
            )
            if content_action == "unchanged" and path_action != "unchanged":
                property_mergeability = "path_only"
            elif content_action != "unchanged":
                property_mergeability = "unscoped_content"
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
                property_mergeability=property_mergeability,
                property_changes=property_changes,
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
    plan = {
        "schema": 1,
        "scope": "metadata-object-v1",
        "coverage": "partial",
        "base_digest": path_plan["base_digest"],
        "current_digest": path_plan["current_digest"],
        "upstream_digest": path_plan["upstream_digest"],
        "counts": counts,
        "objects": [asdict(row) for row in rows],
        "unsupported_files": sorted(unsupported, key=lambda path: path.encode("utf-8")),
        "semantics": _semantic_plan(trees, records),
    }
    return plan, path_plan, trees, records


_MAX_MERGE_EVIDENCE = 256
_SOURCE_BY_ACTION = {
    "unchanged": "current",
    "same_change": "current",
    "keep_current": "current",
    "take_upstream": "upstream",
}


class _UnsupportedPropertyMerge(Exception):
    """Carries only a fixed reason code, never input XML."""


def _materialization_shape(record):
    root = ET.fromstring(record["raw"])
    node = record["node"]
    properties = list(node.findall(f"{{{_MD_NS}}}Properties"))
    return (
        root.tag == f"{{{_MD_NS}}}{_ROOT}"
        and len(root) == 1
        and node.tag.startswith(f"{{{_MD_NS}}}")
        and len(properties) == 1
        and record["properties"] is not None
        and all(child.tag.startswith(f"{{{_MD_NS}}}") for child in properties[0])
    )


def _property_layout(raw):
    """Locate direct property bytes without rewriting namespaces or QName values.

    This qualified splice accepts UTF-8 XML only. Expat provides byte offsets;
    ElementTree has already validated the declaration-free object and identity.
    """
    try:
        raw.decode("utf-8-sig")
    except UnicodeError:
        raise _UnsupportedPropertyMerge("property_encoding_unsupported") from None
    if b"\x00" in raw:
        raise _UnsupportedPropertyMerge("property_encoding_unsupported")
    parser = expat.ParserCreate(namespace_separator="}")
    stack, spans, bounds = [], {}, []

    def opening_end(begin):
        quote = None
        for offset in range(begin, len(raw)):
            char = raw[offset]
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in (34, 39):
                quote = char
            elif char == 62:
                return offset + 1
        raise _UnsupportedPropertyMerge("property_xml_unsupported")

    def declaration(version, encoding, standalone):
        if encoding and encoding.lower() not in {"utf-8", "utf8", "us-ascii", "ascii"}:
            raise _UnsupportedPropertyMerge("property_encoding_unsupported")

    def start(name, attributes):
        begin = parser.CurrentByteIndex
        stack.append((name, begin, opening_end(begin)))

    def end(name):
        tag, begin, open_end = stack.pop()
        index = parser.CurrentByteIndex
        finish = (
            open_end
            if raw[open_end - 2 : open_end] == b"/>"
            else raw.find(b">", index) + 1
        )
        if len(stack) == 3 and stack[-1][0] == f"{_MD_NS}}}Properties":
            spans[tag.rsplit("}", 1)[-1]] = (begin, finish)
        elif len(stack) == 2 and tag == f"{_MD_NS}}}Properties":
            bounds.extend((open_end, index))

    parser.XmlDeclHandler = declaration
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    try:
        parser.Parse(raw, True)
    except expat.ExpatError:
        raise _UnsupportedPropertyMerge("property_xml_unsupported") from None
    if len(bounds) != 2 or not spans:
        raise _UnsupportedPropertyMerge("properties_shape_unsupported")
    first, last = bounds
    cursor = first
    fragments = {}
    items = list(spans.items())
    for index, (name, (begin, finish)) in enumerate(items):
        if raw[cursor:begin].strip():
            raise _UnsupportedPropertyMerge("properties_unscoped_content")
        following = items[index + 1][1][0] if index + 1 < len(items) else last
        fragments[name] = raw[begin:following]
        cursor = finish
    if raw[cursor:last].strip():
        raise _UnsupportedPropertyMerge("properties_unscoped_content")
    return raw[: items[0][1][0]], raw[last:], fragments


def _merge_properties(values):
    layouts = [_property_layout(value["raw"]) for value in values]
    if any(layout[:2] != layouts[0][:2] for layout in layouts[1:]):
        raise _UnsupportedPropertyMerge("xml_envelope_changed")
    fragments = [layout[2] for layout in layouts]
    names = set().union(*fragments)
    selected = {}
    for name in sorted(names):
        action = _property_action(*(value["properties"].get(name) for value in values))
        lexical_action = _action(*(fragment.get(name) for fragment in fragments))
        if action != lexical_action or action not in _SOURCE_BY_ACTION:
            raise _UnsupportedPropertyMerge("property_lexical_change_unsupported")
        source = 2 if action == "take_upstream" else 1
        if name in fragments[source]:
            selected[name] = fragments[source][name]
    current_order = [name for name in fragments[1] if name in selected]
    current_names = set(current_order)
    before, pending = {}, []
    for name in fragments[2]:
        if name not in selected:
            continue
        if name in current_names:
            before[name], pending = pending, []
        else:
            pending.append(name)
    order = []
    for name in current_order:
        order.extend(before.get(name, ()))
        order.append(name)
    order.extend(pending)
    for fragment in fragments[1:]:
        retained = [name for name in fragment if name in selected]
        if retained != [name for name in order if name in fragment]:
            raise _UnsupportedPropertyMerge("property_order_conflict")
    return layouts[1][0] + b"".join(selected[name] for name in order) + layouts[1][1]


def _raise_merge_blockers(blockers):
    if not blockers:
        return
    details = {
        "blocking_scopes": blockers[:_MAX_MERGE_EVIDENCE],
        "blocking_scope_count": len(blockers),
    }
    if len(blockers) > _MAX_MERGE_EVIDENCE:
        details["scopes_truncated"] = True
    raise CoreError(
        "THREE_WAY_CONFLICT",
        "Metadata merge has unresolved or unsupported scopes",
        details=details,
    )


def materialize_metadata_three_way(
    base,
    current,
    upstream,
    *,
    max_files=10_000,
    max_file_bytes=16 * 1024 * 1024,
    max_total_bytes=64 * 1024 * 1024,
):
    """Return a qualified in-memory candidate; never expose a partial merge.

    Only disjoint direct Designer Properties may resolve an object conflict.
    Other objects and recognized companions remain atomic; unsupported scopes
    fail closed. All planning and selection use the same validated snapshots.
    """
    limits = dict(
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    snapshots = _prepare_trees(base, current, upstream, **limits)
    plan, path_plan, trees, records = _metadata_plan(snapshots, max_files=max_files)
    blockers, merged, covered_paths = [], [], set()
    owners = {}
    for label, tree in trees.items():
        by_path = {value["path"]: key for key, value in records[label].items()}
        for path in tree:
            owners.setdefault(path, set()).add(by_path.get(path))
        for value in records[label].values():
            if not _materialization_shape(value):
                blockers.append(
                    {"path": value["path"], "reason": "object_shape_unsupported"}
                )
        for path, raw in tree.items():
            if path not in by_path and path.lower().endswith(".xml"):
                if ET.fromstring(raw).tag.rsplit("}", 1)[-1] == _ROOT:
                    blockers.append(
                        {"path": path, "reason": "object_shape_unsupported"}
                    )
    for path, bindings in owners.items():
        if len(bindings) > 1:
            blockers.append({"path": path, "reason": "object_identity_changed"})
    for row in plan["semantics"]["scopes"]:
        if row["status"] != "supported":
            blockers.append(
                {
                    "object_uuid": row["object_uuid"],
                    "scope": row["scope"],
                    "reason": row["reason"],
                }
            )
    for row in plan["objects"]:
        if row["action"] != "conflict":
            continue
        key = (row["object_type"], row["object_uuid"])
        values = [records[label].get(key) for label in trees]
        paths = [row[label + "_path"] for label in trees]
        path_action = _action(*paths)
        if (
            row["property_mergeability"] != "disjoint_changes"
            or _unscoped_action(values) != "unchanged"
            or path_action == "conflict"
            or not all(_materialization_shape(value) for value in values)
        ):
            blockers.append({"object_uuid": key[1], "reason": "object_conflict"})
            continue
        try:
            raw = _merge_properties(values)
        except _UnsupportedPropertyMerge as exc:
            blockers.append({"object_uuid": key[1], "reason": str(exc)})
            continue
        source = _SOURCE_BY_ACTION[path_action]
        path = row[source + "_path"]
        merged.append((key, path, raw))
        covered_paths.update(paths)
    for row in path_plan["changes"]:
        if row["action"] == "conflict" and row["path"] not in covered_paths:
            blockers.append({"path": row["path"], "reason": "path_conflict"})
    _raise_merge_blockers(blockers)

    candidate = {}
    for row in path_plan["changes"]:
        path = row["path"]
        if path in covered_paths:
            continue
        source = trees[_SOURCE_BY_ACTION[row["action"]]]
        if path in source:
            candidate[path] = source[path]
    for key, path, raw in merged:
        candidate[path] = raw
    normalized = _tree(candidate, "candidate", **limits)
    candidate_records, _ = _records(candidate, "candidate")
    for key, scope in _semantic_records(candidate, candidate_records).items():
        if scope["reason"]:
            blockers.append({"path": scope["path"], "reason": scope["reason"]})
    _raise_merge_blockers(blockers)
    evidence = [
        {
            "object_type": key[0],
            "object_uuid": key[1],
            "candidate_path": path,
            "candidate_sha256": sha256(raw),
            "candidate_size_bytes": len(raw),
        }
        for key, path, raw in merged[:_MAX_MERGE_EVIDENCE]
    ]
    return {
        "schema": 1,
        "scope": "metadata-properties-v1",
        "status": "ready",
        "base_digest": plan["base_digest"],
        "current_digest": plan["current_digest"],
        "upstream_digest": plan["upstream_digest"],
        "candidate_digest": _tree_digest(normalized),
        "candidate": candidate,
        "counts": {
            "objects": len(plan["objects"]),
            "merged_objects": len(merged),
            "candidate_files": len(candidate),
            "path_actions": path_plan["counts"],
        },
        "merged_objects": evidence,
        "merged_objects_truncated": len(merged) > _MAX_MERGE_EVIDENCE,
    }
