"""Internal ALM artifact graph for 1cAI enterprise governance."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.audit_log import record_event


ROOT = Path(__file__).resolve().parents[3]
STORE_PATH = ROOT / "data" / "artifact_graph.json"

ARTIFACT_TYPES = {
    "need",
    "requirement",
    "capability",
    "architecture_element",
    "work_item",
    "change_set",
    "metadata_object",
    "bsl_module",
    "form",
    "role",
    "query",
    "test_case",
    "test_run",
    "defect",
    "release",
    "incident",
    "approval",
    "waiver",
    "baseline",
    "review_pack",
}

LINK_TYPES = {
    "relates_to",
    "refines",
    "satisfies",
    "implements",
    "impacts",
    "verifies",
    "tested_by",
    "blocks",
    "depends_on",
    "owns",
    "approves",
    "waives",
    "released_in",
    "caused_by",
    "mitigates",
}

DEFAULT_STATUSES = {
    "draft",
    "reviewed",
    "approved",
    "baselined",
    "changed",
    "deprecated",
    "open",
    "closed",
    "rejected",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _safe_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_clean(value, limit=120) for value in values if _clean(value, limit=120)]


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _load(path: Path | None = None) -> dict[str, list[dict[str, Any]]]:
    target = path or STORE_PATH
    if not target.exists():
        return {"artifacts": [], "links": []}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"artifacts": [], "links": []}
    if not isinstance(payload, dict):
        return {"artifacts": [], "links": []}
    artifacts = payload.get("artifacts", [])
    links = payload.get("links", [])
    return {
        "artifacts": artifacts if isinstance(artifacts, list) else [],
        "links": links if isinstance(links, list) else [],
    }


def _write(payload: dict[str, list[dict[str, Any]]], path: Path | None = None) -> None:
    target = path or STORE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def _audit_path(path: Path | None = None) -> Path:
    return (path or STORE_PATH).parent / "audit_log.ndjson"


def _audit(action: str, *, target: str, metadata: dict[str, Any], path: Path | None = None) -> None:
    try:
        record_event(
            action=action,
            target=target,
            category="artifact",
            metadata=metadata,
            path=_audit_path(path),
        )
    except Exception:
        return


def _artifact_id(artifact_type: str, title: str, created_at: str, external_id: str | None = None) -> str:
    if external_id:
        return _clean(external_id, limit=120)
    source = "\n".join([artifact_type, title, created_at])
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]
    return f"art_{artifact_type}_{digest}"


def _link_id(source_id: str, target_id: str, link_type: str) -> str:
    source = "\n".join([source_id, target_id, link_type])
    return "lnk_" + hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


def _artifact_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in items if item.get("id")}


def _validate_artifact_type(value: str) -> str:
    artifact_type = _clean(value, limit=80)
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(f"Unsupported artifact type: {value}")
    return artifact_type


def _validate_link_type(value: str) -> str:
    link_type = _clean(value, limit=80)
    if link_type not in LINK_TYPES:
        raise ValueError(f"Unsupported link type: {value}")
    return link_type


def _normalize_artifact(
    data: dict[str, Any],
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    artifact_type = _validate_artifact_type(data.get("type") or existing.get("type") if existing else data.get("type"))
    title = _clean(data.get("title") if data.get("title") is not None else (existing or {}).get("title"), limit=240)
    if not title:
        raise ValueError("Artifact title is required")

    created_at = str((existing or {}).get("created_at") or now)
    artifact_id = str((existing or {}).get("id") or _artifact_id(artifact_type, title, created_at, data.get("id")))
    version = int((existing or {}).get("version") or 0) + (1 if existing else 0)

    return {
        "id": artifact_id,
        "type": artifact_type,
        "title": title,
        "description": _clean(
            data.get("description") if data.get("description") is not None else (existing or {}).get("description"),
            limit=4000,
        ),
        "status": _clean(data.get("status") if data.get("status") is not None else (existing or {}).get("status"), limit=80)
        or "draft",
        "owner": _clean(data.get("owner") if data.get("owner") is not None else (existing or {}).get("owner"), limit=160),
        "risk": _clean(data.get("risk") if data.get("risk") is not None else (existing or {}).get("risk"), limit=40),
        "priority": _clean(
            data.get("priority") if data.get("priority") is not None else (existing or {}).get("priority"),
            limit=40,
        ),
        "tags": _safe_list(data.get("tags") if data.get("tags") is not None else (existing or {}).get("tags")),
        "source": _clean(data.get("source") if data.get("source") is not None else (existing or {}).get("source"), limit=240),
        "version": max(1, version),
        "attributes": {
            **_safe_dict((existing or {}).get("attributes")),
            **_safe_dict(data.get("attributes")),
        },
        "created_at": created_at,
        "updated_at": now,
    }


def create_artifact(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    """Create or upsert an artifact in the local graph store."""

    payload = _load(path)
    requested_id = _clean(data.get("id"), limit=120)
    existing = None
    if requested_id:
        existing = next((item for item in payload["artifacts"] if item.get("id") == requested_id), None)
    artifact = _normalize_artifact(data, existing=existing)
    items = [item for item in payload["artifacts"] if item.get("id") != artifact["id"]]
    items.insert(0, artifact)
    payload["artifacts"] = items
    _write(payload, path)
    _audit(
        "artifact.upsert",
        target=artifact["id"],
        metadata={"type": artifact["type"], "title": artifact["title"], "version": artifact["version"]},
        path=path,
    )
    return artifact


def update_artifact(artifact_id: str, patch: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    """Patch an artifact while preserving id, creation time and unknown attributes."""

    payload = _load(path)
    for index, item in enumerate(payload["artifacts"]):
        if item.get("id") != artifact_id:
            continue
        updated = _normalize_artifact({**item, **patch, "id": artifact_id}, existing=item)
        payload["artifacts"][index] = updated
        _write(payload, path)
        _audit(
            "artifact.update",
            target=artifact_id,
            metadata={"type": updated["type"], "title": updated["title"], "version": updated["version"]},
            path=path,
        )
        return updated
    raise KeyError(f"Artifact not found: {artifact_id}")


def get_artifact(artifact_id: str, *, path: Path | None = None) -> dict[str, Any] | None:
    """Return one artifact by id."""

    for item in _load(path)["artifacts"]:
        if item.get("id") == artifact_id:
            return item
    return None


def list_artifacts(
    *,
    artifact_type: str | None = None,
    status: str | None = None,
    owner: str | None = None,
    query: str | None = None,
    limit: int = 100,
    path: Path | None = None,
) -> dict[str, Any]:
    """List artifacts with lightweight filters."""

    items = _load(path)["artifacts"]
    if artifact_type:
        items = [item for item in items if item.get("type") == artifact_type]
    if status:
        items = [item for item in items if item.get("status") == status]
    if owner:
        folded = owner.casefold()
        items = [item for item in items if folded in str(item.get("owner") or "").casefold()]
    if query:
        folded_query = query.casefold()
        items = [
            item
            for item in items
            if folded_query in " ".join(
                [
                    str(item.get("id") or ""),
                    str(item.get("title") or ""),
                    str(item.get("description") or ""),
                    " ".join(item.get("tags") or []),
                ]
            ).casefold()
        ]
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"items": items[: max(1, limit)], "total": len(items), "path": str(path or STORE_PATH)}


def link_artifacts(
    *,
    source_id: str,
    target_id: str,
    link_type: str,
    rationale: str | None = None,
    status: str = "active",
    suspect: bool = False,
    attributes: dict[str, Any] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Create or update a directed traceability link between two artifacts."""

    payload = _load(path)
    artifacts = _artifact_index(payload["artifacts"])
    if source_id not in artifacts:
        raise KeyError(f"Source artifact not found: {source_id}")
    if target_id not in artifacts:
        raise KeyError(f"Target artifact not found: {target_id}")

    clean_type = _validate_link_type(link_type)
    link_id = _link_id(source_id, target_id, clean_type)
    now = _now()
    existing = next((item for item in payload["links"] if item.get("id") == link_id), None)
    link = {
        "id": link_id,
        "source_id": source_id,
        "target_id": target_id,
        "type": clean_type,
        "status": _clean(status, limit=80) or "active",
        "suspect": bool(suspect),
        "rationale": _clean(rationale, limit=1000),
        "attributes": {**_safe_dict((existing or {}).get("attributes")), **_safe_dict(attributes)},
        "created_at": (existing or {}).get("created_at") or now,
        "updated_at": now,
    }
    payload["links"] = [item for item in payload["links"] if item.get("id") != link_id]
    payload["links"].insert(0, link)
    _write(payload, path)
    _audit(
        "artifact.link",
        target=link_id,
        metadata={"source_id": source_id, "target_id": target_id, "type": clean_type, "suspect": bool(suspect)},
        path=path,
    )
    return link


def trace_artifact(
    artifact_id: str,
    *,
    depth: int = 4,
    direction: str = "both",
    path: Path | None = None,
) -> dict[str, Any]:
    """Traverse artifact links around one artifact."""

    payload = _load(path)
    artifacts = _artifact_index(payload["artifacts"])
    if artifact_id not in artifacts:
        raise KeyError(f"Artifact not found: {artifact_id}")

    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in payload["links"]:
        outgoing[str(link.get("source_id"))].append(link)
        incoming[str(link.get("target_id"))].append(link)

    max_depth = max(0, min(int(depth), 12))
    visited = {artifact_id}
    queue = deque([(artifact_id, 0)])
    result_links: dict[str, dict[str, Any]] = {}

    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= max_depth:
            continue
        candidates: list[tuple[dict[str, Any], str]] = []
        if direction in {"out", "both"}:
            candidates.extend((link, str(link.get("target_id"))) for link in outgoing.get(current, []))
        if direction in {"in", "both"}:
            candidates.extend((link, str(link.get("source_id"))) for link in incoming.get(current, []))
        for link, neighbor in candidates:
            if neighbor not in artifacts:
                continue
            result_links[str(link["id"])] = link
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, current_depth + 1))

    nodes = [artifacts[item_id] for item_id in visited if item_id in artifacts]
    nodes.sort(key=lambda item: (item.get("type", ""), item.get("title", "")))
    return {
        "root": artifacts[artifact_id],
        "nodes": nodes,
        "links": list(result_links.values()),
        "summary": {
            "nodes": len(nodes),
            "links": len(result_links),
            "suspect_links": sum(1 for link in result_links.values() if link.get("suspect")),
            "depth": max_depth,
            "direction": direction,
        },
    }


def coverage_matrix(*, path: Path | None = None) -> dict[str, Any]:
    """Build a requirements-oriented coverage matrix from artifact links."""

    payload = _load(path)
    artifacts = _artifact_index(payload["artifacts"])
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for link in payload["links"]:
        outgoing[str(link.get("source_id"))].append(link)

    rows = []
    for artifact in payload["artifacts"]:
        if artifact.get("type") not in {"need", "requirement", "capability"}:
            continue
        linked = [artifacts.get(str(link.get("target_id"))) for link in outgoing.get(str(artifact["id"]), [])]
        linked = [item for item in linked if item]
        by_type = CounterLike(linked)
        rows.append(
            {
                "artifact_id": artifact["id"],
                "type": artifact["type"],
                "title": artifact["title"],
                "status": artifact.get("status"),
                "owner": artifact.get("owner"),
                "linked": {
                    "architecture": by_type.get("architecture_element"),
                    "work_items": by_type.get("work_item"),
                    "change_sets": by_type.get("change_set"),
                    "metadata_objects": by_type.get("metadata_object"),
                    "bsl_modules": by_type.get("bsl_module"),
                    "test_cases": by_type.get("test_case"),
                    "test_runs": by_type.get("test_run"),
                    "releases": by_type.get("release"),
                    "defects": by_type.get("defect"),
                },
                "coverage": _coverage_status(by_type),
                "suspect_links": sum(1 for link in outgoing.get(str(artifact["id"]), []) if link.get("suspect")),
            }
        )

    summary = {
        "rows": len(rows),
        "covered": sum(1 for row in rows if row["coverage"] == "covered"),
        "partial": sum(1 for row in rows if row["coverage"] == "partial"),
        "gaps": sum(1 for row in rows if row["coverage"] == "gap"),
        "suspect_rows": sum(1 for row in rows if row["suspect_links"]),
        "artifacts": len(payload["artifacts"]),
        "links": len(payload["links"]),
    }
    return {"summary": summary, "rows": rows, "path": str(path or STORE_PATH)}


def CounterLike(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[str(item.get("type") or "unknown")] += 1
    return counts


def _coverage_status(counts: dict[str, int]) -> str:
    has_implementation = bool(
        counts.get("work_item")
        or counts.get("change_set")
        or counts.get("metadata_object")
        or counts.get("bsl_module")
    )
    has_verification = bool(counts.get("test_case") or counts.get("test_run"))
    if has_implementation and has_verification:
        return "covered"
    if has_implementation or has_verification or counts:
        return "partial"
    return "gap"


def health(*, path: Path | None = None) -> dict[str, Any]:
    """Return local graph store status."""

    payload = _load(path)
    by_type = CounterLike(payload["artifacts"])
    return {
        "status": "ok",
        "path": str(path or STORE_PATH),
        "artifacts": len(payload["artifacts"]),
        "links": len(payload["links"]),
        "by_type": dict(sorted(by_type.items())),
        "supported_types": sorted(ARTIFACT_TYPES),
        "supported_link_types": sorted(LINK_TYPES),
    }
