"""Bounded runtime files and snapshot-only EDT metadata identity inventories."""
from dataclasses import asdict, dataclass
import hashlib
import os
from pathlib import Path
import re

from ._windows_source_tree import WindowsHandleOps, _retained_stamp, pinned_directory
from .errors import CoreError
from .metadata import (
    FOLDER_TO_TYPE,
    MetadataLimits,
    _attach_refs,
    _candidate,
    _local,
    _operation,
)
from .source_paths import validate_inventory_paths

MAX_FILES, MAX_TOTAL, MAX_FILE = 8192, 4 * 1024**3, 256 * 1024**2
BOOT = (
    "configuration/config.ini",
    "configuration/org.eclipse.equinox.simpleconfigurator/bundles.info",
)

_EDT_NAMESPACE = "http://g5.1c.ru/v8/dt/metadata/mdclass"
_EDT_METADATA_NAMESPACE = "http://v8.1c.ru/8.3/MDClasses"
_EDT_CHILDREN = {
    "attributes": "Attribute",
    "tabularSections": "TabularSection",
    "dimensions": "Dimension",
    "resources": "Resource",
    "forms": "Form",
    "commands": "Command",
    "enumValues": "EnumValue",
}
_EDT_XML_CHILDREN = {
    "Attribute": "Attribute",
    "TabularSection": "TabularSection",
    "Dimension": "Dimension",
    "Resource": "Resource",
    "Form": "Form",
    "Command": "Command",
    "EnumValue": "EnumValue",
}
_EDT_XML_SEPARATE = {"Forms": "Form", "Commands": "Command"}


@dataclass(frozen=True)
class EDTInventoryLimits(MetadataLimits):
    """Additional whole-operation budgets; inherited XML/read caps still apply."""

    max_mdo_files: int = 2048
    max_identities: int = 20_000

    def __post_init__(self):
        super().__post_init__()
        if any(
            type(value) is not int or not 1 <= value <= maximum
            for value, maximum in (
                (self.max_mdo_files, 2048),
                (self.max_identities, 20_000),
            )
        ):
            raise CoreError("INVALID_QUERY_OPTIONS", "EDT limits must be bounded")


def _identity_error(code, message, ref):
    return CoreError(code, message, details={"source_ref": ref})


def _edt_identity(node, kind, xml_path, owner, layer, ref):
    observed = node.attrib.get("uuid", "")
    names = [child for child in node if _local(child.tag) == "name"]
    name = (names[0].text or "") if len(names) == 1 else ""
    if (
        not re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", observed
        )
        or observed == "00000000-0000-0000-0000-000000000000"
        or len(names) != 1
        or len(names[0])
        or names[0].tag not in ("name", "{" + _EDT_NAMESPACE + "}name")
        or not 1 <= len(name) <= 256
        or not re.fullmatch(r"[^\W\d]\w*", name)
    ):
        raise _identity_error("EDT_IDENTITY_INVALID", "Invalid EDT UUID or name", ref)
    return {
        "canonical_uuid": observed.lower(),
        "observed_uuid": observed,
        "type": kind,
        "name": name,
        "xml_path": xml_path,
        "owner": owner,
        "layer": asdict(layer),
        "source_ref": ref,
    }


def _edt_objects(root, kind, entry, layer, reader, objects, seen):
    ref = asdict(entry.ref)
    if root.tag != "{" + _EDT_NAMESPACE + "}" + kind:
        raise _identity_error(
            "EDT_INVENTORY_UNSUPPORTED", "EDT root does not match path/type", ref
        )
    pending = [(root, kind, "/" + kind, None)]
    sibling_names = set()
    while pending:
        reader.session.checkpoint()
        node, node_kind, xml_path, owner = pending.pop()
        if len(objects) >= reader.limits.max_identities:
            raise CoreError("METADATA_LIMIT_EXCEEDED", "EDT identity limit exceeded")
        row = _edt_identity(node, node_kind, xml_path, owner, layer, ref)
        if node is root and kind != "Configuration":
            if row["name"] != entry.ref.relative_path.split("/")[1]:
                raise _identity_error(
                    "EDT_IDENTITY_INVALID", "EDT name does not match object path", ref
                )
        key = (layer.layer_id, row["canonical_uuid"])
        if key in seen:
            raise _identity_error(
                "EDT_IDENTITY_DUPLICATE", "Duplicate EDT UUID in selected layer", ref
            )
        seen.add(key)
        name_key = (
            owner["canonical_uuid"] if owner else None,
            node_kind,
            row["name"].casefold(),
        )
        if name_key in sibling_names:
            raise _identity_error(
                "EDT_IDENTITY_DUPLICATE", "Ambiguous EDT name under one owner", ref
            )
        sibling_names.add(name_key)
        objects.append(row)
        parent = {
            "canonical_uuid": row["canonical_uuid"],
            "source_ref": ref,
            "xml_path": xml_path,
        }
        children = []
        for index, child in enumerate(node):
            tag = _local(child.tag)
            if tag in _EDT_CHILDREN:
                if child.tag not in (tag, "{" + _EDT_NAMESPACE + "}" + tag) or (
                    node is not root
                    and not (node_kind == "TabularSection" and tag == "attributes")
                ):
                    raise _identity_error(
                        "EDT_INVENTORY_UNSUPPORTED",
                        "Unsupported EDT child namespace or owner",
                        ref,
                    )
                children.append(
                    (child, _EDT_CHILDREN[tag], f"{xml_path}/{tag}[{index}]", parent)
                )
            elif any(
                _local(attribute) == "uuid"
                for element in child.iter()
                for attribute in element.attrib
            ):
                raise _identity_error(
                    "EDT_INVENTORY_UNSUPPORTED",
                    "Unknown or indirect EDT identity declaration",
                    ref,
                )
        pending.extend(reversed(children))


def _edt_xml_candidate(path):
    """Return an actual EDT MetaDataObject kind and optional path owner.

    EDT stores metadata descriptors as ``MetaDataObject`` XML files.  Forms and
    commands of an object live below ``<owner>/Forms`` or ``<owner>/Commands``
    and therefore cannot be recognized by the Designer-style path helper.
    The returned owner path is only a locator; it is resolved to a verified
    identity before it is exposed in an inventory row.
    """
    if not isinstance(path, str) or not path.endswith(".xml"):
        return None
    kind = _candidate(path)
    if kind is not None:
        return kind, None
    parts = path.split("/")
    if (
        len(parts) == 4
        and parts[0] in FOLDER_TO_TYPE
        and parts[2] in _EDT_XML_SEPARATE
        and parts[3].endswith(".xml")
        and parts[3][:-4]
    ):
        return _EDT_XML_SEPARATE[parts[2]], "/".join(parts[:2]) + ".xml"
    return None


def _edt_xml_identity(node, kind, xml_path, owner, layer, ref):
    """Read one identity from an EDT ``MetaDataObject`` XML element."""
    if node.tag != "{" + _EDT_METADATA_NAMESPACE + "}" + kind:
        raise _identity_error(
            "EDT_INVENTORY_UNSUPPORTED",
            "EDT XML root or child type does not match path/type",
            ref,
        )
    if set(node.attrib) != {"uuid"}:
        raise _identity_error(
            "EDT_IDENTITY_INVALID", "Invalid EDT XML identity attributes", ref
        )
    properties = [child for child in node if _local(child.tag) == "Properties"]
    if (
        len(properties) != 1
        or properties[0].tag != "{" + _EDT_METADATA_NAMESPACE + "}Properties"
    ):
        raise _identity_error(
            "EDT_IDENTITY_INVALID", "EDT XML identity properties are invalid", ref
        )
    if any("uuid" in item.attrib for item in properties[0].iter()):
        raise _identity_error(
            "EDT_INVENTORY_UNSUPPORTED",
            "Unexpected UUID in EDT XML identity properties",
            ref,
        )
    names = [child for child in properties[0] if _local(child.tag) == "Name"]
    if (
        len(names) != 1
        or names[0].tag != "{" + _EDT_METADATA_NAMESPACE + "}Name"
        or len(names[0])
    ):
        raise _identity_error(
            "EDT_IDENTITY_INVALID", "EDT XML identity name is invalid", ref
        )
    observed = node.attrib["uuid"]
    name = names[0].text or ""
    if (
        not re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", observed
        )
        or observed == "00000000-0000-0000-0000-000000000000"
        or not 1 <= len(name) <= 256
        or not re.fullmatch(r"[^\W\d]\w*", name)
    ):
        raise _identity_error(
            "EDT_IDENTITY_INVALID", "Invalid EDT XML UUID or name", ref
        )
    return {
        "canonical_uuid": observed.lower(),
        "observed_uuid": observed,
        "type": kind,
        "name": name,
        "xml_path": xml_path,
        "owner": owner,
        "layer": asdict(layer),
        "source_ref": ref,
    }


def _edt_xml_objects(
    root,
    kind,
    entry,
    layer,
    reader,
    objects,
    seen,
    names,
    owner=None,
):
    """Parse one real EDT ``MetaDataObject`` and its direct child identities."""
    ref = asdict(entry.ref)
    if root.tag != "{" + _EDT_METADATA_NAMESPACE + "}MetaDataObject":
        raise _identity_error(
            "EDT_INVENTORY_UNSUPPORTED", "EDT XML metadata wrapper is unsupported", ref
        )
    if "uuid" in root.attrib:
        raise _identity_error(
            "EDT_INVENTORY_UNSUPPORTED",
            "Unexpected UUID on EDT XML metadata wrapper",
            ref,
        )
    children = list(root)
    if len(children) != 1 or _local(children[0].tag) != kind:
        raise _identity_error(
            "EDT_INVENTORY_UNSUPPORTED",
            "EDT XML metadata root does not match path/type",
            ref,
        )
    allowed = {"InternalInfo", "Properties", "ChildObjects"}
    for child in children[0]:
        tag = _local(child.tag)
        if tag not in allowed and any("uuid" in item.attrib for item in child.iter()):
            raise _identity_error(
                "EDT_INVENTORY_UNSUPPORTED",
                "Unknown EDT XML identity container",
                ref,
            )
        if tag in allowed and child.tag != "{" + _EDT_METADATA_NAMESPACE + "}" + tag:
            raise _identity_error(
                "EDT_INVENTORY_UNSUPPORTED",
                "EDT XML structural namespace is unsupported",
                ref,
            )
        if tag in {"InternalInfo", "Properties"} and any(
            "uuid" in item.attrib for item in child.iter()
        ):
            raise _identity_error(
                "EDT_INVENTORY_UNSUPPORTED",
                "Unexpected UUID in EDT XML structural data",
                ref,
            )
    row = _edt_xml_identity(children[0], kind, "/" + kind, owner, layer, ref)
    expected = entry.ref.relative_path.removesuffix(".xml").split("/")[-1]
    if row["name"] != expected and kind != "Configuration":
        raise _identity_error(
            "EDT_IDENTITY_INVALID", "EDT XML name does not match path", ref
        )
    key = (layer.layer_id, row["canonical_uuid"])
    if key in seen:
        raise _identity_error(
            "EDT_IDENTITY_DUPLICATE", "Duplicate EDT UUID in selected layer", ref
        )
    name_key = (
        owner["canonical_uuid"] if owner else None,
        kind,
        row["name"].casefold(),
    )
    if name_key in names:
        raise _identity_error(
            "EDT_IDENTITY_DUPLICATE", "Ambiguous EDT name under one owner", ref
        )
    seen.add(key)
    names.add(name_key)
    objects.append(row)
    parent = {
        "canonical_uuid": row["canonical_uuid"],
        "source_ref": ref,
        "xml_path": "/" + kind,
    }
    child_groups = [
        child for child in children[0] if _local(child.tag) == "ChildObjects"
    ]
    if len(child_groups) > 1 or any(
        child.tag != "{" + _EDT_METADATA_NAMESPACE + "}ChildObjects"
        for child in child_groups
    ):
        raise _identity_error(
            "EDT_INVENTORY_UNSUPPORTED", "EDT XML child container is unsupported", ref
        )
    for group in child_groups:
        for index, child in enumerate(group):
            tag = _local(child.tag)
            child_kind = _EDT_XML_CHILDREN.get(tag)
            has_uuid = "uuid" in child.attrib
            if child_kind is None:
                if has_uuid or any("uuid" in item.attrib for item in child.iter()):
                    raise _identity_error(
                        "EDT_INVENTORY_UNSUPPORTED",
                        "Unknown EDT XML identity declaration",
                        ref,
                    )
                continue
            if not has_uuid:
                # A form/command reference in the parent descriptor is not an
                # identity; its dedicated MetaDataObject is inventoried below.
                if any("uuid" in item.attrib for item in child.iter()):
                    raise _identity_error(
                        "EDT_INVENTORY_UNSUPPORTED",
                        "EDT XML identity declaration is incomplete",
                        ref,
                    )
                continue
            child_row = _edt_xml_identity(
                child,
                child_kind,
                f"/{kind}/ChildObjects/{tag}[{index}]",
                parent,
                layer,
                ref,
            )
            child_key = (layer.layer_id, child_row["canonical_uuid"])
            child_name_key = (
                parent["canonical_uuid"],
                child_kind,
                child_row["name"].casefold(),
            )
            if child_key in seen or child_name_key in names:
                raise _identity_error(
                    "EDT_IDENTITY_DUPLICATE", "Duplicate EDT child identity", ref
                )
            seen.add(child_key)
            names.add(child_name_key)
            objects.append(child_row)


def _edt_metadata_inventory_impl(ctx, *, layer_id=None, limits=EDTInventoryLimits()):
    """Verify root/embedded identities without inferring extension or asset owners.

    The caller selects declared snapshot layers; UUID uniqueness is layer-local.
    Unknown metadata paths or identity-bearing declarations fail closed. Other
    assets remain outside this identity profile, even when a filename suggests an
    owner. Actual EDT ``MetaDataObject`` XML uses profile v2; legacy compact MDO
    files retain profile v1 for compatibility.
    """
    if not isinstance(limits, EDTInventoryLimits):
        raise CoreError("INVALID_QUERY_OPTIONS", "Typed EDT inventory limits required")
    with _operation(ctx, layer_id, limits) as (reader, layers):
        entries = reader.session.entries()
        if len(entries) > limits.max_inventory:
            raise CoreError("METADATA_LIMIT_EXCEEDED", "EDT inventory limit exceeded")
        objects, layer_rows, seen, names, mdo_count = [], [], set(), set(), 0
        xml_profile = False
        profiles = set()
        for layer in layers:
            reader.session.checkpoint()
            if layer.source_format != "edt":
                raise CoreError(
                    "EDT_INVENTORY_UNSUPPORTED",
                    "Explicit EDT layer declaration required",
                )
            selected = sorted(
                (entry for entry in entries if entry.ref.layer_id == layer.layer_id),
                key=lambda entry: entry.ref.relative_path.encode("utf-8"),
            )
            parsed = 0
            layer_profile = None
            root_rows = {}
            deferred = []
            for entry in selected:
                reader.session.checkpoint()
                path = entry.ref.relative_path
                is_mdo = path.lower().endswith(".mdo")
                candidate = (
                    _edt_xml_candidate(path) if path.lower().endswith(".xml") else None
                )
                if is_mdo or candidate is not None:
                    if is_mdo:
                        kind = _candidate(path)
                        profile = "mdo"
                    else:
                        kind, owner_path = candidate
                        profile = "xml"
                    if kind is None:
                        raise _identity_error(
                            "EDT_INVENTORY_UNSUPPORTED",
                            "Unknown EDT path or mixed Designer candidate",
                            asdict(entry.ref),
                        )
                    if layer_profile is not None and layer_profile != profile:
                        raise _identity_error(
                            "EDT_INVENTORY_UNSUPPORTED",
                            "Mixed legacy MDO and MetaDataObject XML is unsupported",
                            asdict(entry.ref),
                        )
                    layer_profile = profile
                    mdo_count += 1
                    if mdo_count > limits.max_mdo_files:
                        raise CoreError(
                            "METADATA_LIMIT_EXCEEDED", "EDT document limit exceeded"
                        )
                    root = reader.xml(entry)
                    start = len(objects)
                    if profile == "mdo":
                        _edt_objects(root, kind, entry, layer, reader, objects, seen)
                    elif owner_path is not None:
                        deferred.append((entry, kind, owner_path, root))
                    else:
                        _edt_xml_objects(
                            root,
                            kind,
                            entry,
                            layer,
                            reader,
                            objects,
                            seen,
                            names,
                        )
                        root_rows[path] = objects[start]
                        xml_profile = True
                    parsed += 1
            if layer_profile == "xml":
                profiles.add(layer_profile)
                for entry, kind, owner_path, root in deferred:
                    owner = root_rows.get(owner_path)
                    if owner is None:
                        raise _identity_error(
                            "EDT_INVENTORY_UNSUPPORTED",
                            "EDT child metadata owner is not inventoried",
                            asdict(entry.ref),
                        )
                    owner_identity = {
                        key: owner[key]
                        for key in ("canonical_uuid", "source_ref", "xml_path")
                    }
                    _edt_xml_objects(
                        root,
                        kind,
                        entry,
                        layer,
                        reader,
                        objects,
                        seen,
                        names,
                        owner=owner_identity,
                    )
            elif layer_profile == "mdo":
                profiles.add(layer_profile)
            if len(profiles) > 1:
                raise CoreError(
                    "EDT_INVENTORY_UNSUPPORTED",
                    "Mixed legacy MDO and MetaDataObject XML layers are unsupported",
                )
            layer_rows.append(
                {
                    **asdict(layer),
                    "parsed_mdo_files": parsed,
                    "unparsed_files": len(selected) - parsed,
                    "count_basis": "verified_manifest_paths",
                }
            )
        result = {
            "snapshot": asdict(ctx.snapshot),
            "parser": "edt_identity_v2" if xml_profile else "edt_identity_v1",
            "identity_scope": "snapshot_layer",
            "coverage": "partial",
            "owner_basis": (
                "direct_xml_containment_and_verified_path_owner"
                if xml_profile
                else "direct_xml_containment_only"
            ),
            "layer_basis": "pinned_snapshot_declaration",
            "layers": layer_rows,
            "objects": objects,
        }
        _attach_refs(reader, result)
    result["validation_summary"] = {"generation": reader.session.validation_summary}
    return result


def edt_metadata_inventory(ctx, *, layer_id=None, limits=EDTInventoryLimits()):
    """Return a bounded, read-only EDT identity inventory for one snapshot.

    A final project permission check wraps the complete operation. This keeps
    source references out of an identity/parser error when membership is
    revoked after a source read but before the result is emitted.
    """
    try:
        return _edt_metadata_inventory_impl(ctx, layer_id=layer_id, limits=limits)
    except BaseException:
        if ctx is not None:
            with ctx.state.transaction(ctx.principal) as tx:
                tx.require_all({"project:read"})
        raise


def inventory(root, *, java=False, authorize=lambda: None, hashes=True):
    starts = ("bin", "lib", "conf", "release") if java else ("plugins", *BOOT)
    return _inventory(root, starts, authorize=authorize, hashes=hashes)


def exported_inventory(root, *, authorize):
    """Bounded complete export inventory, including unknown files."""
    return _inventory(root, (".",), authorize=authorize, hashes=True)


def _inventory(root, starts, *, authorize, hashes):
    root = Path(root)
    todo = [root / p for p in starts]
    rows, total, visited = [], 0, 0
    ops = WindowsHandleOps()
    with pinned_directory(root):
        while todo:
            authorize()
            path = todo.pop()
            visited += 1
            if visited > MAX_FILES * 2 or len(path.relative_to(root).parts) > 32:
                raise CoreError("EDT_RUNTIME_LIMIT", "Runtime tree exceeds limits")
            stamp = path.stat(follow_symlinks=False)
            if path.is_symlink() or getattr(stamp, "st_file_attributes", 0) & 0x400:
                raise CoreError(
                    "EDT_RUNTIME_INVALID", "Runtime links are not supported"
                )
            if path.is_dir():
                with pinned_directory(path), os.scandir(path) as children:
                    for child in children:
                        todo.append(Path(child.path))
                        if len(todo) + visited > MAX_FILES * 2:
                            raise CoreError(
                                "EDT_RUNTIME_LIMIT", "Too many runtime entries"
                            )
                continue
            handle = ops.open(path, directory=False)
            try:
                info = _retained_stamp(ops, handle)
                if info.directory or ops.final_path(handle) != path:
                    raise CoreError("EDT_RUNTIME_INVALID", "Invalid runtime file")
                total += info.size
                if len(rows) >= MAX_FILES or info.size > MAX_FILE or total > MAX_TOTAL:
                    raise CoreError(
                        "EDT_RUNTIME_LIMIT", "Runtime input volume exceeds limits"
                    )
                row = {"path": path.relative_to(root).as_posix(), "size": info.size}
                if hashes:
                    digest = hashlib.sha256()
                    for chunk in ops.chunks(handle):
                        digest.update(chunk)
                    row["sha256"] = digest.hexdigest()
                rows.append(row)
            finally:
                ops.close(handle)
        authorize()
    validate_inventory_paths(row["path"] for row in rows)
    return sorted(rows, key=lambda row: row["path"])
