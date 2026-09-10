"""Typed metadata intent over exact retained snapshot bytes and UUID ownership."""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from ._windows_source_tree import pinned_directory
from .edt_execution import IDENTIFIER
from .edt_profiles import authorized, parse_json
from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .metadata_xml import parse_xml
from .resolver import require_snapshot
from .sources import SnapshotReadLimits

MD = "{http://v8.1c.ru/8.3/MDClasses}"
MAX_TOTAL = 1024**3


def require(condition, message="Invalid metadata plan"):
    if not condition:
        raise CoreError("METADATA_PLAN_INVALID", message)


def keys(value, expected):
    require(type(value) is dict and set(value) == set(expected))


def _request(ctx, value):
    require_snapshot(ctx)
    require(ctx.sources is not None)
    keys(
        value,
        {
            "schema",
            "operation",
            "snapshot",
            "layer_id",
            "catalog",
            "attribute",
            "new_name",
        },
    )
    raw = canonical_bytes(value)
    require(len(raw) <= 8192)
    value = parse_json(raw)
    require(type(value["schema"]) is int and value["schema"] == 1)
    require(value["operation"] == "rename_catalog_attribute")
    require(
        value["snapshot"] == asdict(ctx.snapshot),
        "Plan snapshot differs from selected snapshot",
    )
    for name in ("catalog", "attribute"):
        keys(value[name], {"name", "uuid"})
        identifier, identity = value[name]["name"], value[name]["uuid"]
        require(type(identifier) is str and IDENTIFIER.fullmatch(identifier))
        try:
            require(type(identity) is str and str(UUID(identity)) == identity)
        except ValueError as exc:
            raise CoreError("METADATA_PLAN_INVALID", "Invalid object UUID") from exc
    require(type(value["new_name"]) is str and IDENTIFIER.fullmatch(value["new_name"]))
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"project:read", "source:edit", "analysis:run"})
        layers = tx.get_snapshot_layers(ctx.snapshot.snapshot_id)
    require(
        len(layers) == 1
        and layers[0].kind == "base"
        and layers[0].source_format == "designer_xml",
        "One captured Designer XML base layer is required",
    )
    require(value["layer_id"] == layers[0].layer_id)
    return value


def _name(element):
    nodes = element.findall(MD + "Properties/" + MD + "Name")
    require(len(nodes) == 1 and nodes[0].text, "Missing or ambiguous metadata name")
    return nodes[0].text


def _identity(root, request):
    require(root.tag == MD + "MetaDataObject")
    catalogs = root.findall(MD + "Catalog")
    require(len(catalogs) == 1)
    catalog = catalogs[0]
    require(_name(catalog) == request["catalog"]["name"])
    require(
        catalog.get("uuid", "").lower() == request["catalog"]["uuid"],
        "Catalog UUID does not match its retained source",
    )
    attributes = catalog.findall(MD + "ChildObjects/" + MD + "Attribute")
    names = [_name(item) for item in attributes]
    require(
        len({name.casefold() for name in names}) == len(names),
        "Ambiguous attribute names",
    )
    found = [
        item
        for item, name in zip(attributes, names)
        if name == request["attribute"]["name"]
    ]
    require(
        len(found) == 1
        and found[0].get("uuid", "").lower() == request["attribute"]["uuid"],
        "Attribute UUID or ownership does not match",
    )
    require(
        request["new_name"].casefold() not in {name.casefold() for name in names},
        "New attribute name already exists",
    )


def _scan(ctx, request, check, *, destination=None):
    path = "Catalogs/" + request["catalog"]["name"] + ".xml"
    target, catalog_tree, configuration = None, None, False
    identities, inventory = Counter(), []
    with ctx.sources.read_session(limits=SnapshotReadLimits()) as session:
        entries = session.entries()
        require(
            sum(entry.size_bytes for entry in entries) <= MAX_TOTAL,
            "Configuration exceeds materialization limits",
        )
        for entry in entries:
            check()
            require(entry.ref.layer_id == request["layer_id"])
            require(
                entry.size_bytes <= 64 * 1024**2,
                "Source file exceeds materialization limits",
            )
            raw = session.read_source(entry.ref)
            relative = entry.ref.relative_path
            if relative.lower().endswith(".xml"):
                tree = parse_xml(raw)
                for element in tree.iter():
                    if element.tag.startswith(MD) and "uuid" in element.attrib:
                        identities[element.attrib["uuid"].lower()] += 1
                if relative == path:
                    target, catalog_tree = entry.ref, tree
                if relative == "Configuration.xml":
                    configuration = (
                        tree.tag == MD + "MetaDataObject"
                        and len(tree.findall(MD + "Configuration")) == 1
                    )
            inventory.append(
                {"path": relative, "size": len(raw), "sha256": entry.ref.raw_sha256}
            )
            if destination is not None:
                output = destination / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("xb") as stream:
                    stream.write(raw)
        require(
            configuration and target is not None,
            "Retained configuration or catalog is missing",
        )
        _identity(catalog_tree, request)
        require(
            all(
                identities[request[key]["uuid"]] == 1
                for key in ("catalog", "attribute")
            ),
            "Object UUID is duplicated across retained metadata",
        )
    inventory.sort(key=lambda row: row["path"])
    return target, inventory


def _plan(request, source, inventory):
    value = {
        "schema": 1,
        "request": request,
        "source_ref": asdict(source),
        "input_digest": sha256(canonical_bytes(inventory)),
        "input_files": len(inventory),
        "input_bytes": sum(row["size"] for row in inventory),
    }
    return {**value, "plan_id": sha256(canonical_bytes(value))}


def create_plan(ctx, request):
    with authorized(ctx) as check:
        request = _request(ctx, request)
        source, inventory = _scan(ctx, request, check)
        return _plan(request, source, inventory)


def validate_plan(ctx, value):
    with authorized(ctx):
        keys(
            value,
            {
                "schema",
                "request",
                "source_ref",
                "input_digest",
                "input_files",
                "input_bytes",
                "plan_id",
            },
        )
        value = parse_json(canonical_bytes(value))
        actual = create_plan(ctx, value["request"])
        require(
            canonical_bytes(actual) == canonical_bytes(value),
            "Plan does not match retained inputs",
        )
        return actual


def materialize(ctx, value, destination):
    with authorized(ctx) as check:
        value = validate_plan(ctx, value)
        destination = Path(destination)
        destination.mkdir(exist_ok=False)
        with pinned_directory(destination):
            source, inventory = _scan(
                ctx, value["request"], check, destination=destination
            )
        require(
            _plan(value["request"], source, inventory) == value,
            "Materialized inputs differ from plan",
        )
        return inventory
