"""Read-only direct EDT Catalog attribute evidence over selected byte trees."""

import io
import re
import xml.etree.ElementTree as ET

from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .source_paths import collision_key
from .three_way import _action, _plan_from_trees, _prepare_trees


_NS = "http://g5.1c.ru/v8/dt/metadata/mdclass"
_UUID = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\Z")
_UNSAFE = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_IDENTITIES = {"attributes", "forms", "commands", "tabularSections"}
_LABELS = ("base", "current", "upstream")


def _reject(reason, *, limit=False):
    raise CoreError(
        "EDT_THREE_WAY_LIMIT" if limit else "EDT_THREE_WAY_INVALID",
        "Selected EDT Catalog attribute projection was rejected",
        details={"reason": reason},
    )


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _qualified(node):
    if node.tag not in (_local(node.tag), "{" + _NS + "}" + _local(node.tag)):
        _reject("namespace_unsupported")


def _identity(node):
    _qualified(node)
    identity = node.get("uuid", "")
    names = [child for child in node if _local(child.tag) == "name"]
    if len(names) > 1:
        _reject("property_ambiguous")
    if names:
        _qualified(names[0])
    name = names[0].text or "" if names else ""
    if (
        not _UUID.fullmatch(identity)
        or identity == "00000000-0000-0000-0000-000000000000"
        or not names
        or len(names[0])
        or not 1 <= len(name) <= 256
        or not re.fullmatch(r"[^\W\d]\w*", name)
        or set(node.attrib) != {"uuid"}
    ):
        _reject("identity_invalid")
    return identity.lower(), name


def _projection(node):
    # Expanded XML names and sorted attributes avoid global serializer state.
    # Tail is outside the selected element; source hashes retain the full bytes.
    return [
        node.tag,
        [[name, value] for name, value in sorted(node.attrib.items())],
        node.text,
        [[_projection(child), child.tail] for child in node],
    ]


def _fingerprint(node, namespaces):
    raw = canonical_bytes([namespaces, _projection(node)])
    return {"sha256": sha256(raw), "size_bytes": len(raw)}


def _parse(raw):
    if _UNSAFE.search(raw.replace(b"\x00", b"")):
        _reject("xml_declaration_forbidden")
    depth, count, pending, namespaces = 0, 0, [], []
    try:
        parser = ET.iterparse(
            io.BytesIO(raw), events=("start", "end", "start-ns", "comment", "pi")
        )
        for event, node in parser:
            if event in {"comment", "pi"}:
                _reject("xml_misc_unsupported")
            if event == "start-ns":
                pending.append(list(node))
            elif event == "start":
                depth += 1
                count += 1
                if depth > 64 or count > 100_000:
                    _reject("xml_limit", limit=True)
                if pending:
                    namespaces.append([count, sorted(pending)])
                    pending = []
            elif event == "end":
                depth -= 1
        root = parser.root
    except (ET.ParseError, ValueError, UnicodeError, LookupError):
        _reject("xml_invalid")
    if root.tag != "{" + _NS + "}Catalog":
        _reject("namespace_unsupported")
    # Include declaration positions so QName-valued text cannot conceal a
    # changed or locally rebound prefix. This is deliberately conservative:
    # even an unused declaration change affects every projected property.
    return root, sha256(canonical_bytes(namespaces))


def _validate_identities(root, seen):
    """Validate containment, including excluded form/command/tabular identities."""
    pending = [(root, None)]
    sibling_names = set()
    while pending:
        node, parent = pending.pop()
        identity, name = _identity(node)
        key = (
            None if parent is None else parent.get("uuid").lower(),
            _local(node.tag),
            name.casefold(),
        )
        if identity in seen or key in sibling_names:
            _reject("identity_duplicate")
        seen.add(identity)
        sibling_names.add(key)
        for child in node:
            tag = _local(child.tag)
            _qualified(child)
            if tag in _IDENTITIES:
                if node is not root and not (
                    _local(node.tag) == "tabularSections" and tag == "attributes"
                ):
                    _reject("nested_identity_unsupported")
                pending.append((child, node))
            elif any(
                _local(attr) == "uuid" for item in child.iter() for attr in item.attrib
            ):
                _reject(
                    "nested_identity_unsupported"
                    if node is not root
                    else "identity_shape_unsupported"
                )
            elif tag.casefold() in {
                "objectbelonging",
                "extendedconfigurationobject",
                "configurationextensionpurpose",
                "adoptedobject",
            }:
                _reject("identity_shape_unsupported")


def _properties(node, namespaces):
    if node.text and node.text.strip():
        _reject("mixed_content_unsupported")
    result = {}
    if len(node) > 128:
        _reject("property_limit", limit=True)
    for child in node:
        _qualified(child)
        name = _local(child.tag)
        if name in result:
            _reject("property_ambiguous")
        if child.tail and child.tail.strip():
            _reject("mixed_content_unsupported")
        result[name] = _fingerprint(child, namespaces)
    return result


def _records(tree, max_children):
    children, owners, seen = {}, {}, set()
    for path, raw in sorted(tree.values()):
        parts = path.split("/")
        if len(parts) != 3 or parts[0] != "Catalogs" or parts[2] != parts[1] + ".mdo":
            _reject("path_unsupported")
        root, namespaces = _parse(raw)
        owner_uuid, owner_name = _identity(root)
        if owner_name != parts[1]:
            _reject("path_name_mismatch")
        _validate_identities(root, seen)
        owner = {"type": "Catalog", "uuid": owner_uuid, "path": path}
        owners[owner_uuid] = owner
        source = {"source_sha256": sha256(raw), "source_size_bytes": len(raw)}
        for index, node in enumerate(root):
            if _local(node.tag) != "attributes":
                continue
            if len(children) >= max_children:
                _reject("child_limit", limit=True)
            identity, name = _identity(node)
            children[identity] = {
                "name": name,
                "owner": owner,
                "xml_path": f"/Catalog/attributes[{index}]",
                **_fingerprint(node, namespaces),
                **source,
                "properties": _properties(node, namespaces),
            }
    return children, owners


def _property_changes(values):
    if any(value is None for value in values):
        return "not_available", []
    properties = [value["properties"] for value in values]
    rows, actions = [], set()
    for name in sorted(set().union(*properties)):
        fingerprints = [version.get(name) for version in properties]
        action = _action(*fingerprints)
        if action == "unchanged":
            continue
        row = {"property_name": name, "action": action}
        for label, value in zip(_LABELS, fingerprints):
            row[label + "_sha256"] = None if value is None else value["sha256"]
            row[label + "_size_bytes"] = None if value is None else value["size_bytes"]
        rows.append(row)
        actions.add(action)
    if "conflict" in actions:
        return "overlap_conflict", rows
    if {"keep_current", "take_upstream"} <= actions:
        return "disjoint_changes", rows
    if not actions:
        return "unchanged", rows
    return next(iter(actions)) if len(actions) == 1 else "mixed_changes", rows


def plan_edt_attribute_three_way(
    base,
    current,
    upstream,
    *,
    max_files=256,
    max_file_bytes=1024 * 1024,
    max_total_bytes=16 * 1024 * 1024,
    max_children=20_000,
):
    """Compare direct attributes of explicitly selected EDT Catalog descriptors.

    Inputs contain only Catalogs/<name>/<name>.mdo byte entries. Identity and
    property fingerprints describe a structural XML projection, not a native
    schema validation or merge. The exact source bytes have separate digests.
    """
    for value, maximum in (
        (max_files, 256),
        (max_file_bytes, 1024 * 1024),
        (max_total_bytes, 16 * 1024 * 1024),
        (max_children, 20_000),
    ):
        if type(value) is not int or not 1 <= value <= maximum:
            _reject("limits_invalid", limit=True)
    snapshots = _prepare_trees(
        base,
        current,
        upstream,
        max_files=max_files,
        max_file_bytes=max_file_bytes,
        max_total_bytes=max_total_bytes,
    )
    path_plan = _plan_from_trees(snapshots, max_files=max_files)
    records = [_records(tree, max_children) for tree in snapshots.values()]
    path_owners = {}
    for _, owners in records:
        for identity, owner in owners.items():
            path_owners.setdefault(collision_key(owner["path"]), set()).add(identity)
    if any(len(identities) > 1 for identities in path_owners.values()):
        _reject("owner_identity_changed")
    identities = set().union(*(children for children, _ in records))
    if len(identities) > max_children:
        _reject("child_limit", limit=True)
    rows = []
    for identity in sorted(identities):
        values = [children.get(identity) for children, _ in records]
        owner_ids = {value["owner"]["uuid"] for value in values if value is not None}
        if len(owner_ids) != 1:
            _reject("owner_changed")
        owner_uuid = next(iter(owner_ids))
        if any(owner_uuid not in owners for _, owners in records):
            _reject("owner_missing")
        owner_paths = [owners[owner_uuid]["path"] for _, owners in records]
        if _action(*owner_paths) == "conflict":
            _reject("owner_path_conflict")
        mergeability, properties = _property_changes(values)
        fingerprints = [None if value is None else value["sha256"] for value in values]
        if mergeability == "unchanged" and _action(*fingerprints) != "unchanged":
            mergeability = "unscoped_content"
        row = {
            "child_type": "Attribute",
            "child_uuid": identity,
            "action": _action(*fingerprints),
            "property_mergeability": mergeability,
            "property_changes": properties,
        }
        for label, value in zip(_LABELS, values):
            row[label] = (
                None
                if value is None
                else {key: item for key, item in value.items() if key != "properties"}
            )
        rows.append(row)
    return {
        "schema": 1,
        "scope": "edt-catalog-attributes-v1",
        "mode": "read_only",
        "coverage": "partial",
        "fingerprint_basis": "structural_xml_json_v1",
        "owner_basis": "direct_xml_containment_only",
        "child_objects": rows,
        **{label + "_digest": path_plan[label + "_digest"] for label in _LABELS},
    }
