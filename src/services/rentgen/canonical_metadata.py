"""Canonical 1C metadata model with snapshots, drift and artifact sync."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.audit_log import record_event
from src.services.rentgen import artifact_graph
from src.services.rentgen.metadata_graph import _enrich_object, build_metadata_graph

ROOT = Path(__file__).resolve().parents[3]
STORE_PATH = ROOT / "data" / "canonical_metadata.json"

DATA_TYPES = {
    "Catalog",
    "Document",
    "InformationRegister",
    "AccumulationRegister",
    "AccountingRegister",
    "CalculationRegister",
    "Constant",
    "ChartOfAccounts",
    "ChartOfCharacteristicTypes",
    "ChartOfCalculationTypes",
    "Sequence",
    "DocumentJournal",
}
EXCHANGE_TYPES = {
    "ExchangePlan",
    "ExternalDataSource",
    "IntegrationService",
    "HTTPService",
    "WebService",
    "WSReference",
    "XDTOPackage",
}
ROLE_TYPES = {"Role"}
FORM_TYPES = {"CommonForm"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _load(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    target = path or STORE_PATH
    if not target.exists():
        return {"snapshots": [], "objects": []}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"snapshots": [], "objects": []}
    if not isinstance(payload, dict):
        return {"snapshots": [], "objects": []}
    return {
        "snapshots": payload.get("snapshots", [])
        if isinstance(payload.get("snapshots"), list)
        else [],
        "objects": payload.get("objects", [])
        if isinstance(payload.get("objects"), list)
        else [],
    }


def _write(payload: dict[str, list[dict[str, Any]]], path: Path | None = None) -> None:
    target = path or STORE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def _audit_path(path: Path | None = None) -> Path:
    return (path or STORE_PATH).parent / "audit_log.ndjson"


def _audit(
    action: str, *, target: str, metadata: dict[str, Any], path: Path | None = None
) -> None:
    try:
        record_event(
            action=action,
            target=target,
            category="metadata",
            metadata=metadata,
            path=_audit_path(path),
        )
    except Exception:
        return


def _id(prefix: str, value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"{prefix}_" + hashlib.sha1(encoded).hexdigest()[:16]


def _fingerprint(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _group(metadata_type: str) -> str:
    if metadata_type in ROLE_TYPES:
        return "security"
    if metadata_type in FORM_TYPES or metadata_type.endswith("Form"):
        return "ui"
    if metadata_type in EXCHANGE_TYPES:
        return "integration"
    if metadata_type in DATA_TYPES:
        return "data"
    return "support"


def _artifact_type(metadata_type: str) -> str:
    if metadata_type == "Role":
        return "role"
    if metadata_type in FORM_TYPES or metadata_type.endswith("Form"):
        return "form"
    return "metadata_object"


def _module_id(module_path: str) -> str:
    return _id("bsl", module_path)


def _form_id(form_path: str) -> str:
    return _id("form", form_path)


def _rights_summary(
    rights: dict[str, Any] | None, rights_path: str | None
) -> dict[str, Any]:
    rights = rights or {}
    return {
        "path": rights.get("path") or rights_path,
        "objects": int(rights.get("objects") or 0),
        "rights": int(rights.get("rights") or 0),
        "dangerous_total": int(rights.get("dangerous_total") or 0),
        "dangerous": list(rights.get("dangerous") or [])[:30],
        "by_right": dict(rights.get("by_right") or {}),
    }


def _canonical_object(
    graph: dict[str, Any], raw: dict[str, Any], *, snapshot_id: str, imported_at: str
) -> dict[str, Any]:
    enriched = _enrich_object(graph, raw)
    stable = {
        "ref": enriched["ref"],
        "type": enriched["type"],
        "name": enriched.get("name"),
        "synonym": enriched.get("synonym"),
        "uuid": enriched.get("uuid"),
        "path": enriched.get("path"),
        "modules": enriched.get("modules") or [],
        "forms": enriched.get("forms") or [],
        "commands": enriched.get("commands") or [],
        "attributes": enriched.get("attributes") or [],
        "tabular_sections": enriched.get("tabular_sections") or [],
        "dimensions": enriched.get("dimensions") or [],
        "resources": enriched.get("resources") or [],
        "references": enriched.get("references") or [],
        "rights": _rights_summary(enriched.get("rights"), enriched.get("rights_path")),
        "counts": enriched.get("counts") or {},
    }
    return {
        "id": _id("meta", enriched["ref"]),
        "snapshot_id": snapshot_id,
        "imported_at": imported_at,
        "source": "edt",
        "group": _group(enriched["type"]),
        **stable,
        "fingerprint": _fingerprint(stable),
    }


def _snapshot_preview(obj: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": obj["id"],
        "ref": obj["ref"],
        "type": obj["type"],
        "name": obj["name"],
        "path": obj["path"],
        "group": obj["group"],
        "fingerprint": obj["fingerprint"],
        "counts": obj.get("counts") or {},
        "rights": obj.get("rights") or {},
        "modules": [module["path"] for module in obj.get("modules", [])],
        "forms": [form["path"] for form in obj.get("forms", [])],
        "commands": [command["path"] for command in obj.get("commands", [])],
    }


def _sync_to_artifacts(
    objects: list[dict[str, Any]], *, artifact_path: Path | None = None
) -> dict[str, Any]:
    sync = {"artifacts": 0, "links": 0, "errors": []}
    for obj in objects:
        try:
            artifact_graph.create_artifact(
                {
                    "id": obj["id"],
                    "type": _artifact_type(obj["type"]),
                    "title": obj["ref"],
                    "description": obj.get("synonym") or "",
                    "status": "imported",
                    "source": "canonical_metadata",
                    "attributes": {
                        "metadata_type": obj["type"],
                        "path": obj["path"],
                        "group": obj["group"],
                        "counts": obj.get("counts") or {},
                        "fingerprint": obj["fingerprint"],
                    },
                },
                path=artifact_path,
            )
            sync["artifacts"] += 1
        except (KeyError, ValueError) as exc:
            sync["errors"].append(str(exc))
            continue

        for module in obj.get("modules", []):
            module_path = module.get("path")
            if not module_path:
                continue
            module_id = _module_id(module_path)
            try:
                artifact_graph.create_artifact(
                    {
                        "id": module_id,
                        "type": "bsl_module",
                        "title": module_path,
                        "status": "imported",
                        "source": "canonical_metadata",
                        "attributes": module,
                    },
                    path=artifact_path,
                )
                artifact_graph.link_artifacts(
                    source_id=obj["id"],
                    target_id=module_id,
                    link_type="relates_to",
                    rationale="Metadata object owns or uses this BSL module.",
                    path=artifact_path,
                )
                sync["artifacts"] += 1
                sync["links"] += 1
            except (KeyError, ValueError) as exc:
                sync["errors"].append(str(exc))

        for form in obj.get("forms", []):
            form_path = form.get("path")
            if not form_path:
                continue
            form_id = _form_id(form_path)
            try:
                artifact_graph.create_artifact(
                    {
                        "id": form_id,
                        "type": "form",
                        "title": form.get("name") or form_path,
                        "status": "imported",
                        "source": "canonical_metadata",
                        "attributes": form,
                    },
                    path=artifact_path,
                )
                artifact_graph.link_artifacts(
                    source_id=obj["id"],
                    target_id=form_id,
                    link_type="relates_to",
                    rationale="Metadata object includes this form.",
                    path=artifact_path,
                )
                sync["artifacts"] += 1
                sync["links"] += 1
            except (KeyError, ValueError) as exc:
                sync["errors"].append(str(exc))
    return sync


def import_metadata_snapshot(
    *,
    config_path: str | None = None,
    name: str | None = None,
    source: str = "edt",
    path: Path | None = None,
    artifact_path: Path | None = None,
    refresh: bool = True,
) -> dict[str, Any]:
    """Import EDT metadata into the canonical metadata store."""

    if refresh:
        build_metadata_graph.cache_clear()
    graph = build_metadata_graph(config_path)
    if not graph["available"]:
        raise FileNotFoundError(
            f"Metadata configuration path not found: {graph['config_path']}"
        )

    imported_at = _now()
    snapshot_id = _id(
        "msnap", {"config_path": graph["config_path"], "name": name, "at": imported_at}
    )
    objects = [
        _canonical_object(graph, raw, snapshot_id=snapshot_id, imported_at=imported_at)
        for raw in graph["objects"]
    ]
    by_type = Counter(obj["type"] for obj in objects)
    by_group = Counter(obj["group"] for obj in objects)
    snapshot_objects = [_snapshot_preview(obj) for obj in objects]
    evidence_hash = _fingerprint(snapshot_objects)
    snapshot = {
        "id": snapshot_id,
        "name": _clean(name, limit=160)
        or graph["configuration"].get("name")
        or "metadata",
        "source": _clean(source, limit=80) or "edt",
        "config_path": graph["config_path"],
        "created_at": imported_at,
        "configuration": graph["configuration"],
        "summary": {
            "objects": len(objects),
            "by_type": dict(by_type),
            "by_group": dict(by_group),
            "modules": sum(len(obj.get("modules", [])) for obj in objects),
            "forms": sum(len(obj.get("forms", [])) for obj in objects),
            "dangerous_rights": sum(
                int((obj.get("rights") or {}).get("dangerous_total") or 0)
                for obj in objects
            ),
        },
        "object_ids": [obj["id"] for obj in objects],
        "objects": snapshot_objects,
        "evidence_hash": evidence_hash,
    }

    payload = _load(path)
    latest_by_id = {obj["id"]: obj for obj in payload["objects"]}
    latest_by_id.update({obj["id"]: obj for obj in objects})
    snapshots = [item for item in payload["snapshots"] if item.get("id") != snapshot_id]
    snapshots.insert(0, snapshot)
    _write({"snapshots": snapshots[:200], "objects": list(latest_by_id.values())}, path)
    sync = _sync_to_artifacts(objects, artifact_path=artifact_path)
    snapshot["artifact_sync"] = sync
    payload = _load(path)
    payload["snapshots"] = [
        snapshot if item.get("id") == snapshot_id else item
        for item in payload["snapshots"]
    ]
    _write(payload, path)
    _audit(
        "metadata.canonical.import",
        target=snapshot_id,
        metadata={
            "name": snapshot["name"],
            "summary": snapshot["summary"],
            "config_path": graph["config_path"],
        },
        path=path,
    )
    return snapshot


def list_metadata_objects(
    *,
    metadata_type: str | None = None,
    group: str | None = None,
    query: str | None = None,
    limit: int = 100,
    path: Path | None = None,
) -> dict[str, Any]:
    payload = _load(path)
    items = payload["objects"]
    if metadata_type:
        items = [item for item in items if item.get("type") == metadata_type]
    if group:
        items = [item for item in items if item.get("group") == group]
    if query:
        needle = query.casefold()
        items = [
            item
            for item in items
            if needle
            in " ".join(
                [
                    str(item.get("ref") or ""),
                    str(item.get("name") or ""),
                    str(item.get("path") or ""),
                ]
            ).casefold()
        ]
    items.sort(key=lambda item: (item.get("type", ""), item.get("ref", "")))
    return {
        "items": items[: max(1, limit)],
        "total": len(items),
        "path": str(path or STORE_PATH),
    }


def get_canonical_object(
    identifier: str, *, path: Path | None = None
) -> dict[str, Any] | None:
    needle = identifier.casefold().replace("\\", "/")
    for item in _load(path)["objects"]:
        candidates = {
            str(item.get("id") or "").casefold(),
            str(item.get("ref") or "").casefold(),
            str(item.get("path") or "").casefold(),
            str(item.get("name") or "").casefold(),
        }
        if needle in candidates:
            return item
    return None


def list_metadata_snapshots(
    *, limit: int = 50, path: Path | None = None
) -> dict[str, Any]:
    items = _load(path)["snapshots"]
    return {
        "items": items[: max(1, limit)],
        "total": len(items),
        "path": str(path or STORE_PATH),
    }


def _snapshot(snapshot_id: str, *, path: Path | None = None) -> dict[str, Any]:
    for item in _load(path)["snapshots"]:
        if item.get("id") == snapshot_id:
            return item
    raise KeyError(f"Canonical metadata snapshot not found: {snapshot_id}")


def _latest_snapshot(*, path: Path | None = None) -> dict[str, Any] | None:
    items = _load(path)["snapshots"]
    return items[0] if items else None


def _object_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {obj["ref"]: obj for obj in snapshot.get("objects", [])}


def diff_metadata(
    *,
    before_id: str,
    after_id: str | None = None,
    limit: int = 200,
    path: Path | None = None,
) -> dict[str, Any]:
    before = _snapshot(before_id, path=path)
    after = _snapshot(after_id, path=path) if after_id else _latest_snapshot(path=path)
    if after is None:
        raise KeyError("No canonical metadata snapshots available")

    before_map = _object_map(before)
    after_map = _object_map(after)
    before_refs = set(before_map)
    after_refs = set(after_map)
    added_refs = sorted(after_refs - before_refs)
    removed_refs = sorted(before_refs - after_refs)
    changed = []
    for ref in sorted(before_refs & after_refs):
        old = before_map[ref]
        new = after_map[ref]
        if old.get("fingerprint") == new.get("fingerprint"):
            continue
        changes = {}
        for key in ("counts", "modules", "forms", "commands", "rights"):
            if old.get(key) != new.get(key):
                changes[key] = {"before": old.get(key), "after": new.get(key)}
        changed.append(
            {
                "ref": ref,
                "type": new.get("type"),
                "name": new.get("name"),
                "changes": changes,
            }
        )

    return {
        "before": {
            "id": before["id"],
            "created_at": before.get("created_at"),
            "summary": before.get("summary", {}),
        },
        "after": {
            "id": after["id"],
            "created_at": after.get("created_at"),
            "summary": after.get("summary", {}),
        },
        "summary": {
            "added": len(added_refs),
            "removed": len(removed_refs),
            "changed": len(changed),
        },
        "added": [after_map[ref] for ref in added_refs[:limit]],
        "removed": [before_map[ref] for ref in removed_refs[:limit]],
        "changed": changed[:limit],
    }


def diff_rights(
    *,
    before_id: str,
    after_id: str | None = None,
    limit: int = 200,
    path: Path | None = None,
) -> dict[str, Any]:
    drift = diff_metadata(
        before_id=before_id, after_id=after_id, limit=limit, path=path
    )
    rights_changes = []
    for item in drift["changed"]:
        if "rights" in item.get("changes", {}):
            rights_changes.append(item)
    added_roles = [item for item in drift["added"] if item.get("type") == "Role"]
    removed_roles = [item for item in drift["removed"] if item.get("type") == "Role"]
    return {
        "before": drift["before"],
        "after": drift["after"],
        "summary": {
            "changed_roles": len(rights_changes),
            "added_roles": len(added_roles),
            "removed_roles": len(removed_roles),
            "dangerous_rights_after": drift["after"]["summary"].get(
                "dangerous_rights", 0
            ),
        },
        "changed": rights_changes[:limit],
        "added_roles": added_roles[:limit],
        "removed_roles": removed_roles[:limit],
    }
