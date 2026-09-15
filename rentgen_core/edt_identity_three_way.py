"""Pure bounded identity evidence over EDT producer inventories, never a merge."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType

from .context import SnapshotRef
from .errors import CoreError
from .metadata import FOLDER_TO_TYPE
from .snapshots import SnapshotLayer
from .source_paths import validate_file_paths
from .three_way import _action

_CEILINGS = {
    "max_input_bytes": 8 * 1024**2,
    "max_objects": 20_000,
    "max_owners": 20_000,
    "max_layers": 64,
    "max_rows": 20_000,
}
_OUTPUT_LIMIT = 8 * 1024**2
_ACTIONS = (
    "unchanged",
    "same_change",
    "keep_current",
    "take_upstream",
    "conflict",
    "unsupported",
)
_CHILDREN = {
    "Attribute": "attributes",
    "TabularSection": "tabularSections",
    "Dimension": "dimensions",
    "Resource": "resources",
    "Form": "forms",
    "Command": "commands",
    "EnumValue": "enumValues",
}
_XML_CHILDREN = {
    "Attribute": "Attribute",
    "TabularSection": "TabularSection",
    "Dimension": "Dimension",
    "Resource": "Resource",
    "Form": "Form",
    "Command": "Command",
    "EnumValue": "EnumValue",
}
_LAYER_FIELDS = {
    "layer_id",
    "ordinal",
    "kind",
    "configuration_uuid",
    "identity_status",
    "source_format",
}
_SOURCE_LAYER_FIELDS = {
    "layer_id",
    "ordinal",
    "kind",
    "root_relative_path",
    "source_format",
}
_SNAPSHOT_FIELDS = {"project_id", "snapshot_id", "manifest_hash"}
_OBJECT_FIELDS = {
    "canonical_uuid",
    "observed_uuid",
    "type",
    "name",
    "xml_path",
    "owner",
    "layer",
    "source_ref",
}
_GENERATION_COUNTS = {
    "verified_source_files",
    "verified_derived_files",
    "verified_source_bytes",
    "verified_total_bytes",
}


@dataclass(frozen=True)
class EDTIdentityThreeWayLimits:
    max_input_bytes: int = 8 * 1024**2
    max_objects: int = 20_000
    max_owners: int = 20_000
    max_layers: int = 64
    max_rows: int = 20_000

    def __post_init__(self):
        if any(
            type(value) is not int or not 1 <= value <= _CEILINGS[name]
            for name, value in asdict(self).items()
        ):
            raise CoreError(
                "INVALID_QUERY_OPTIONS",
                "Identity plan limits must be positive and bounded",
            )


def _invalid():
    return CoreError("EDT_IDENTITY_PLAN_INVALID", "EDT identity inventory is invalid")


def _limit():
    raise CoreError("EDT_IDENTITY_PLAN_LIMIT", "EDT identity plan exceeds its limits")


def _canonical(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _capture(value, maximum, memo, active, depth=0):
    """Copy each caller container once; aliases reuse captured, private values."""
    if depth > 32:
        raise _invalid()
    if type(value) in (str, int, bool) or value is None:
        size = len(_canonical(value))
        result = value
    elif isinstance(value, Mapping) or type(value) is list:
        identity = id(value)
        if identity in active:
            raise _invalid()
        if identity in memo:
            _, result, size = memo[identity]
            return result, size
        active.add(identity)
        size = 2
        if isinstance(value, Mapping):
            result = {}
            for key, child in value.items():
                if type(key) is not str or key in result:
                    raise _invalid()
                copied, child_size = _capture(child, maximum, memo, active, depth + 1)
                size += len(_canonical(key)) + child_size + 1 + bool(result)
                if size > maximum:
                    _limit()
                result[key] = copied
        else:
            result = []
            for child in value:
                copied, child_size = _capture(child, maximum, memo, active, depth + 1)
                size += child_size + bool(result)
                if size > maximum:
                    _limit()
                result.append(copied)
        active.remove(identity)
        # Keep caller containers alive: dynamic mappings can otherwise recycle
        # an ephemeral child's id and falsely alias a later, unrelated value.
        memo[identity] = (value, result, size)
    else:
        raise _invalid()
    if size > maximum:
        _limit()
    return result, size


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise _invalid()
    return value


def _integer(value):
    if type(value) is not int or not 0 <= value < 2**63:
        raise _invalid()
    return value


def _uuid(value):
    if (
        type(value) is not str
        or not re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value
        )
        or value == "00000000-0000-0000-0000-000000000000"
    ):
        raise _invalid()
    return value.lower()


def _hash(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise _invalid()
    return value.lower()


def _snapshot(value):
    _fields(value, _SNAPSHOT_FIELDS)
    return asdict(
        SnapshotRef(
            _uuid(value["project_id"]),
            _hash(value["snapshot_id"]),
            _hash(value["manifest_hash"]),
        )
    )


def _layer(value):
    if set(value) == _LAYER_FIELDS:
        result = asdict(SnapshotLayer(**value))
    elif set(value) == _SOURCE_LAYER_FIELDS:
        from .source_configuration import SourceLayerSpec

        source = SourceLayerSpec(**value)
        result = {
            "layer_id": source.layer_id,
            "ordinal": source.ordinal,
            "kind": source.kind,
            "configuration_uuid": None,
            "identity_status": "unresolved",
            "source_format": source.source_format,
            "root_relative_path": source.root_relative_path,
        }
    else:
        raise _invalid()
    if result["source_format"] != "edt" or result["kind"] != (
        "base" if result["ordinal"] == 0 else "extension"
    ):
        raise _invalid()
    return result


def _xml_path_kind(path):
    if path == "Configuration.xml":
        return "Configuration", None
    parts = path.split("/")
    folder_kind = FOLDER_TO_TYPE.get(parts[0]) if parts else None
    if folder_kind is None or not path.endswith(".xml"):
        return None, None
    if (
        len(parts) in (2, 3)
        and parts[-1][:-4]
        and (len(parts) == 2 or parts[-1][:-4] == parts[1])
    ):
        return folder_kind, None
    if len(parts) == 4 and parts[2] in {"Forms", "Commands"} and parts[3][:-4]:
        return ("Form" if parts[2] == "Forms" else "Command"), "/".join(
            parts[:2]
        ) + ".xml"
    return None, None


def _ref(value, snapshot, layers, *, xml=False):
    _fields(value, {"snapshot", "layer_id", "relative_path", "raw_sha256"})
    if (
        _snapshot(value["snapshot"]) != snapshot
        or value["layer_id"] not in layers
        or type(value["relative_path"]) is not str
    ):
        raise _invalid()
    path = value["relative_path"]
    validate_file_paths((path,))
    parts = path.split("/")
    if xml:
        if _xml_path_kind(path)[0] is None:
            raise _invalid()
    elif path != "Configuration/Configuration.mdo" and (
        len(parts) != 3
        or parts[0] not in FOLDER_TO_TYPE
        or parts[2] != parts[1] + ".mdo"
    ):
        raise _invalid()
    return {
        "snapshot": snapshot,
        "layer_id": value["layer_id"],
        "relative_path": path,
        "raw_sha256": _hash(value["raw_sha256"]),
    }


@dataclass(frozen=True)
class _Row:
    record: bytes
    projection: bytes
    kind: str
    xml_path: str
    source_path: str
    owner_uuid: str | None
    owner_path: tuple | None
    layer: bytes


@dataclass(frozen=True)
class _Inventory:
    snapshot: dict
    digest: str
    layers: Mapping
    rows: Mapping
    owners: frozenset


def _normalize(value, limits):
    _fields(
        value,
        {
            "snapshot",
            "parser",
            "identity_scope",
            "coverage",
            "owner_basis",
            "layer_basis",
            "layers",
            "objects",
            "source_refs",
            "validation_summary",
        },
    )
    parser = value["parser"]
    xml_profile = parser == "edt_identity_v2"
    if parser not in {"edt_identity_v1", "edt_identity_v2"}:
        raise _invalid()
    if any(
        value[key] != expected
        for key, expected in {
            "identity_scope": "snapshot_layer",
            "coverage": "partial",
            "layer_basis": "pinned_snapshot_declaration",
        }.items()
    ):
        raise _invalid()
    expected_owner_basis = (
        "direct_xml_containment_and_verified_path_owner"
        if xml_profile
        else "direct_xml_containment_only"
    )
    if value["owner_basis"] != expected_owner_basis:
        raise _invalid()
    snapshot = _snapshot(value["snapshot"])
    for key, maximum in (
        ("layers", limits.max_layers),
        ("objects", limits.max_objects),
        ("source_refs", limits.max_objects),
    ):
        if type(value[key]) is not list:
            raise _invalid()
        if len(value[key]) > maximum:
            _limit()
    layers, layer_counts, ordinals = {}, {}, set()
    for entry in value["layers"]:
        counts = {"parsed_mdo_files", "unparsed_files", "count_basis"}
        fields = set(entry) - counts if type(entry) is dict else set()
        if fields == _LAYER_FIELDS:
            layer_input = {key: entry[key] for key in _LAYER_FIELDS}
        elif fields == _SOURCE_LAYER_FIELDS:
            layer_input = {key: entry[key] for key in _SOURCE_LAYER_FIELDS}
        else:
            raise _invalid()
        if type(entry) is not dict or type(entry.get("count_basis")) is not str:
            raise _invalid()
        layer = _layer(layer_input)
        lid, ordinal = layer["layer_id"], layer["ordinal"]
        if (
            lid in layers
            or ordinal in ordinals
            or entry["count_basis"] != "verified_manifest_paths"
        ):
            raise _invalid()
        ordinals.add(ordinal)
        layers[lid] = layer
        layer_counts[lid] = (
            _integer(entry["parsed_mdo_files"]),
            _integer(entry["unparsed_files"]),
        )
    refs = {}
    for entry in value["source_refs"]:
        ref = _ref(entry, snapshot, layers, xml=xml_profile)
        key = (ref["layer_id"], ref["relative_path"])
        if key in refs:
            raise _invalid()
        refs[key] = ref
    for lid in layers:
        paths = [path for layer, path in refs if layer == lid]
        validate_file_paths(paths)
        if len(paths) != layer_counts[lid][0]:
            raise _invalid()
    records, used_refs, locations, sibling_names = {}, set(), set(), set()
    child_positions = set()
    for entry in value["objects"]:
        _fields(entry, _OBJECT_FIELDS)
        uid = _uuid(entry["canonical_uuid"])
        if _uuid(entry["observed_uuid"]) != uid:
            raise _invalid()
        layer = _layer(entry["layer"])
        lid = layer["layer_id"]
        if layers.get(lid) != layer:
            raise _invalid()
        ref = _ref(entry["source_ref"], snapshot, layers, xml=xml_profile)
        ref_key = (lid, ref["relative_path"])
        if ref["layer_id"] != lid or refs.get(ref_key) != ref:
            raise _invalid()
        name, kind, xml_path = entry["name"], entry["type"], entry["xml_path"]
        if (
            type(name) is not str
            or not 1 <= len(name) <= 256
            or not re.fullmatch(r"[^\W\d]\w*", name)
            or type(kind) is not str
            or type(xml_path) is not str
            or len(xml_path) > 2048
        ):
            raise _invalid()
        owner = entry["owner"]
        if owner is not None:
            _fields(owner, {"canonical_uuid", "source_ref", "xml_path"})
            owner = {
                "canonical_uuid": _uuid(owner["canonical_uuid"]),
                "source_ref": _ref(
                    owner["source_ref"], snapshot, layers, xml=xml_profile
                ),
                "xml_path": owner["xml_path"],
            }
            if type(owner["xml_path"]) is not str:
                raise _invalid()
            if not xml_profile:
                if owner["source_ref"] != ref or kind not in _CHILDREN:
                    raise _invalid()
                position_match = re.fullmatch(
                    re.escape(owner["xml_path"] + "/" + _CHILDREN[kind])
                    + r"\[(0|[1-9][0-9]{0,5})\]",
                    xml_path,
                )
                if position_match is None:
                    raise _invalid()
                # Producer indices enumerate all direct XML children, across kinds.
                position = (*ref_key, owner["xml_path"], int(position_match[1]))
                if position in child_positions:
                    raise _invalid()
                child_positions.add(position)
            else:
                child_kind, parent_path = _xml_path_kind(ref["relative_path"])
                if parent_path is None:
                    if owner["source_ref"] != ref:
                        raise _invalid()
                    if kind not in _XML_CHILDREN or not re.fullmatch(
                        re.escape(owner["xml_path"] + "/ChildObjects/" + kind)
                        + r"\[(0|[1-9][0-9]{0,5})\]",
                        xml_path,
                    ):
                        raise _invalid()
                    position_match = re.fullmatch(
                        re.escape(owner["xml_path"] + "/ChildObjects/" + kind)
                        + r"\[(0|[1-9][0-9]{0,5})\]",
                        xml_path,
                    )
                    position = (*ref_key, owner["xml_path"], int(position_match[1]))
                    if position in child_positions:
                        raise _invalid()
                    child_positions.add(position)
                else:
                    if (
                        child_kind != kind
                        or owner["source_ref"]["relative_path"] != parent_path
                        or xml_path != "/" + kind
                        or name
                        != ref["relative_path"].removesuffix(".xml").split("/")[-1]
                    ):
                        raise _invalid()
        else:
            path = ref["relative_path"]
            expected = (
                _xml_path_kind(path)[0]
                if xml_profile
                else (
                    "Configuration"
                    if path == "Configuration/Configuration.mdo"
                    else FOLDER_TO_TYPE[path.split("/")[0]]
                )
            )
            expected_name = path.removesuffix(".xml" if xml_profile else ".mdo").split(
                "/"
            )[-1]
            if (
                kind != expected
                or xml_path != "/" + kind
                or (kind != "Configuration" and name != expected_name)
            ):
                raise _invalid()
        key = (lid, uid)
        location = (*ref_key, xml_path)
        sibling = (
            lid,
            owner["canonical_uuid"] if owner else None,
            kind,
            name.casefold(),
        )
        if key in records or location in locations or sibling in sibling_names:
            raise _invalid()
        locations.add(location)
        sibling_names.add(sibling)
        used_refs.add(ref_key)
        records[key] = {
            "canonical_uuid": uid,
            "observed_uuid": entry["observed_uuid"],
            "type": kind,
            "name": name,
            "xml_path": xml_path,
            "owner": owner,
            "layer": layer,
            "source_ref": ref,
            "source_size_bytes": None,
        }
    if used_refs != set(refs):
        raise _invalid()
    rows, owners = {}, set()
    for key, record in records.items():
        owner = record["owner"]
        owner_path = None
        if owner is not None:
            owner_key = (key[0], owner["canonical_uuid"])
            parent = records.get(owner_key)
            if (
                parent is None
                or parent["source_ref"] != owner["source_ref"]
                or parent["xml_path"] != owner["xml_path"]
                or (
                    parent["owner"] is not None
                    and not (
                        parent["type"] == "TabularSection"
                        and record["type"] == "Attribute"
                    )
                )
            ):
                raise _invalid()
            owners.add(owner_key)
            owner_path = (owner["source_ref"]["relative_path"], owner["xml_path"])
        projection = {
            "type": record["type"],
            "name": record["name"],
            "xml_path": record["xml_path"],
            "owner": None if owner is None else [owner["canonical_uuid"], *owner_path],
            "layer": record["layer"],
            "source_path": record["source_ref"]["relative_path"],
            "source_hash": record["source_ref"]["raw_sha256"],
            "source_size_bytes": None,
        }
        rows[key] = _Row(
            _canonical(record),
            _canonical(projection),
            record["type"],
            record["xml_path"],
            record["source_ref"]["relative_path"],
            owner["canonical_uuid"] if owner else None,
            owner_path,
            _canonical(record["layer"]),
        )
    if len(owners) > limits.max_owners:
        _limit()
    _fields(value["validation_summary"], {"generation"})
    generation = _fields(
        value["validation_summary"]["generation"],
        _SNAPSHOT_FIELDS
        | _GENERATION_COUNTS
        | {
            "source_digest",
            "graph_hash",
            "all_expected_files_verified",
            "inventory_checks",
            "expected_bytes_protected",
            "temporal_namespace_atomicity",
        },
    )
    if (
        _snapshot({key: generation[key] for key in _SNAPSHOT_FIELDS}) != snapshot
        or generation["all_expected_files_verified"] is not True
        or generation["inventory_checks"] != "entry_exit"
        or generation["expected_bytes_protected"] != "retained_handles"
        or generation["temporal_namespace_atomicity"] != "not_proven"
    ):
        raise _invalid()
    for name in _GENERATION_COUNTS:
        _integer(generation[name])
    _hash(generation["source_digest"])
    _hash(generation["graph_hash"])
    if (
        generation["verified_source_files"]
        < sum(sum(counts) for counts in layer_counts.values())
        or generation["verified_total_bytes"] < generation["verified_source_bytes"]
    ):
        raise _invalid()
    return _Inventory(
        snapshot,
        sha256(_canonical(value)).hexdigest(),
        MappingProxyType(layers),
        MappingProxyType(rows),
        frozenset(owners),
    )


def _unsupported(key, versions, records, moved):
    present = [record for record in records if record is not None]
    if key[1] in moved or len({record.layer for record in present}) > 1:
        return "layer_changed"
    if len({record.kind for record in present}) > 1:
        return "type_changed"
    if len({record.owner_uuid for record in present}) > 1:
        return "owner_changed"
    if len({record.owner_path for record in present}) > 1:
        return "owner_path_changed"
    example = present[0]
    for version, record in zip(versions, records):
        layer = version.layers.get(key[0])
        if layer is None:
            return "missing_layer_evidence"
        if _canonical(layer) != example.layer:
            return "layer_changed"
        if record is None and example.owner_uuid is not None:
            owner = version.rows.get((key[0], example.owner_uuid))
            if owner is None:
                return "missing_owner_evidence"
            if (owner.source_path, owner.xml_path) != example.owner_path:
                return "owner_path_changed"
    return None


def plan_edt_identity_three_way(
    base, current, upstream, *, limits=EDTIdentityThreeWayLimits()
):
    """Compare untrusted producer evidence; never read, write or materialize sources."""
    limits = EDTIdentityThreeWayLimits() if limits is None else limits
    if type(limits) is not EDTIdentityThreeWayLimits:
        raise CoreError("INVALID_QUERY_OPTIONS", "Typed identity plan limits required")
    try:
        memo = {}
        versions = tuple(
            _normalize(_capture(value, limits.max_input_bytes, memo, set())[0], limits)
            for value in (base, current, upstream)
        )
        if len({version.snapshot["project_id"] for version in versions}) != 1:
            raise _invalid()
        keys = set().union(*(version.rows for version in versions))
        layers = set().union(*(version.layers for version in versions))
        owners = set().union(*(version.owners for version in versions))
        if (
            len(keys) > min(limits.max_rows, limits.max_objects)
            or len(layers) > limits.max_layers
            or len(owners) > limits.max_owners
        ):
            _limit()
        memberships = {}
        for index, version in enumerate(versions):
            for lid, uid in version.rows:
                memberships.setdefault(uid, [set(), set(), set()])[index].add(lid)
        moved = {
            uid
            for uid, values in memberships.items()
            if len({frozenset(value) for value in values if value}) > 1
        }
        counts = {"objects": len(keys), **dict.fromkeys(_ACTIONS, 0)}
        rows = []
        ordered = sorted(
            keys,
            key=lambda key: (
                min(
                    version.layers[key[0]]["ordinal"]
                    for version in versions
                    if key[0] in version.layers
                ),
                *key,
            ),
        )
        for key in ordered:
            records = [version.rows.get(key) for version in versions]
            reason = _unsupported(key, versions, records, moved)
            action = (
                "unsupported"
                if reason
                else _action(
                    *(record.projection if record else None for record in records)
                )
            )
            row = {
                "key": {"layer_id": key[0], "canonical_uuid": key[1]},
                "action": action,
                **{
                    label: json.loads(record.record) if record else None
                    for label, record in zip(("base", "current", "upstream"), records)
                },
            }
            if reason:
                row["reason"] = reason
            counts[action] += 1
            rows.append(row)
        result = {
            "schema": 1,
            "scope": "edt-identity-v1",
            "mode": "read_only",
            "coverage": "partial",
            "materialization": "unavailable",
            "native_validation": "unavailable",
            "project_id": versions[0].snapshot["project_id"],
            "inputs": {
                label: {"snapshot": version.snapshot, "digest": version.digest}
                for label, version in zip(("base", "current", "upstream"), versions)
            },
            "counts": counts,
            "objects": rows,
        }
        if len(_canonical(result)) > _OUTPUT_LIMIT:
            raise CoreError(
                "OUTPUT_LIMIT_EXCEEDED", "Identity plan result exceeds its byte limit"
            )
        return result
    except CoreError as exc:
        if exc.code in {"EDT_IDENTITY_PLAN_LIMIT", "OUTPUT_LIMIT_EXCEEDED"}:
            raise
        raise _invalid() from exc
    except Exception as exc:
        raise _invalid() from exc
