"""Internal change-set workflow for 1cAI delivery governance."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen import artifact_graph
from src.services.rentgen.change_plan import build_change_plan, dedupe, extract_diff_modules
from src.services.rentgen.policy_engine import evaluate_policy
from src.services.rentgen.release_readiness import build_release_readiness
from src.services.rentgen.test_coverage_matrix import build_test_coverage_matrix
from src.services.rentgen.test_evidence import summarize_test_evidence


ROOT = Path(__file__).resolve().parents[3]
STORE_PATH = ROOT / "data" / "change_sets.json"

STATUSES = {
    "draft",
    "impact_analyzed",
    "tests_selected",
    "review_ready",
    "approved",
    "merged",
    "released",
    "rejected",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _safe_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_clean(item, limit=260) for item in values if _clean(item, limit=260)]


def _load(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or STORE_PATH
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    return items if isinstance(items, list) else []


def _write(items: list[dict[str, Any]], path: Path | None = None) -> None:
    target = path or STORE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def _artifact_path_for_store(path: Path | None, artifact_path: Path | None) -> Path | None:
    if artifact_path is not None:
        return artifact_path
    if path is not None:
        return path.parent / "artifact_graph.json"
    return None


def _test_evidence_path_for_store(path: Path | None) -> Path | None:
    if path is not None:
        return path.parent / "test_runs.json"
    return None


def _change_set_id(title: str, created_at: str, explicit_id: str | None = None) -> str:
    if explicit_id:
        return _clean(explicit_id, limit=120)
    digest = hashlib.sha1(f"{title}\n{created_at}".encode("utf-8")).hexdigest()[:16]
    return f"chg_{digest}"


def _module_artifact_id(module_path: str) -> str:
    digest = hashlib.sha1(module_path.encode("utf-8")).hexdigest()[:16]
    return f"bsl_{digest}"


def _stable_artifact_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _normalize(data: dict[str, Any], *, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    now = _now()
    title = _clean(data.get("title") if data.get("title") is not None else (existing or {}).get("title"), limit=240)
    if not title:
        raise ValueError("Change set title is required")
    created_at = (existing or {}).get("created_at") or now
    modules = dedupe(_safe_list(data.get("changed_modules") if data.get("changed_modules") is not None else (existing or {}).get("changed_modules")))
    diff = data.get("diff") if data.get("diff") is not None else (existing or {}).get("diff")
    modules = dedupe(modules + extract_diff_modules(diff))
    status = _clean(data.get("status") if data.get("status") is not None else (existing or {}).get("status"), limit=80) or "draft"
    if status not in STATUSES:
        raise ValueError(f"Unsupported change set status: {status}")

    return {
        "id": (existing or {}).get("id") or _change_set_id(title, created_at, data.get("id")),
        "title": title,
        "description": _clean(
            data.get("description") if data.get("description") is not None else (existing or {}).get("description"),
            limit=4000,
        ),
        "status": status,
        "owner": _clean(data.get("owner") if data.get("owner") is not None else (existing or {}).get("owner"), limit=160),
        "source_requirement_ids": _safe_list(
            data.get("source_requirement_ids")
            if data.get("source_requirement_ids") is not None
            else (existing or {}).get("source_requirement_ids")
        ),
        "changed_modules": modules,
        "diff": diff or "",
        "risk_summary": data.get("risk_summary") or (existing or {}).get("risk_summary") or {},
        "change_plan": data.get("change_plan") or (existing or {}).get("change_plan") or None,
        "test_matrix": data.get("test_matrix") or (existing or {}).get("test_matrix") or None,
        "release_readiness": data.get("release_readiness") or (existing or {}).get("release_readiness") or None,
        "approval_ids": _safe_list(data.get("approval_ids") if data.get("approval_ids") is not None else (existing or {}).get("approval_ids")),
        "waiver_ids": _safe_list(data.get("waiver_ids") if data.get("waiver_ids") is not None else (existing or {}).get("waiver_ids")),
        "decision_log": list((existing or {}).get("decision_log") or []),
        "artifact_sync": data.get("artifact_sync") or (existing or {}).get("artifact_sync") or {},
        "created_at": created_at,
        "updated_at": now,
    }


def _upsert(record: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    items = [item for item in _load(path) if item.get("id") != record["id"]]
    items.insert(0, record)
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    _write(items, path)
    return record


def sync_change_set_to_artifacts(record: dict[str, Any], *, artifact_path: Path | None = None) -> dict[str, Any]:
    """Project a change set into the internal artifact graph."""

    sync = {"artifact_id": record["id"], "artifacts": 1, "links": 0, "errors": []}
    try:
        artifact_graph.create_artifact(
            {
                "id": record["id"],
                "type": "change_set",
                "title": record["title"],
                "description": record.get("description") or "",
                "status": record.get("status") or "draft",
                "owner": record.get("owner") or "",
                "risk": str((record.get("risk_summary") or {}).get("max_risk") or ""),
                "priority": "high"
                if int((record.get("risk_summary") or {}).get("max_risk") or 0) >= 70
                else "medium",
                "tags": ["change-set", "delivery"],
                "source": "change_sets",
                "attributes": {
                    "changed_modules": record.get("changed_modules", []),
                    "source_requirement_ids": record.get("source_requirement_ids", []),
                    "summary": record.get("risk_summary", {}),
                },
            },
            path=artifact_path,
        )
    except (KeyError, ValueError) as exc:
        sync["errors"].append(str(exc))

    for req_id in record.get("source_requirement_ids", []):
        try:
            if artifact_graph.get_artifact(req_id, path=artifact_path) is None:
                artifact_graph.create_artifact(
                    {
                        "id": req_id,
                        "type": "requirement",
                        "title": req_id,
                        "status": "linked",
                        "source": "change_sets",
                    },
                    path=artifact_path,
                )
                sync["artifacts"] += 1
            artifact_graph.link_artifacts(
                source_id=req_id,
                target_id=record["id"],
                link_type="implements",
                rationale="Change set implements or contributes to this requirement.",
                path=artifact_path,
            )
            sync["links"] += 1
        except (KeyError, ValueError) as exc:
            sync["errors"].append(str(exc))

    for module_path in record.get("changed_modules", []):
        artifact_id = _module_artifact_id(module_path)
        try:
            artifact_graph.create_artifact(
                {
                    "id": artifact_id,
                    "type": "bsl_module",
                    "title": module_path,
                    "status": "changed",
                    "source": "change_sets",
                    "attributes": {"module_path": module_path},
                },
                path=artifact_path,
            )
            sync["artifacts"] += 1
            artifact_graph.link_artifacts(
                source_id=record["id"],
                target_id=artifact_id,
                link_type="impacts",
                rationale="Change set declares this changed BSL module.",
                path=artifact_path,
            )
            sync["links"] += 1
        except (KeyError, ValueError) as exc:
            sync["errors"].append(str(exc))

    test_matrix = record.get("test_matrix") or {}
    for module in test_matrix.get("modules", []) if isinstance(test_matrix, dict) else []:
        for test in list(module.get("exact_tests") or []) + list(module.get("planned_tests") or []):
            selector = test.get("selector") or test.get("id") or test.get("command")
            if not selector:
                continue
            artifact_id = _stable_artifact_id("test", str(selector))
            try:
                artifact_graph.create_artifact(
                    {
                        "id": artifact_id,
                        "type": "test_case",
                        "title": str(selector),
                        "status": str(test.get("status") or "planned"),
                        "source": "change_sets",
                        "attributes": test,
                    },
                    path=artifact_path,
                )
                sync["artifacts"] += 1
                artifact_graph.link_artifacts(
                    source_id=record["id"],
                    target_id=artifact_id,
                    link_type="tested_by",
                    rationale="Change set selected this risk-driven verification test.",
                    path=artifact_path,
                )
                sync["links"] += 1
            except (KeyError, ValueError) as exc:
                sync["errors"].append(str(exc))

    readiness = record.get("release_readiness") or {}
    if isinstance(readiness, dict) and readiness.get("release_name"):
        release_id = _stable_artifact_id("rel", f"{record['id']}:{readiness['release_name']}")
        try:
            artifact_graph.create_artifact(
                {
                    "id": release_id,
                    "type": "release",
                    "title": str(readiness["release_name"]),
                    "status": str((readiness.get("decision") or {}).get("status") or "review_ready"),
                    "source": "change_sets",
                    "attributes": {
                        "change_set_id": record["id"],
                        "decision": readiness.get("decision", {}),
                        "summary": readiness.get("summary", {}),
                    },
                },
                path=artifact_path,
            )
            sync["artifacts"] += 1
            artifact_graph.link_artifacts(
                source_id=record["id"],
                target_id=release_id,
                link_type="released_in",
                rationale="Change set has an attached release-readiness report.",
                path=artifact_path,
            )
            sync["links"] += 1
        except (KeyError, ValueError) as exc:
            sync["errors"].append(str(exc))
    return sync


def create_change_set(data: dict[str, Any], *, path: Path | None = None, artifact_path: Path | None = None) -> dict[str, Any]:
    """Create or upsert a change set."""

    existing = None
    if data.get("id"):
        existing = get_change_set(str(data["id"]), path=path)
    record = _normalize(data, existing=existing)
    record["artifact_sync"] = sync_change_set_to_artifacts(record, artifact_path=_artifact_path_for_store(path, artifact_path))
    return _upsert(record, path=path)


def list_change_sets(*, status: str | None = None, owner: str | None = None, limit: int = 100, path: Path | None = None) -> dict[str, Any]:
    """List change sets with lightweight filters."""

    items = _load(path)
    if status:
        items = [item for item in items if item.get("status") == status]
    if owner:
        folded = owner.casefold()
        items = [item for item in items if folded in str(item.get("owner") or "").casefold()]
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"items": items[: max(1, limit)], "total": len(items), "path": str(path or STORE_PATH)}


def get_change_set(change_set_id: str, *, path: Path | None = None) -> dict[str, Any] | None:
    """Return one change set."""

    for item in _load(path):
        if item.get("id") == change_set_id:
            return item
    return None


def transition_change_set(
    change_set_id: str,
    *,
    status: str,
    actor: str,
    reason: str | None = None,
    allow_policy_failure: bool = False,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Move a change set through its lifecycle."""

    if status not in STATUSES:
        raise ValueError(f"Unsupported change set status: {status}")
    record = get_change_set(change_set_id, path=path)
    if record is None:
        raise KeyError(f"Change set not found: {change_set_id}")
    now = _now()
    updated = dict(record)
    if status in {"approved", "merged", "released"}:
        policy_context = {
            "risk_summary": updated.get("risk_summary") or {},
            "test_matrix": updated.get("test_matrix") or {},
            "test_evidence": summarize_test_evidence(
                change_set_id=change_set_id,
                path=_test_evidence_path_for_store(path),
            ),
            "release_readiness": updated.get("release_readiness") or {},
        }
        policy = evaluate_policy(policy_context, scope_id=change_set_id)
        updated["policy_evaluation"] = {
            "id": policy["id"],
            "status": policy["status"],
            "summary": policy["summary"],
        }
        if policy["status"] == "fail" and not allow_policy_failure:
            _upsert(updated, path=path)
            raise ValueError(f"Policy gate failed for {change_set_id}: {policy['id']}")
    updated["status"] = status
    updated["updated_at"] = now
    decisions = list(updated.get("decision_log") or [])
    decisions.insert(0, {"at": now, "actor": actor or "system", "status": status, "reason": reason or ""})
    updated["decision_log"] = decisions
    updated["artifact_sync"] = sync_change_set_to_artifacts(updated, artifact_path=_artifact_path_for_store(path, artifact_path))
    return _upsert(updated, path=path)


def add_decision(
    change_set_id: str,
    *,
    actor: str,
    decision: str,
    reason: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Append a decision-log entry without changing status."""

    record = get_change_set(change_set_id, path=path)
    if record is None:
        raise KeyError(f"Change set not found: {change_set_id}")
    updated = dict(record)
    updated["updated_at"] = _now()
    decisions = list(updated.get("decision_log") or [])
    decisions.insert(
        0,
        {
            "at": updated["updated_at"],
            "actor": actor or "system",
            "decision": decision,
            "reason": reason or "",
        },
    )
    updated["decision_log"] = decisions
    return _upsert(updated, path=path)


def analyze_change_set(
    store: Any,
    change_set_id: str,
    *,
    max_depth: int = 5,
    max_edges: int = 600,
    hotspot_limit: int = 10,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Attach Rentgen impact analysis to a change set."""

    record = get_change_set(change_set_id, path=path)
    if record is None:
        raise KeyError(f"Change set not found: {change_set_id}")
    modules = dedupe(record.get("changed_modules") or [])
    if not modules:
        raise ValueError("Change set has no changed modules or diff modules.")
    plan = build_change_plan(
        store,
        modules,
        max_depth=max_depth,
        max_edges=max_edges,
        hotspot_limit=hotspot_limit,
    )
    risks = [int((item.get("quality") or {}).get("risk") or 0) for item in plan.get("modules", [])]
    updated = dict(record)
    updated["status"] = "impact_analyzed"
    updated["change_plan"] = plan
    updated["risk_summary"] = {
        "changed_modules": len(modules),
        "total_impact_edges": plan.get("total_impact_edges", 0),
        "total_impacted_modules": plan.get("total_impacted_modules", 0),
        "max_risk": max(risks or [0]),
        "high_risk_modules": sum(1 for risk in risks if risk >= 70),
    }
    updated["updated_at"] = _now()
    updated["artifact_sync"] = sync_change_set_to_artifacts(updated, artifact_path=_artifact_path_for_store(path, artifact_path))
    return _upsert(updated, path=path)


def select_change_set_tests(
    store: Any,
    change_set_id: str,
    *,
    max_depth: int = 5,
    max_edges: int = 600,
    hotspot_limit: int = 10,
    match_limit: int = 10,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Attach risk-driven test coverage matrix to a change set."""

    record = get_change_set(change_set_id, path=path)
    if record is None:
        raise KeyError(f"Change set not found: {change_set_id}")
    matrix = build_test_coverage_matrix(
        store,
        changed_modules=record.get("changed_modules", []),
        diff=record.get("diff"),
        max_depth=max_depth,
        max_edges=max_edges,
        hotspot_limit=hotspot_limit,
        match_limit=match_limit,
    )
    updated = dict(record)
    updated["status"] = "tests_selected"
    updated["test_matrix"] = matrix
    updated["updated_at"] = _now()
    updated["artifact_sync"] = sync_change_set_to_artifacts(updated, artifact_path=_artifact_path_for_store(path, artifact_path))
    return _upsert(updated, path=path)


def attach_release_readiness(
    store: Any,
    change_set_id: str,
    *,
    include_security: bool = False,
    include_forms: bool = True,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Attach release-readiness report to a change set."""

    record = get_change_set(change_set_id, path=path)
    if record is None:
        raise KeyError(f"Change set not found: {change_set_id}")
    report = build_release_readiness(
        store,
        changed_modules=record.get("changed_modules", []),
        diff=record.get("diff"),
        release_name=record.get("title"),
        include_security=include_security,
        include_forms=include_forms,
    )
    updated = dict(record)
    updated["status"] = "review_ready"
    updated["release_readiness"] = report
    updated["updated_at"] = _now()
    updated["artifact_sync"] = sync_change_set_to_artifacts(updated, artifact_path=_artifact_path_for_store(path, artifact_path))
    return _upsert(updated, path=path)
