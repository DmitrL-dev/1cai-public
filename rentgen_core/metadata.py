"""Read-only Designer metadata over one authorized published snapshot.

No live paths, defaults, inferred canonical IDs, cross-layer merge or cache.
"""

from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
import re

from .errors import CoreError
from .manifests import canonical_bytes, sha256
from .metadata_xml import parse_xml
from .sources import SnapshotReadLimits
from .source_paths import validate_source_path

# Pure vocabulary adapted from the legacy metadata graph; no service import.
FOLDER_TO_TYPE = {
    plural: singular
    for plural, singular in (
        ("Catalogs", "Catalog"),
        ("Documents", "Document"),
        ("InformationRegisters", "InformationRegister"),
        ("AccumulationRegisters", "AccumulationRegister"),
        ("AccountingRegisters", "AccountingRegister"),
        ("CalculationRegisters", "CalculationRegister"),
        ("Enums", "Enum"),
        ("ChartsOfAccounts", "ChartOfAccounts"),
        ("ChartsOfCharacteristicTypes", "ChartOfCharacteristicTypes"),
        ("ChartsOfCalculationTypes", "ChartOfCalculationTypes"),
        ("BusinessProcesses", "BusinessProcess"),
        ("Tasks", "Task"),
        ("DataProcessors", "DataProcessor"),
        ("Reports", "Report"),
        ("CommonModules", "CommonModule"),
        ("ExchangePlans", "ExchangePlan"),
        ("Constants", "Constant"),
        ("CommonForms", "CommonForm"),
        ("CommonCommands", "CommonCommand"),
        ("SettingsStorages", "SettingsStorage"),
        ("SessionParameters", "SessionParameter"),
        ("Roles", "Role"),
        ("CommonTemplates", "CommonTemplate"),
        ("FilterCriteria", "FilterCriterion"),
        ("EventSubscriptions", "EventSubscription"),
        ("ScheduledJobs", "ScheduledJob"),
        ("FunctionalOptions", "FunctionalOption"),
        ("FunctionalOptionsParameters", "FunctionalOptionsParameter"),
        ("DefinedTypes", "DefinedType"),
        ("Sequences", "Sequence"),
        ("DocumentJournals", "DocumentJournal"),
        ("CommandGroups", "CommandGroup"),
        ("CommonAttributes", "CommonAttribute"),
        ("Subsystems", "Subsystem"),
        ("WebServices", "WebService"),
        ("HTTPServices", "HTTPService"),
        ("ExternalDataSources", "ExternalDataSource"),
        ("IntegrationServices", "IntegrationService"),
        ("WSReferences", "WSReference"),
        ("XDTOPackages", "XDTOPackage"),
    )
}


@dataclass(frozen=True)
class MetadataLimits:
    max_xml_bytes: int = 4 * 1024 * 1024
    max_nodes: int = 50_000
    max_depth: int = 64
    max_inventory: int = 20_000
    max_collection: int = 200
    max_total_bytes: int = 64 * 1024 * 1024
    max_asset_bytes: int = 16 * 1024 * 1024

    def __post_init__(self):
        maxima = (
            4 * 1024 * 1024,
            50_000,
            64,
            20_000,
            200,
            64 * 1024 * 1024,
            16 * 1024 * 1024,
        )
        if any(
            type(value) is not int or not 1 <= value <= maximum
            for value, maximum in zip(asdict(self).values(), maxima)
        ):
            raise CoreError(
                "INVALID_QUERY_OPTIONS", "Metadata limits must be positive and bounded"
            )


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _child(element, name):
    return (
        next((item for item in element if _local(item.tag) == name), None)
        if element is not None
        else None
    )


def _text(element, name):
    item = _child(element, name)
    return (item.text or "").strip() or None if item is not None else None


def _localized(element, name):
    node = _child(element, name)
    if node is None:
        return None
    values = {}
    for item in node.iter():
        if _local(item.tag) == "item":
            content = _text(item, "content")
            if content:
                values[_text(item, "lang") or ""] = content
    return (
        values.get("ru")
        or values.get("")
        or next(iter(values.values()), None)
        or (node.text or "").strip()
        or None
    )


def _candidate(path):
    if path == "Configuration.xml":
        return "Configuration"
    parts = path.split("/")
    if parts[0] not in FOLDER_TO_TYPE or not path.endswith(".xml"):
        return None
    if len(parts) == 2 or (len(parts) == 3 and parts[2] == parts[1] + ".xml"):
        return FOLDER_TO_TYPE[parts[0]]
    return None


def _metadata(root, kind):
    if _local(root.tag) != "MetaDataObject":
        return None
    children = [
        item for item in root if _local(item.tag) not in ("InternalInfo", "Properties")
    ]
    if len(children) != 1 or _local(children[0].tag) != kind:
        return None
    return children[0] if _child(children[0], "Properties") is not None else None


def _authorize(ctx):
    if ctx is None:
        raise CoreError("CONTEXT_REQUIRED", "Pinned project context is required")
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all({"project:read"})
        if ctx.snapshot is None or ctx.sources is None:
            raise CoreError(
                "SNAPSHOT_REQUIRED", "Metadata requires a published snapshot"
            )
        return tx.get_snapshot_layers(ctx.snapshot.snapshot_id)


class _Read:
    def __init__(self, session, limits):
        self.session, self.limits, self.used = session, limits, 0
        self.verified = {}

    def bytes(self, entry, *, xml=False):
        self.session.checkpoint()
        limit = self.limits.max_xml_bytes if xml else self.limits.max_asset_bytes
        if (
            entry.size_bytes > limit
            or self.used + entry.size_bytes > self.limits.max_total_bytes
        ):
            raise CoreError(
                "METADATA_LIMIT_EXCEEDED",
                "Metadata read byte budget exceeded",
                details={"source_ref": asdict(entry.ref)},
            )
        self.used += entry.size_bytes
        raw = self.session.read_source(entry.ref)
        self.session.checkpoint()
        self.verified[entry.ref] = entry.ref
        return raw

    def xml(self, entry):
        # Capability failures (particularly revocation) remain unchanged; never
        # attach a previously discovered source path to a forbidden response.
        raw = self.bytes(entry, xml=True)
        try:
            result = parse_xml(
                raw,
                max_bytes=self.limits.max_xml_bytes,
                max_nodes=self.limits.max_nodes,
                max_depth=self.limits.max_depth,
            )
            self.session.checkpoint()
            return result
        except CoreError as error:
            raise CoreError(
                error.code,
                error.message,
                details={**error.details, "source_ref": asdict(entry.ref)},
            ) from error


def _inventory(reader):
    entries = reader.session.entries()
    if len(entries) > reader.limits.max_inventory:
        raise CoreError("METADATA_LIMIT_EXCEEDED", "Metadata inventory limit exceeded")
    return entries


@contextmanager
def _operation(ctx, layer_id, limits):
    layers = _authorize(ctx)
    if not isinstance(limits, MetadataLimits):
        raise CoreError("INVALID_QUERY_OPTIONS", "Typed metadata limits required")
    if layer_id is not None and layer_id not in {layer.layer_id for layer in layers}:
        raise CoreError("SOURCE_LAYER_NOT_FOUND", "Layer is absent from this snapshot")
    with ctx.sources.read_session(limits=SnapshotReadLimits()) as session:
        reader = _Read(session, limits)
        yield reader, [
            layer for layer in layers if layer_id is None or layer.layer_id == layer_id
        ]
        session.checkpoint()


def _refs_digest(snapshot, layers, kind, refs):
    ordinals = {layer: index for index, layer in enumerate(layers)}
    return sha256(
        canonical_bytes(
            {
                "domain": "rentgen.metadata.examined_refs.v1",
                "snapshot": asdict(snapshot),
                "parser": "designer_xml_v1",
                "selected_layers": layers,
                "kind": kind,
                "records": [
                    {
                        "layer_id": ref.layer_id,
                        "relative_path": ref.relative_path,
                        "raw_sha256": ref.raw_sha256,
                    }
                    for ref in sorted(
                        refs,
                        key=lambda ref: (
                            ordinals[ref.layer_id],
                            ref.relative_path.encode("utf-8"),
                        ),
                    )
                ],
            }
        )
    )


def _attach_refs(reader, result):
    """Only returned values/witnesses get inline refs; scanning has a separate digest."""
    selected = {}
    verified = {(ref.layer_id, ref.relative_path): ref for ref in reader.verified}

    def walk(value):
        reader.session.checkpoint()
        if isinstance(value, dict):
            if set(value) == {"snapshot", "layer_id", "relative_path", "raw_sha256"}:
                ref = verified.get((value["layer_id"], value["relative_path"]))
                if ref is None or asdict(ref) != value:
                    raise CoreError(
                        "SOURCE_REF_MISMATCH",
                        "Metadata result contains an unverified source reference",
                    )
                selected[ref] = value
            else:
                for key, child in value.items():
                    # Arbitrary XML attribute names are source data, never
                    # transport capability fields, even when their keys coincide.
                    if key != "xml_attributes":
                        walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(result)
    # The reader's order follows the pinned layer/path inventory, then nested reads.
    result["source_refs"] = [
        selected[ref] for ref in reader.verified if ref in selected
    ]


def _preview(entry, meta, kind):
    props = _child(meta, "Properties")
    return {
        "source_ref": asdict(entry.ref),
        "type": kind,
        "name": _text(props, "Name"),
        "synonym": _localized(props, "Synonym"),
        "observed_uuid": meta.attrib.get("uuid"),
        "uuid_status": "unverified",
    }


def _load(ctx, layers, reader, *, search_options=None, object_path=None):
    entries = _inventory(reader)
    grouped = {layer.layer_id: [] for layer in layers}
    for entry in entries:
        if entry.ref.layer_id in grouped:
            grouped[entry.ref.layer_id].append(entry)
    results, matches, selected_object, total_matches = [], [], None, 0
    all_xml, all_mdo, candidate_count, matching_roots = [], [], 0, 0
    all_examined = True
    layer_ids = [layer.layer_id for layer in layers]
    for layer in layers:
        reader.session.checkpoint()
        selected = grouped[layer.layer_id]
        candidates = [
            (entry, _candidate(entry.ref.relative_path)) for entry in selected
        ]
        candidates = [(entry, kind) for entry, kind in candidates if kind is not None]
        candidate_count += len(candidates)
        xml_refs, mdo_refs, witnesses = [], [], {}
        decision = {
            "declared": layer.source_format,
            "detected": None,
            "status": "unsupported",
            "reason": "No verified Designer XML path/root evidence",
            "evidence": [],
            "evidence_scope": "bounded_witnesses",
        }
        result = {
            **asdict(layer),
            "format_decision": decision,
            "status": "unsupported",
            "completeness": "unsupported_format",
            "inventory_counts": {
                "files": len(selected),
                "objects": None,
                "modules": sum(
                    entry.ref.relative_path.lower().endswith((".bsl", ".os", ".bsp"))
                    for entry in selected
                ),
                "forms": sum(
                    bool(
                        re.fullmatch(
                            r"[^/]+/[^/]+/Forms/[^/]+\.xml", entry.ref.relative_path
                        )
                    )
                    for entry in selected
                ),
                "commands": sum(
                    bool(
                        re.fullmatch(
                            r"[^/]+/[^/]+/Commands/[^/]+\.xml", entry.ref.relative_path
                        )
                    )
                    for entry in selected
                ),
                "rights_documents": sum(
                    entry.ref.relative_path.endswith("/Ext/Rights.xml")
                    for entry in selected
                ),
            },
            "count_basis": "verified_manifest_paths; object roots verified only for supported layers",
            "parsed_rights": None,
        }
        results.append(result)
        mdo = [
            entry
            for entry in selected
            if entry.ref.relative_path.lower().endswith(".mdo")
        ]
        skip_xml = layer.source_format == "edt" or bool(mdo)
        local_types, local_matches, local_total = Counter(), [], 0
        local_object, configuration, valid = None, None, True
        if skip_xml:
            all_examined = False
            decision["reason"] = "EDT .mdo parsing is not implemented"
            for entry in mdo:
                reader.bytes(entry)
                mdo_refs.append(entry.ref)
                witnesses.setdefault("mdo", entry.ref)
        else:
            for entry, kind in candidates:
                reader.session.checkpoint()
                meta = _metadata(reader.xml(entry), kind)
                xml_refs.append(entry.ref)
                if meta is None:
                    valid = False
                    decision[
                        "reason"
                    ] = "Candidate XML root does not match Designer path/type"
                    witnesses.setdefault("mismatch", entry.ref)
                    continue
                local_types[kind] += 1
                witnesses.setdefault(
                    "configuration" if kind == "Configuration" else "object", entry.ref
                )
                if kind == "Configuration":
                    if configuration is None:
                        configuration = _preview(entry, meta, kind)
                else:
                    if object_path == entry.ref.relative_path:
                        local_object = (entry, meta, kind)
                    if search_options is not None:
                        query, metadata_type, limit = search_options
                        preview = _preview(entry, meta, kind)
                        haystack = " ".join(
                            value or ""
                            for value in (
                                preview["name"],
                                preview["synonym"],
                                kind,
                                entry.ref.relative_path,
                            )
                        ).casefold()
                        if (
                            metadata_type is None
                            or kind.casefold() == metadata_type.casefold()
                        ) and (not query or query.casefold() in haystack):
                            local_total += 1
                            if len(local_matches) < max(0, limit - len(matches)):
                                local_matches.append(preview)
                # The exact selected object is the only tree allowed to survive
                # this iteration. Summary/search keep only bounded scalar previews.
                del meta
                reader.session.checkpoint()
            if valid and local_types:
                decision.update(
                    detected="designer_xml",
                    status="supported",
                    reason="Verified MetaDataObject/Properties and path-matching type",
                )
                result.update(
                    status="supported", completeness="supported_layer_inventory"
                )
                result["inventory_counts"]["objects"] = sum(
                    count
                    for kind, count in local_types.items()
                    if kind != "Configuration"
                )
                result["by_type"] = {
                    kind: count
                    for kind, count in local_types.items()
                    if kind != "Configuration"
                }
                result["configuration"] = configuration
                matches.extend(local_matches)
                total_matches += local_total
                if local_object is not None:
                    selected_object = local_object
        # Separate XML parser observations from opaque EDT raw-byte verification.
        local_matching = sum(local_types.values())
        matching_roots += local_matching
        all_xml.extend(xml_refs)
        all_mdo.extend(mdo_refs)
        decision["evidence"] = [
            asdict(ref)
            for ref in sorted(
                set(witnesses.values()),
                key=lambda ref: ref.relative_path.encode("utf-8"),
            )
        ]
        decision["scan"] = {
            "xml_candidates": {
                "status": "skipped_unsupported_format"
                if skip_xml
                else "examined"
                if candidates
                else "no_candidates",
                "candidate_count": len(candidates),
                "parsed_count": len(xml_refs),
                "matching_root_count": local_matching,
                "refs_sha256": _refs_digest(
                    ctx.snapshot, [layer.layer_id], "xml_candidates", xml_refs
                ),
            },
            "opaque_mdo": {
                "status": "verified_bytes" if mdo_refs else "absent",
                "verified_count": len(mdo_refs),
                "refs_sha256": _refs_digest(
                    ctx.snapshot, [layer.layer_id], "opaque_mdo", mdo_refs
                ),
            },
        }
    envelope = {
        "snapshot": asdict(ctx.snapshot),
        "parser": "designer_xml_v1",
        "evidence_schema": "metadata_scan_v2",
        "identity_status": "source_path_only",
        "layers": results,
        "source_refs_scope": "returned_values_and_format_witnesses",
        "truncated": False,
        "completeness": "supported_layer_inventory"
        if all(layer["format_decision"]["status"] == "supported" for layer in results)
        else "unsupported_layers",
        "validation_summary": {
            "metadata_scan": {
                "selection_policy": "designer_candidates_unless_edt_or_mdo_v1",
                "selected_layers": layer_ids,
                "all_selected_candidates_examined": all_examined,
                "xml_candidates": {
                    "candidate_count": candidate_count,
                    "parsed_count": len(all_xml),
                    "matching_root_count": matching_roots,
                    "refs_sha256": _refs_digest(
                        ctx.snapshot, layer_ids, "xml_candidates", all_xml
                    ),
                },
                "opaque_mdo": {
                    "verified_count": len(all_mdo),
                    "refs_sha256": _refs_digest(
                        ctx.snapshot, layer_ids, "opaque_mdo", all_mdo
                    ),
                },
            }
        },
    }
    if search_options is not None:
        envelope.update(
            objects=matches,
            total_matches=total_matches,
            returned=len(matches),
            truncated=total_matches > len(matches),
        )
    reader.session.checkpoint()
    return (
        envelope,
        selected_object,
        [entry for entry in entries if entry.ref.layer_id in grouped],
    )


def metadata_summary(ctx, *, layer_id=None, limits=MetadataLimits()):
    with _operation(ctx, layer_id, limits) as (reader, layers):
        result, _, _ = _load(ctx, layers, reader)
        _attach_refs(reader, result)
    result["validation_summary"]["generation"] = reader.session.validation_summary
    return result


def _collection(items, limit):
    return {
        "items": items[:limit],
        "total": len(items),
        "truncated": len(items) > limit,
    }


def _properties(meta, ref, limit):
    """Bounded leaf projection preserves nesting and original scalar strings."""
    values = []

    def walk(node, path):
        if not len(node):
            values.append(
                {
                    "path": path,
                    "value": (node.text or "").strip(),
                    "xml_attributes": dict(node.attrib),
                    "source_ref": ref,
                }
            )
        for index, child in enumerate(node):
            walk(child, path + "/" + _local(child.tag) + "[" + str(index) + "]")

    props = _child(meta, "Properties")
    if props is not None:
        walk(props, "Properties")
    return _collection(values, limit)


def _named(meta, tag, ref, limit):
    result = []
    for item in meta.iter():
        if _local(item.tag) != tag:
            continue
        props = _child(item, "Properties")
        result.append(
            {
                "name": item.attrib.get("name")
                or _text(item, "Name")
                or _text(props, "Name"),
                "synonym": _localized(item, "Synonym") or _localized(props, "Synonym"),
                "observed_uuid": item.attrib.get("uuid"),
                "uuid_status": "unverified",
                "properties": _properties(item, ref, limit),
                "source_ref": ref,
            }
        )
    return _collection(result, limit)


def _rights(entry, reader, limit):
    root, ref = reader.xml(entry), asdict(entry.ref)
    if _local(root.tag) != "Rights":
        raise CoreError(
            "METADATA_FORMAT_UNSUPPORTED",
            "Rights XML has an unsupported root",
            details={"source_ref": ref},
        )
    objects, records = 0, []
    for element in root.iter():
        if _local(element.tag) != "object":
            continue
        objects += 1
        for right in element:
            if _local(right.tag) != "right":
                continue
            value = _text(right, "value")
            records.append(
                {
                    "object": _text(element, "name"),
                    "name": _text(right, "name"),
                    "value": value,
                    "enabled": {"true": True, "false": False}.get(
                        (value or "").lower()
                    ),
                    "source_ref": ref,
                }
            )
    understood = all(
        record["enabled"] is not None and record["name"] and record["object"]
        for record in records
    )
    return {
        "source_ref": ref,
        "status": "parsed" if understood else "uninterpreted_values",
        "counts": {
            "objects": objects,
            "declared_rights": len(records),
            "enabled_rights": sum(record["enabled"] is True for record in records)
            if understood
            else None,
        },
        "entries": _collection(records, limit),
        "semantic_scope": "XML declarations only; effective platform permissions unverified",
    }


def _nested_assets(entry, entries, reader, limit):
    path = entry.ref.relative_path
    parts = path.split("/")
    prefix = "/".join((parts[0], parts[1].removesuffix(".xml"))) + "/"
    groups = {name: [] for name in ("modules", "forms", "form_documents", "commands")}
    rights = None
    for child in entries:
        relative = child.ref.relative_path
        if child.ref.layer_id != entry.ref.layer_id or not relative.startswith(prefix):
            continue
        tail = relative[len(prefix) :]
        segments = tail.split("/")
        if relative.lower().endswith((".bsl", ".os", ".bsp")):
            groups["modules"].append(child)
        elif (
            len(segments) == 2
            and segments[0] in ("Forms", "Commands")
            and relative.endswith(".xml")
        ):
            groups["forms" if segments[0] == "Forms" else "commands"].append(child)
        elif ("Forms" in segments and relative.endswith("/Ext/Form.xml")) or (
            parts[0] == "CommonForms" and tail == "Ext/Form.xml"
        ):
            groups["form_documents"].append(child)
        elif tail == "Ext/Rights.xml":
            rights = child
    result = {}
    for category, selected in groups.items():
        values = []
        for child in selected[:limit]:
            ref = asdict(child.ref)
            if category == "modules":
                reader.bytes(child)
                value = {
                    "source_ref": ref,
                    "size_bytes": child.size_bytes,
                    "status": "verified_bytes",
                    "encoding": child.encoding,
                }
            else:
                root = reader.xml(child)
                kind = "Command" if category == "commands" else "Form"
                meta = _metadata(root, kind)
                if category == "form_documents":
                    if _local(root.tag) != "Form":
                        raise CoreError(
                            "METADATA_FORMAT_UNSUPPORTED",
                            "Unsupported form document root",
                            details={"source_ref": ref},
                        )
                    # The full bounded XML is retained by SourceRef. A leaf projection
                    # exposes controls/attributes without claiming structural editing.
                    value = {
                        "source_ref": ref,
                        "status": "parsed",
                        "root": "Form",
                        "fields": _document_fields(root, ref, limit),
                    }
                elif meta is None:
                    raise CoreError(
                        "METADATA_FORMAT_UNSUPPORTED",
                        "Nested metadata root does not match path",
                        details={"source_ref": ref},
                    )
                else:
                    value = {
                        **_preview(child, meta, kind),
                        "properties": _properties(meta, ref, limit),
                    }
            values.append(value)
        result[category] = {
            "items": values,
            "total": len(selected),
            "truncated": len(selected) > limit,
        }
    result["rights"] = (
        _rights(rights, reader, limit)
        if rights is not None
        else {"status": "absent_in_snapshot", "counts": None, "source_ref": None}
    )
    return result


def _document_fields(root, ref, limit):
    values = [
        {
            "tag": _local(item.tag),
            "value": (item.text or "").strip(),
            "xml_attributes": dict(item.attrib),
            "source_ref": ref,
        }
        for item in root.iter()
        if not len(item)
    ]
    return _collection(values, limit)


def get_metadata_object(ctx, *, layer_id, relative_path, limits=MetadataLimits()):
    _authorize(ctx)
    if not isinstance(layer_id, str) or not layer_id:
        raise CoreError(
            "INVALID_QUERY_OPTIONS", "Object lookup requires an explicit layer"
        )
    validate_source_path(relative_path)
    with _operation(ctx, layer_id, limits) as (reader, layers):
        result, selected, entries = _load(
            ctx, layers, reader, object_path=relative_path
        )
        if result["layers"][0]["status"] != "supported":
            raise CoreError(
                "METADATA_FORMAT_UNSUPPORTED",
                "Layer has no supported Designer metadata",
                details={
                    "snapshot": asdict(ctx.snapshot),
                    "layer": result["layers"][0],
                },
            )
        if selected is None:
            raise CoreError(
                "METADATA_OBJECT_NOT_FOUND",
                "Exact metadata path is absent from this layer",
            )
        entry, meta, kind = selected
        ref, limit = asdict(entry.ref), limits.max_collection
        obj = {
            **_preview(entry, meta, kind),
            "properties": _properties(meta, ref, limit),
        }
        for field, tag in (
            ("attributes", "Attribute"),
            ("tabular_sections", "TabularSection"),
            ("dimensions", "Dimension"),
            ("resources", "Resource"),
        ):
            obj[field] = _named(meta, tag, ref, limit)
        references = []
        for item in meta.iter():
            value = (item.text or "").strip()
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*(?:\.[\w]+)+", value):
                references.append(
                    {"value": value, "resolution": "unresolved", "source_ref": ref}
                )
        obj["references"] = _collection(references, limit)
        obj.update(_nested_assets(entry, entries, reader, limit))
        result.update(object=obj)
        result["truncated"] = _has_truncation(obj)
        result["completeness"] = (
            "bounded_object_details"
            if result["truncated"]
            else "parsed_supported_object"
        )
        _attach_refs(reader, result)
    result["validation_summary"]["generation"] = reader.session.validation_summary
    return result


def _has_truncation(value):
    if isinstance(value, dict):
        return value.get("truncated") is True or any(
            _has_truncation(item) for item in value.values()
        )
    return isinstance(value, list) and any(_has_truncation(item) for item in value)


def search_metadata(
    ctx,
    query=None,
    *,
    metadata_type=None,
    layer_id=None,
    limit=30,
    limits=MetadataLimits(),
):
    if (
        type(limit) is not int
        or not 1 <= limit <= 200
        or any(
            value is not None and (not isinstance(value, str) or len(value) > 256)
            for value in (query, metadata_type)
        )
    ):
        raise CoreError("INVALID_QUERY_OPTIONS", "Invalid metadata search options")
    with _operation(ctx, layer_id, limits) as (reader, layers):
        result, _, _ = _load(
            ctx, layers, reader, search_options=(query, metadata_type, limit)
        )
        _attach_refs(reader, result)
    result["validation_summary"]["generation"] = reader.session.validation_summary
    return result
