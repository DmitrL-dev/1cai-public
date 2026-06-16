"""Policy and gate evaluation for 1cAI enterprise workflows."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.services.audit_log import record_event
from src.services.rentgen import artifact_graph


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = ROOT / "policy" / "1cai-default-policy.json"
EVALUATIONS_PATH = ROOT / "data" / "policy_evaluations.json"
WAIVERS_PATH = ROOT / "data" / "policy_waivers.json"


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_items(path: Path, items: list[dict[str, Any]], key: str = "items") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({key: items}, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _audit_path(path: Path | None = None) -> Path:
    return (path or EVALUATIONS_PATH).parent / "audit_log.ndjson"


def _audit(action: str, *, target: str, metadata: dict[str, Any], path: Path | None = None) -> None:
    try:
        record_event(
            action=action,
            target=target,
            category="policy",
            metadata=metadata,
            path=_audit_path(path),
        )
    except Exception:
        return


def _items(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path, {"items": []})
    items = payload.get("items", []) if isinstance(payload, dict) else payload
    return items if isinstance(items, list) else []


def _id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"{prefix}_" + hashlib.sha1(encoded).hexdigest()[:16]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_policy(path: Path | None = None) -> dict[str, Any]:
    """Load policy-as-code JSON."""

    policy = _load_json(path or DEFAULT_POLICY_PATH, {"version": "empty", "rules": []})
    if not isinstance(policy, dict):
        return {"version": "empty", "rules": []}
    rules = policy.get("rules", [])
    policy["rules"] = rules if isinstance(rules, list) else []
    return policy


def _field(context: dict[str, Any], dotted: str) -> Any:
    current: Any = context
    for part in dotted.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "exists":
        return actual is not None
    if op == "missing":
        return actual is None
    if op in {">", ">=", "<", "<="}:
        try:
            left = float(actual or 0)
            right = float(expected or 0)
        except (TypeError, ValueError):
            return False
        return {
            ">": left > right,
            ">=": left >= right,
            "<": left < right,
            "<=": left <= right,
        }[op]
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == "contains":
        return str(expected) in str(actual or "")
    if op == "count>":
        return len(actual or []) > int(expected or 0) if isinstance(actual, list) else False
    if op == "count>=":
        return len(actual or []) >= int(expected or 0) if isinstance(actual, list) else False
    raise ValueError(f"Unsupported policy operator: {op}")


def _rule_matches(rule: dict[str, Any], context: dict[str, Any]) -> bool:
    condition = rule.get("when") or {}
    if not isinstance(condition, dict):
        return False
    actual = _field(context, str(condition.get("field") or ""))
    return _compare(actual, str(condition.get("op") or "=="), condition.get("value"))


def _active_waivers(
    *,
    rule_id: str,
    scope_id: str | None,
    waivers_path: Path,
) -> list[dict[str, Any]]:
    now = _now_dt()
    matches = []
    for waiver in _items(waivers_path):
        if waiver.get("status") != "approved":
            continue
        if waiver.get("rule_id") != rule_id:
            continue
        # Defense in depth: a self-approved waiver (approver == owner, or no
        # distinct approver recorded) must NOT be able to flip a gate. This
        # neutralises any forged/legacy self-approved waiver in the store even
        # if it bypassed decide_waiver's check.
        owner = _clean(waiver.get("owner"), limit=160)
        approved_by = _clean(waiver.get("approved_by"), limit=160)
        if not approved_by or (owner and approved_by == owner):
            continue
        waiver_scope = waiver.get("scope_id") or "*"
        if waiver_scope not in {"*", scope_id}:
            continue
        expires = _parse_dt(waiver.get("expires_at"))
        if expires and expires < now:
            continue
        matches.append(waiver)
    return matches


def evaluate_policy(
    context: dict[str, Any],
    *,
    domain: str | None = None,
    scope_id: str | None = None,
    policy_path: Path | None = None,
    evaluations_path: Path | None = None,
    waivers_path: Path | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Evaluate policy rules against a workflow context."""

    policy = load_policy(policy_path)
    waiver_store = waivers_path or WAIVERS_PATH
    evaluated = []
    status = "pass"

    for rule in policy["rules"]:
        if domain and rule.get("domain") != domain:
            continue
        if not _rule_matches(rule, context):
            evaluated.append({"rule_id": rule.get("id"), "matched": False, "status": "pass"})
            continue
        waivers = _active_waivers(rule_id=str(rule.get("id")), scope_id=scope_id, waivers_path=waiver_store)
        waived = bool(waivers)
        rule_status = "waived" if waived else str(rule.get("decision") or "warn")
        if not waived and rule_status == "fail":
            status = "fail"
        elif not waived and rule_status == "warn" and status == "pass":
            status = "warn"
        evaluated.append(
            {
                "rule_id": rule.get("id"),
                "domain": rule.get("domain"),
                "severity": rule.get("severity"),
                "decision": rule.get("decision"),
                "description": rule.get("description"),
                "requires_approval": bool(rule.get("requires_approval")),
                "matched": True,
                "status": rule_status,
                "waiver_ids": [waiver["id"] for waiver in waivers],
                "field": (rule.get("when") or {}).get("field"),
                "actual": _field(context, str((rule.get("when") or {}).get("field") or "")),
                "expected": (rule.get("when") or {}).get("value"),
            }
        )

    matched = [item for item in evaluated if item.get("matched")]
    result = {
        "id": _id("pol", {"context": context, "domain": domain, "scope_id": scope_id, "at": _now()}),
        "status": status,
        "policy_version": policy.get("version"),
        "scope_id": scope_id,
        "domain": domain,
        "generated_at": _now(),
        "summary": {
            "rules": len(evaluated),
            "matched": len(matched),
            "fail": sum(1 for item in matched if item.get("status") == "fail"),
            "warn": sum(1 for item in matched if item.get("status") == "warn"),
            "waived": sum(1 for item in matched if item.get("status") == "waived"),
            "requires_approval": sum(1 for item in matched if item.get("requires_approval")),
        },
        "results": evaluated,
        "context": context,
    }
    if persist:
        path = evaluations_path or EVALUATIONS_PATH
        items = _items(path)
        items.insert(0, result)
        _write_items(path, items[:500])
        _audit(
            "policy.evaluate",
            target=result["id"],
            metadata={"status": result["status"], "scope_id": scope_id, "summary": result["summary"]},
            path=path,
        )
    return result


def list_evaluations(*, limit: int = 100, path: Path | None = None) -> dict[str, Any]:
    target = path or EVALUATIONS_PATH
    items = _items(target)
    return {"items": items[: max(1, limit)], "total": len(items), "path": str(target)}


def get_evaluation(evaluation_id: str, *, path: Path | None = None) -> dict[str, Any] | None:
    for item in _items(path or EVALUATIONS_PATH):
        if item.get("id") == evaluation_id:
            return item
    return None


def create_waiver(
    *,
    rule_id: str,
    scope_id: str | None,
    reason: str,
    owner: str,
    expires_in_days: int = 30,
    remediation: str | None = None,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Create a requested policy waiver."""

    now = _now()
    record = {
        "id": _id("waiver", {"rule_id": rule_id, "scope_id": scope_id, "owner": owner, "at": now}),
        "rule_id": _clean(rule_id, limit=160),
        "scope_id": _clean(scope_id, limit=160) or "*",
        "reason": _clean(reason, limit=1000),
        "owner": _clean(owner, limit=160),
        "remediation": _clean(remediation, limit=1000),
        "status": "requested",
        "created_at": now,
        "updated_at": now,
        "expires_at": (_now_dt() + timedelta(days=max(1, min(int(expires_in_days), 365)))).replace(microsecond=0).isoformat(),
        "approved_by": None,
        "decision_reason": None,
    }
    target = path or WAIVERS_PATH
    items = [item for item in _items(target) if item.get("id") != record["id"]]
    items.insert(0, record)
    _write_items(target, items)
    _sync_waiver_artifact(record, artifact_path=artifact_path)
    _audit(
        "policy.waiver.request",
        target=record["id"],
        metadata={"rule_id": record["rule_id"], "scope_id": record["scope_id"], "owner": record["owner"]},
        path=target,
    )
    return record


def decide_waiver(
    waiver_id: str,
    *,
    status: str,
    actor: str,
    decision_reason: str | None = None,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Approve or reject a policy waiver."""

    if status not in {"approved", "rejected"}:
        raise ValueError("Waiver decision must be approved or rejected")
    clean_actor = _clean(actor, limit=160)
    target = path or WAIVERS_PATH
    items = _items(target)
    for index, item in enumerate(items):
        if item.get("id") != waiver_id:
            continue
        # Separation of duties: the waiver owner/requester may not approve
        # their own waiver. A self-approved waiver could otherwise silence a
        # high-severity policy gate.
        if status == "approved":
            owner = _clean(item.get("owner"), limit=160)
            if clean_actor and owner and clean_actor == owner:
                raise PermissionError(
                    "Separation of duties: waiver owner cannot approve their "
                    "own waiver"
                )
        updated = dict(item)
        updated["status"] = status
        updated["updated_at"] = _now()
        updated["approved_by"] = clean_actor if status == "approved" else None
        updated["decision_reason"] = _clean(decision_reason, limit=1000)
        items[index] = updated
        _write_items(target, items)
        _sync_waiver_artifact(updated, artifact_path=artifact_path)
        _audit(
            "policy.waiver.decide",
            target=updated["id"],
            metadata={"status": updated["status"], "rule_id": updated["rule_id"], "actor": actor},
            path=target,
        )
        return updated
    raise KeyError(f"Policy waiver not found: {waiver_id}")


def list_waivers(*, status: str | None = None, limit: int = 100, path: Path | None = None) -> dict[str, Any]:
    target = path or WAIVERS_PATH
    items = _items(target)
    if status:
        items = [item for item in items if item.get("status") == status]
    return {"items": items[: max(1, limit)], "total": len(items), "path": str(target)}


def _sync_waiver_artifact(record: dict[str, Any], *, artifact_path: Path | None = None) -> None:
    try:
        artifact_graph.create_artifact(
            {
                "id": record["id"],
                "type": "waiver",
                "title": f"{record.get('rule_id')} waiver for {record.get('scope_id')}",
                "description": record.get("reason") or "",
                "status": record.get("status") or "requested",
                "owner": record.get("owner") or "",
                "source": "policy_engine",
                "attributes": {
                    "rule_id": record.get("rule_id"),
                    "scope_id": record.get("scope_id"),
                    "expires_at": record.get("expires_at"),
                    "remediation": record.get("remediation"),
                },
            },
            path=artifact_path,
        )
    except (KeyError, ValueError):
        return
