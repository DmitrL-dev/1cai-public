"""Baselines and review packs for internal ALM governance."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen import artifact_graph

ROOT = Path(__file__).resolve().parents[3]
BASELINES_PATH = ROOT / "data" / "baselines.json"
REVIEW_PACKS_PATH = ROOT / "data" / "review_packs.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _safe_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_clean(item, limit=260) for item in values if _clean(item, limit=260)]


def _load(path: Path, key: str = "items") -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload.get(key, []) if isinstance(payload, dict) else payload
    return items if isinstance(items, list) else []


def _write(path: Path, items: list[dict[str, Any]], key: str = "items") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps({key: items}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(path)


def _id(
    prefix: str, title: str, created_at: str, explicit_id: str | None = None
) -> str:
    if explicit_id:
        return _clean(explicit_id, limit=120)
    digest = hashlib.sha1(f"{title}\n{created_at}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _artifact_path_for_store(
    path: Path | None, artifact_path: Path | None
) -> Path | None:
    if artifact_path is not None:
        return artifact_path
    if path is not None:
        return path.parent / "artifact_graph.json"
    return None


def _require_artifacts(
    artifact_ids: list[str], artifact_path: Path | None
) -> list[dict[str, Any]]:
    artifacts = []
    missing = []
    for artifact_id in artifact_ids:
        artifact = artifact_graph.get_artifact(artifact_id, path=artifact_path)
        if artifact is None:
            missing.append(artifact_id)
        else:
            artifacts.append(artifact)
    if missing:
        raise KeyError(f"Artifacts not found: {', '.join(missing)}")
    return artifacts


def create_baseline(
    *,
    title: str,
    artifact_ids: list[str],
    description: str | None = None,
    owner: str | None = None,
    release_id: str | None = None,
    change_set_ids: list[str] | None = None,
    baseline_id: str | None = None,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Create an immutable baseline snapshot for selected artifacts."""

    target = path or BASELINES_PATH
    graph_path = _artifact_path_for_store(path, artifact_path)
    ids = _safe_list(artifact_ids)
    if not ids:
        raise ValueError("Baseline requires at least one artifact id")
    artifacts = _require_artifacts(ids, graph_path)
    created_at = _now()
    record_id = _id("base", title, created_at, baseline_id)
    if any(item.get("id") == record_id for item in _load(target)):
        raise ValueError(f"Baseline already exists and is immutable: {record_id}")
    snapshot = {
        "artifacts": artifacts,
        "artifact_ids": ids,
        "release_id": _clean(release_id, limit=160) or None,
        "change_set_ids": _safe_list(change_set_ids),
    }
    record = {
        "id": record_id,
        "title": _clean(title, limit=240),
        "description": _clean(description, limit=4000),
        "owner": _clean(owner, limit=160),
        "status": "sealed",
        "snapshot": snapshot,
        "evidence_hash": _hash(snapshot),
        "created_at": created_at,
        "updated_at": created_at,
    }
    items = [item for item in _load(target) if item.get("id") != record["id"]]
    items.insert(0, record)
    _write(target, items)
    sync_baseline_to_artifacts(record, artifact_path=graph_path)
    return record


def sync_baseline_to_artifacts(
    record: dict[str, Any], *, artifact_path: Path | None = None
) -> dict[str, Any]:
    """Project a baseline into the internal artifact graph."""

    sync = {"artifact_id": record["id"], "links": 0, "errors": []}
    try:
        artifact_graph.create_artifact(
            {
                "id": record["id"],
                "type": "baseline",
                "title": record["title"],
                "description": record.get("description") or "",
                "status": record.get("status") or "sealed",
                "owner": record.get("owner") or "",
                "source": "baselines",
                "attributes": {
                    "evidence_hash": record.get("evidence_hash"),
                    "artifact_ids": (record.get("snapshot") or {}).get(
                        "artifact_ids", []
                    ),
                    "release_id": (record.get("snapshot") or {}).get("release_id"),
                    "change_set_ids": (record.get("snapshot") or {}).get(
                        "change_set_ids", []
                    ),
                },
            },
            path=artifact_path,
        )
        for artifact_id in (record.get("snapshot") or {}).get("artifact_ids", []):
            artifact_graph.link_artifacts(
                source_id=record["id"],
                target_id=artifact_id,
                link_type="relates_to",
                rationale="Baseline seals this artifact state.",
                path=artifact_path,
            )
            sync["links"] += 1
    except (KeyError, ValueError) as exc:
        sync["errors"].append(str(exc))
    return sync


def list_baselines(*, limit: int = 100, path: Path | None = None) -> dict[str, Any]:
    target = path or BASELINES_PATH
    items = _load(target)
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"items": items[: max(1, limit)], "total": len(items), "path": str(target)}


def get_baseline(
    baseline_id: str, *, path: Path | None = None
) -> dict[str, Any] | None:
    for item in _load(path or BASELINES_PATH):
        if item.get("id") == baseline_id:
            return item
    return None


def create_review_pack(
    *,
    title: str,
    artifact_ids: list[str],
    reviewers: list[str] | None = None,
    description: str | None = None,
    owner: str | None = None,
    review_pack_id: str | None = None,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Create a review pack with a fixed artifact set."""

    target = path or REVIEW_PACKS_PATH
    graph_path = _artifact_path_for_store(path, artifact_path)
    ids = _safe_list(artifact_ids)
    if not ids:
        raise ValueError("Review pack requires at least one artifact id")
    artifacts = _require_artifacts(ids, graph_path)
    created_at = _now()
    record = {
        "id": _id("rp", title, created_at, review_pack_id),
        "title": _clean(title, limit=240),
        "description": _clean(description, limit=4000),
        "owner": _clean(owner, limit=160),
        "reviewers": _safe_list(reviewers),
        "status": "open",
        "artifact_ids": ids,
        "artifact_snapshot": artifacts,
        "comments": [],
        "decisions": [],
        "evidence_hash": _hash({"artifact_ids": ids, "artifacts": artifacts}),
        "created_at": created_at,
        "updated_at": created_at,
    }
    items = [item for item in _load(target) if item.get("id") != record["id"]]
    items.insert(0, record)
    _write(target, items)
    sync_review_pack_to_artifacts(record, artifact_path=graph_path)
    return record


def sync_review_pack_to_artifacts(
    record: dict[str, Any], *, artifact_path: Path | None = None
) -> dict[str, Any]:
    """Project a review pack into the internal artifact graph."""

    sync = {"artifact_id": record["id"], "links": 0, "errors": []}
    try:
        artifact_graph.create_artifact(
            {
                "id": record["id"],
                "type": "review_pack",
                "title": record["title"],
                "description": record.get("description") or "",
                "status": record.get("status") or "open",
                "owner": record.get("owner") or "",
                "source": "review_packs",
                "attributes": {
                    "reviewers": record.get("reviewers", []),
                    "artifact_ids": record.get("artifact_ids", []),
                    "evidence_hash": record.get("evidence_hash"),
                },
            },
            path=artifact_path,
        )
        for artifact_id in record.get("artifact_ids", []):
            artifact_graph.link_artifacts(
                source_id=record["id"],
                target_id=artifact_id,
                link_type="relates_to",
                rationale="Review pack includes this artifact.",
                path=artifact_path,
            )
            sync["links"] += 1
    except (KeyError, ValueError) as exc:
        sync["errors"].append(str(exc))
    return sync


def list_review_packs(
    *, status: str | None = None, limit: int = 100, path: Path | None = None
) -> dict[str, Any]:
    target = path or REVIEW_PACKS_PATH
    items = _load(target)
    if status:
        items = [item for item in items if item.get("status") == status]
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"items": items[: max(1, limit)], "total": len(items), "path": str(target)}


def get_review_pack(
    review_pack_id: str, *, path: Path | None = None
) -> dict[str, Any] | None:
    for item in _load(path or REVIEW_PACKS_PATH):
        if item.get("id") == review_pack_id:
            return item
    return None


def add_review_comment(
    review_pack_id: str,
    *,
    actor: str,
    message: str,
    artifact_id: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Append a comment to a review pack."""

    target = path or REVIEW_PACKS_PATH
    items = _load(target)
    for index, item in enumerate(items):
        if item.get("id") != review_pack_id:
            continue
        updated = dict(item)
        now = _now()
        comments = list(updated.get("comments") or [])
        comments.insert(
            0,
            {
                "at": now,
                "actor": _clean(actor, limit=160) or "system",
                "artifact_id": _clean(artifact_id, limit=160) or None,
                "message": _clean(message, limit=2000),
            },
        )
        updated["comments"] = comments
        updated["updated_at"] = now
        items[index] = updated
        _write(target, items)
        return updated
    raise KeyError(f"Review pack not found: {review_pack_id}")


def decide_review_pack(
    review_pack_id: str,
    *,
    actor: str,
    decision: str,
    reason: str | None = None,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Approve or reject a review pack."""

    clean_decision = decision.strip().lower()
    if clean_decision not in {"approved", "rejected"}:
        raise ValueError("Review pack decision must be approved or rejected")
    target = path or REVIEW_PACKS_PATH
    graph_path = _artifact_path_for_store(path, artifact_path)
    items = _load(target)
    for index, item in enumerate(items):
        if item.get("id") != review_pack_id:
            continue
        updated = dict(item)
        now = _now()
        decisions = list(updated.get("decisions") or [])
        decisions.insert(
            0,
            {
                "at": now,
                "actor": _clean(actor, limit=160) or "system",
                "decision": clean_decision,
                "reason": _clean(reason, limit=1000),
            },
        )
        updated["decisions"] = decisions
        updated["status"] = clean_decision
        updated["updated_at"] = now
        items[index] = updated
        _write(target, items)
        sync_review_pack_to_artifacts(updated, artifact_path=graph_path)
        return updated
    raise KeyError(f"Review pack not found: {review_pack_id}")
