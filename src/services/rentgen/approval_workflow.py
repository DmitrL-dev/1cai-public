"""Internal approval records for privileged 1C delivery actions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
STORE_PATH = ROOT / "data" / "approval_records.json"
APPROVAL_STATUSES = {"requested", "approved", "rejected", "used", "expired"}


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now() -> str:
    return _now_dt().replace(microsecond=0).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


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


def _approval_id(*, tool_name: str, actor: str, reason: str, created_at: str) -> str:
    source = "\n".join([tool_name.strip(), actor.strip(), reason.strip(), created_at])
    return "apv_" + hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


def _trim(value: str | None, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _expires_at(hours: int | float | None) -> str:
    safe_hours = max(1.0, min(float(hours or 24), 24 * 30))
    return (_now_dt() + timedelta(hours=safe_hours)).replace(microsecond=0).isoformat()


def create_approval_record(
    *,
    tool_name: str,
    actor: str,
    approval_reason: str,
    risk: str = "unknown",
    approval_ticket: str | None = None,
    requested_by: str | None = None,
    linked_record_type: str | None = None,
    linked_record_id: str | None = None,
    argument_constraints: dict[str, Any] | None = None,
    expires_in_hours: int | float | None = 24,
    path: Path | None = None,
) -> dict[str, Any]:
    """Create or upsert a requested approval record."""

    created_at = _now()
    clean_tool = _trim(tool_name, limit=200)
    clean_actor = _trim(actor, limit=160)
    clean_reason = _trim(approval_reason, limit=1000)
    record = {
        "id": _approval_id(tool_name=clean_tool, actor=clean_actor, reason=clean_reason, created_at=created_at),
        "kind": "edt_mcp_call",
        "status": "requested",
        "tool_name": clean_tool,
        "risk": _trim(risk, limit=40) or "unknown",
        "actor": clean_actor,
        "approval_reason": clean_reason,
        "approval_ticket": _trim(approval_ticket, limit=160) or None,
        "requested_by": _trim(requested_by, limit=160) or clean_actor,
        "approved_by": None,
        "decision_reason": None,
        "linked_record": {
            "type": _trim(linked_record_type, limit=80) or None,
            "id": _trim(linked_record_id, limit=200) or None,
        },
        "argument_constraints": dict(argument_constraints or {}),
        "created_at": created_at,
        "updated_at": created_at,
        "expires_at": _expires_at(expires_in_hours),
        "used_at": None,
    }
    items = [item for item in _load(path) if item.get("id") != record["id"]]
    items.insert(0, record)
    _write(items, path)
    return record


def list_approval_records(
    *,
    status: str | None = None,
    kind: str | None = None,
    limit: int = 50,
    path: Path | None = None,
) -> dict[str, Any]:
    """List internal approval records."""

    items = _load(path)
    if status:
        items = [item for item in items if item.get("status") == status]
    if kind:
        items = [item for item in items if item.get("kind") == kind]
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return {"items": items[: max(1, limit)], "total": len(items), "path": str(path or STORE_PATH)}


def get_approval_record(approval_id: str, *, path: Path | None = None) -> dict[str, Any] | None:
    """Return one approval record."""

    for item in _load(path):
        if item.get("id") == approval_id:
            return item
    return None


def update_approval_status(
    approval_id: str,
    *,
    status: str,
    actor: str,
    decision_reason: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Update approval status and approver metadata."""

    clean_status = _trim(status, limit=40)
    if clean_status not in APPROVAL_STATUSES:
        raise ValueError(f"Unsupported approval status: {status}")
    clean_actor = _trim(actor, limit=160)
    items = _load(path)
    now = _now()
    for index, item in enumerate(items):
        if item.get("id") != approval_id:
            continue
        # Separation of duties: the principal who requested/created an approval
        # may not approve it. Self-approval defeats the control entirely.
        if clean_status == "approved":
            requester = _trim(item.get("requested_by"), limit=160) or _trim(
                item.get("actor"), limit=160
            )
            if clean_actor and requester and clean_actor == requester:
                raise PermissionError(
                    "Separation of duties: requester cannot approve their own "
                    "request"
                )
        updated = dict(item)
        updated["status"] = clean_status
        updated["updated_at"] = now
        if clean_status == "approved":
            updated["approved_by"] = clean_actor
            updated["decision_reason"] = _trim(decision_reason, limit=1000) or None
        elif clean_status == "used":
            updated["used_at"] = now
        elif clean_status == "rejected":
            updated["decision_reason"] = _trim(decision_reason, limit=1000) or None
        items[index] = updated
        items.sort(key=lambda row: row.get("updated_at", ""), reverse=True)
        _write(items, path)
        return updated
    raise KeyError(f"Approval record not found: {approval_id}")


def validate_approval_for_call(
    approval_id: str | None,
    *,
    tool_name: str,
    actor: str | None,
    risk: str,
    arguments: dict[str, Any] | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Validate that an approval record can authorize an EDT-MCP tool call."""

    if not approval_id:
        return {"valid": False, "reason": "missing_approval_id", "approval": None}
    record = get_approval_record(approval_id, path=path)
    if not record:
        return {"valid": False, "reason": "not_found", "approval": None}
    expires_at = _parse_dt(record.get("expires_at"))
    if expires_at and expires_at < _now_dt():
        return {"valid": False, "reason": "expired", "approval": record}
    if record.get("status") != "approved":
        return {"valid": False, "reason": f"status_{record.get('status')}", "approval": record}
    if record.get("kind") != "edt_mcp_call":
        return {"valid": False, "reason": "wrong_kind", "approval": record}
    if record.get("tool_name") != tool_name:
        return {"valid": False, "reason": "tool_mismatch", "approval": record}
    if actor and record.get("actor") and record.get("actor") != actor:
        return {"valid": False, "reason": "actor_mismatch", "approval": record}
    record_risk = str(record.get("risk") or "")
    if record_risk and record_risk not in {risk, "mixed", "unknown"}:
        return {"valid": False, "reason": "risk_mismatch", "approval": record}
    constraints = record.get("argument_constraints") or {}
    if constraints:
        call_args = arguments if isinstance(arguments, dict) else {}
        for key, expected in constraints.items():
            if call_args.get(key) != expected:
                return {"valid": False, "reason": f"argument_mismatch:{key}", "approval": record}
    return {"valid": True, "reason": "approved", "approval": record}
