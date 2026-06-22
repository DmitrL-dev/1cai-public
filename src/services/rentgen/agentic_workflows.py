"""Deterministic agentic workflow guardrails for 1cAI."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.audit_log import record_event
from src.services.rentgen import artifact_graph
from src.services.rentgen.policy_engine import evaluate_policy
from src.services.rentgen.test_evidence import summarize_test_evidence

ROOT = Path(__file__).resolve().parents[3]
STORE_PATH = ROOT / "data" / "agentic_workflows.json"
MODES = {"ask", "plan", "act", "review"}
PLAN_STATUSES = {
    "draft",
    "ready",
    "approved",
    "running",
    "blocked",
    "completed",
    "rejected",
}
STEP_STATUSES = {"todo", "in_progress", "blocked", "done", "skipped"}
RISKY_ACTIONS = {
    "metadata_write",
    "bsl_write",
    "external_command",
    "edt_mcp_call",
    "release",
    "policy_waiver",
    "rights_change",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _safe_list(values: Any, *, limit: int = 500) -> list[str]:
    if not isinstance(values, list):
        return []
    return [_clean(item, limit=limit) for item in values if _clean(item, limit=limit)]


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
    tmp.write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
            category="agentic",
            metadata=metadata,
            path=_audit_path(path),
        )
    except Exception:
        return


def _id(prefix: str, value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"{prefix}_" + hashlib.sha1(encoded).hexdigest()[:16]


def _normalize_steps(steps: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized = []
    for index, step in enumerate(steps or [], start=1):
        action_type = _clean(
            step.get("action_type") or step.get("action") or "analysis", limit=80
        )
        risk = _clean(
            step.get("risk") or ("high" if action_type in RISKY_ACTIONS else "low"),
            limit=40,
        )
        normalized.append(
            {
                "id": _clean(step.get("id"), limit=80) or f"step-{index}",
                "title": _clean(
                    step.get("title") or step.get("action") or f"Step {index}",
                    limit=240,
                ),
                "role": _clean(step.get("role") or "agent", limit=80),
                "action_type": action_type,
                "status": _clean(step.get("status") or "todo", limit=40)
                if _clean(step.get("status") or "todo", limit=40) in STEP_STATUSES
                else "todo",
                "risk": risk,
                "required_evidence": _safe_list(
                    step.get("required_evidence"), limit=160
                ),
                "notes": _clean(step.get("notes"), limit=1000),
            }
        )
    if not normalized:
        normalized.append(
            {
                "id": "step-1",
                "title": "Review evidence and produce deterministic plan",
                "role": "agent",
                "action_type": "analysis",
                "status": "todo",
                "risk": "low",
                "required_evidence": ["artifact_trace", "policy_context"],
                "notes": "",
            }
        )
    return normalized


def create_agentic_plan(
    data: dict[str, Any],
    *,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Create an agentic work plan with deterministic guardrails."""

    title = _clean(data.get("title"), limit=240)
    if not title:
        raise ValueError("Plan title is required")
    mode = _clean(data.get("mode") or "plan", limit=40)
    if mode not in MODES:
        raise ValueError(f"Unsupported agent mode: {mode}")
    now = _now()
    plan_id = _clean(data.get("id"), limit=120) or _id(
        "agent", {"title": title, "at": now}
    )
    record = {
        "id": plan_id,
        "title": title,
        "objective": _clean(data.get("objective"), limit=4000),
        "mode": mode,
        "status": _clean(data.get("status") or "draft", limit=40),
        "actor": _clean(data.get("actor") or "system", limit=160),
        "change_set_id": _clean(data.get("change_set_id"), limit=160) or None,
        "source_artifact_ids": _safe_list(data.get("source_artifact_ids"), limit=160),
        "steps": _normalize_steps(
            data.get("steps") if isinstance(data.get("steps"), list) else None
        ),
        "review": {},
        "created_at": now,
        "updated_at": now,
    }
    if record["status"] not in PLAN_STATUSES:
        raise ValueError(f"Unsupported plan status: {record['status']}")
    items = [item for item in _load(path) if item.get("id") != record["id"]]
    items.insert(0, record)
    _write(items, path)
    _sync_plan_artifact(record, artifact_path=artifact_path)
    _audit(
        "agentic.plan.create",
        target=record["id"],
        metadata={"mode": mode, "steps": len(record["steps"])},
        path=path,
    )
    return record


def list_agentic_plans(
    *,
    status: str | None = None,
    mode: str | None = None,
    limit: int = 100,
    path: Path | None = None,
) -> dict[str, Any]:
    items = _load(path)
    if status:
        items = [item for item in items if item.get("status") == status]
    if mode:
        items = [item for item in items if item.get("mode") == mode]
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return {
        "items": items[: max(1, limit)],
        "total": len(items),
        "path": str(path or STORE_PATH),
    }


def get_agentic_plan(
    plan_id: str, *, path: Path | None = None
) -> dict[str, Any] | None:
    for item in _load(path):
        if item.get("id") == plan_id:
            return item
    return None


def transition_step(
    plan_id: str,
    *,
    step_id: str,
    status: str,
    actor: str = "system",
    note: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    if status not in STEP_STATUSES:
        raise ValueError(f"Unsupported step status: {status}")
    items = _load(path)
    for index, item in enumerate(items):
        if item.get("id") != plan_id:
            continue
        updated = dict(item)
        steps = [dict(step) for step in updated.get("steps", [])]
        for step in steps:
            if step.get("id") != step_id:
                continue
            step["status"] = status
            step["updated_by"] = actor
            step["updated_at"] = _now()
            if note:
                step["notes"] = _clean(note, limit=1000)
            updated["steps"] = steps
            updated["updated_at"] = _now()
            counts = Counter(step.get("status") for step in steps)
            if counts.get("blocked"):
                updated["status"] = "blocked"
            elif counts.get("todo") or counts.get("in_progress"):
                updated["status"] = "running"
            else:
                updated["status"] = "completed"
            items[index] = updated
            _write(items, path)
            _audit(
                "agentic.step.transition",
                target=plan_id,
                metadata={"step_id": step_id, "status": status, "actor": actor},
                path=path,
            )
            return updated
        raise KeyError(f"Step not found: {step_id}")
    raise KeyError(f"Agentic plan not found: {plan_id}")


def review_agentic_plan(
    plan_id: str,
    *,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    record = get_agentic_plan(plan_id, path=path)
    if record is None:
        raise KeyError(f"Agentic plan not found: {plan_id}")

    findings = []
    if record.get("mode") == "act" and record.get("status") != "approved":
        findings.append(
            {
                "severity": "high",
                "code": "act-without-approved-plan",
                "message": "Act mode requires an approved plan.",
            }
        )
    risky_steps = [
        step
        for step in record.get("steps", [])
        if step.get("action_type") in RISKY_ACTIONS or step.get("risk") == "high"
    ]
    if risky_steps:
        findings.append(
            {
                "severity": "medium",
                "code": "risky-steps",
                "message": "Risky steps require approval or policy gate.",
                "count": len(risky_steps),
            }
        )

    traces = []
    for artifact_id in record.get("source_artifact_ids", [])[:10]:
        try:
            traces.append(
                artifact_graph.trace_artifact(artifact_id, path=artifact_path)[
                    "summary"
                ]
            )
        except (KeyError, ValueError):
            findings.append(
                {
                    "severity": "medium",
                    "code": "artifact-trace-missing",
                    "message": f"Trace source is missing: {artifact_id}",
                }
            )

    test_summary = summarize_test_evidence(
        change_set_id=record.get("change_set_id"),
        path=(path or STORE_PATH).parent / "test_runs.json",
    )
    policy = evaluate_policy(
        {
            "test_evidence": test_summary,
            "agentic": {"risky_steps": len(risky_steps), "mode": record.get("mode")},
        },
        scope_id=record["id"],
        evaluations_path=(path or STORE_PATH).parent / "policy_evaluations.json",
        waivers_path=(path or STORE_PATH).parent / "policy_waivers.json",
    )
    severity = Counter(item["severity"] for item in findings)
    status = (
        "fail"
        if severity.get("high") or policy["status"] == "fail"
        else ("warn" if findings or policy["status"] == "warn" else "pass")
    )
    review = {
        "status": status,
        "generated_at": _now(),
        "findings": findings,
        "policy_evaluation": {
            "id": policy["id"],
            "status": policy["status"],
            "summary": policy["summary"],
        },
        "test_evidence": test_summary,
        "trace_summaries": traces,
    }
    items = _load(path)
    for index, item in enumerate(items):
        if item.get("id") == plan_id:
            updated = dict(item)
            updated["review"] = review
            updated["updated_at"] = _now()
            items[index] = updated
            _write(items, path)
            _audit(
                "agentic.plan.review",
                target=plan_id,
                metadata={"status": status, "findings": len(findings)},
                path=path,
            )
            return updated
    raise KeyError(f"Agentic plan not found: {plan_id}")


def action_gate(
    *,
    action_type: str,
    plan_id: str | None = None,
    change_set_id: str | None = None,
    risk: str = "low",
    confirm: bool = False,
    path: Path | None = None,
) -> dict[str, Any]:
    action = _clean(action_type, limit=80)
    risky = action in RISKY_ACTIONS or risk == "high"
    plan = get_agentic_plan(plan_id, path=path) if plan_id else None
    reasons = []
    if risky and not confirm:
        reasons.append("confirmation_required")
    if risky and plan is None:
        reasons.append("approved_plan_required")
    if plan and plan.get("status") not in {"approved", "running"} and risky:
        reasons.append("plan_not_approved")
    test_summary = summarize_test_evidence(
        change_set_id=change_set_id, path=(path or STORE_PATH).parent / "test_runs.json"
    )
    if test_summary["failed_runs"]:
        reasons.append("failed_test_evidence")
    allowed = not reasons
    decision = {
        "allowed": allowed,
        "action_type": action,
        "risk": risk,
        "requires_approval": risky,
        "reasons": reasons,
        "plan_id": plan_id,
        "change_set_id": change_set_id,
        "test_evidence": test_summary,
    }
    _audit(
        "agentic.action_gate", target=plan_id or action, metadata=decision, path=path
    )
    return decision


def _sync_plan_artifact(
    record: dict[str, Any], *, artifact_path: Path | None = None
) -> None:
    try:
        artifact_graph.create_artifact(
            {
                "id": record["id"],
                "type": "work_item",
                "title": record["title"],
                "description": record.get("objective") or "",
                "status": record.get("status") or "draft",
                "owner": record.get("actor") or "",
                "source": "agentic_workflows",
                "attributes": {
                    "mode": record.get("mode"),
                    "steps": record.get("steps", []),
                },
            },
            path=artifact_path,
        )
        for source_id in record.get("source_artifact_ids", []):
            if artifact_graph.get_artifact(source_id, path=artifact_path):
                artifact_graph.link_artifacts(
                    source_id=source_id,
                    target_id=record["id"],
                    link_type="relates_to",
                    rationale="Agentic plan uses this artifact as source evidence.",
                    path=artifact_path,
                )
    except (KeyError, ValueError):
        return
