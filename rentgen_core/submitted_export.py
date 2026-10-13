"""Read-only metadata analysis of an experimental Rust-owned submitted ZIP.

Imports never become published snapshots or live-source capabilities. This
module reuses the existing bounded XML parser; ZIP and file IO belong to Rust.
"""
from collections import Counter

from .errors import CoreError
from .metadata import _candidate, _child, _localized, _metadata, _text
from .metadata_xml import parse_xml
from .rust_input import RustInputSession

PERMISSIONS = frozenset({"project:read", "analysis:run"})


def _authorize(ctx):
    with ctx.state.transaction(ctx.principal) as tx:
        tx.require_all(PERMISSIONS)


def _short(value):
    if value is not None and (type(value) is not str or len(value.encode("utf-8")) > 4096):
        raise CoreError("IMPORTED_EXPORT_LIMIT", "Submitted export metadata exceeds output field bounds")
    return value


def analyze_export(ctx, *, archive, archive_sha256, input_core, input_core_sha256, query="", limit=50, cancelled=None):
    """Analyze immutable accepted bytes with reauthorization before any release."""
    def authorize():
        _authorize(ctx)
        if cancelled is not None and cancelled():
            raise CoreError("CANCELLED", "Submitted export analysis was cancelled")

    authorize()
    if type(query) is not str or len(query.encode("utf-8")) > 256 or type(limit) is not int or not 1 <= limit <= 200:
        raise CoreError("INVALID_QUERY_OPTIONS", "Export query and page limit must be bounded")
    try:
        with RustInputSession(input_core, input_core_sha256, authorize=authorize) as session:
            manifest = session.open_import(archive, archive_sha256)
            entries = session.entries(manifest)
            objects, modules, types = [], [], Counter()
            candidates = matches = unsupported = module_count = 0
            for entry in sorted(entries, key=lambda item: item["path"].encode("utf-8")):
                authorize()
                reference = {"input_sha256": archive_sha256, "relative_path": entry["path"], "raw_sha256": entry["raw_sha256"]}
                if entry["path"].lower().endswith((".bsl", ".os", ".bsp")):
                    module_count += 1
                    if len(modules) < limit:
                        modules.append({"input_ref": reference, "size_bytes": entry["size_bytes"], "analysis": "inventory_only"})
                kind = _candidate(entry["path"])
                if kind is None or entry["path"].lower().endswith(".mdo"):
                    continue
                candidates += 1
                try:
                    root = parse_xml(session.read_entry(entry))
                except CoreError as error:
                    raise CoreError(error.code, "Submitted export metadata could not be parsed") from error
                meta = _metadata(root, kind)
                if meta is None:
                    unsupported += 1
                    continue
                props = _child(meta, "Properties")
                if props is None:
                    # First profile is explicit Designer XML, not inferred EDT.
                    unsupported += 1
                    continue
                types[kind] += 1
                row = {
                    "type": kind, "name": _short(_text(props, "Name")),
                    "synonym": _short(_localized(props, "Synonym")),
                    "observed_uuid": _short(meta.attrib.get("uuid")),
                    "uuid_status": "unverified", "input_ref": reference,
                }
                text = " ".join(value or "" for value in (row["name"], row["synonym"], kind, entry["path"]))
                if not query or query.casefold() in text.casefold():
                    matches += 1
                    if len(objects) < limit:
                        objects.append(row)
            if not sum(types.values()):
                raise CoreError("IMPORTED_EXPORT_UNSUPPORTED", "No supported Designer metadata roots were found at the explicit archive root")
            result = {
                "format_status": "partial" if unsupported or any(item["path"].lower().endswith(".mdo") for item in entries) else "recognized",
                "schema": 1, "project_id": ctx.project_id,
                "scope": "submitted_designer_export", "parser": "designer_xml_v1",
                "input": manifest,
                "coverage": {
                    "metadata": "bounded_root_properties_only",
                    "bsl": "inventory_only", "live_source": "not_verified",
                    "published_snapshot": False,
                },
                "counts": {
                    "files": len(entries), "metadata_candidates": candidates,
                    "metadata_objects": sum(types.values()),
                    "unsupported_metadata_roots": unsupported, "modules": module_count,
                    "other_files": len(entries) - candidates - module_count,
                },
                "by_type": dict(sorted(types.items())),
                "objects": objects, "matching_objects": matches,
                "objects_truncated": matches > len(objects),
                "modules": modules, "modules_truncated": module_count > len(modules),
            }
        authorize()
        return result
    finally:
        _authorize(ctx)
