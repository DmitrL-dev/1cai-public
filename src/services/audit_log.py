"""Append-only product audit log for governance workflows."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / "data" / "audit_log.ndjson"
_LOCK = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {_clean(key, limit=160): _safe_json(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_safe_json(item) for item in value[:500]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


GENESIS_HASH = "0" * 64


def _content_fields(event: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical, hashable fields of an event (excluding its id)."""
    return {
        "timestamp": event.get("timestamp"),
        "actor": event.get("actor"),
        "action": event.get("action"),
        "target": event.get("target"),
        "category": event.get("category"),
        "outcome": event.get("outcome"),
        "correlation_id": event.get("correlation_id"),
        "metadata": event.get("metadata"),
        "prev_hash": event.get("prev_hash"),
    }


def _compute_id(event: dict[str, Any]) -> str:
    """Compute the tamper-evident id over the event content + prev_hash.

    Because ``prev_hash`` is part of the hashed payload, every entry is
    cryptographically bound to its predecessor: altering any field of any
    earlier entry (or reordering/removing one) changes that entry's id, which
    breaks the ``prev_hash`` linkage of every entry that follows.
    """
    encoded = json.dumps(
        _content_fields(event), ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    return "aud_" + hashlib.sha256(encoded).hexdigest()[:40]


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def record_event(
    *,
    action: str,
    actor: str = "system",
    target: str | None = None,
    category: str = "governance",
    outcome: str = "success",
    metadata: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Append one product audit event."""

    target_path = path or LOG_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        prev_hash = _last_hash(target_path)
        event = {
            "timestamp": _now(),
            "actor": _clean(actor, limit=160) or "system",
            "action": _clean(action, limit=200),
            "target": _clean(target, limit=300) or None,
            "category": _clean(category, limit=80) or "governance",
            "outcome": _clean(outcome, limit=80) or "success",
            "correlation_id": _clean(correlation_id, limit=160) or None,
            "metadata": _safe_json(metadata or {}),
            "prev_hash": prev_hash,
        }
        event["id"] = _compute_id(event)
        with target_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def _last_hash(path: Path) -> str:
    """Return the id of the most recent event, or the genesis hash if empty."""
    items = _read(path)
    if not items:
        return GENESIS_HASH
    last_id = items[-1].get("id")
    return str(last_id) if last_id else GENESIS_HASH


def _read(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or LOG_PATH
    if not target.exists():
        return []
    items = []
    for line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def list_events(
    *,
    actor: str | None = None,
    action: str | None = None,
    category: str | None = None,
    target: str | None = None,
    since: str | None = None,
    limit: int = 100,
    path: Path | None = None,
) -> dict[str, Any]:
    """List audit events newest first."""

    items = _read(path)
    if actor:
        items = [item for item in items if item.get("actor") == actor]
    if action:
        items = [item for item in items if item.get("action") == action]
    if category:
        items = [item for item in items if item.get("category") == category]
    if target:
        needle = target.casefold()
        items = [item for item in items if needle in str(item.get("target") or "").casefold()]
    since_dt = _parse_dt(since)
    if since_dt:
        items = [
            item
            for item in items
            if (_parse_dt(str(item.get("timestamp") or "")) or datetime.min.replace(tzinfo=timezone.utc)) >= since_dt
        ]
    items.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return {"items": items[: max(1, limit)], "total": len(items), "path": str(path or LOG_PATH)}


def verify_chain(*, path: Path | None = None) -> dict[str, Any]:
    """Verify the audit log hash-chain and report any tampering.

    Walks events in file (append) order and checks, for each entry:
      * the stored ``id`` equals the id recomputed from its content + prev_hash
        (detects in-place modification of any field), and
      * its ``prev_hash`` equals the id of the immediately preceding entry
        (detects insertion, deletion or reordering).

    Entries written before the hash-chain existed have no ``prev_hash`` key and
    are reported as ``legacy`` (their integrity cannot be cryptographically
    asserted), but they are not counted as tampering. Returns a structured
    report with ``valid`` True only when no broken entries are found.
    """
    target = path or LOG_PATH
    items = _read(target)
    broken: list[dict[str, Any]] = []
    legacy = 0
    chained = 0
    prev_id = GENESIS_HASH

    for index, event in enumerate(items):
        if "prev_hash" not in event:
            # Pre-chain legacy entry: cannot verify, advance the baseline so a
            # later genuine chain links from this entry's stored id.
            legacy += 1
            prev_id = str(event.get("id") or prev_id)
            continue

        chained += 1
        expected_id = _compute_id(event)
        stored_id = str(event.get("id") or "")
        stored_prev = str(event.get("prev_hash") or "")

        reasons = []
        if stored_id != expected_id:
            reasons.append("id_mismatch")
        if stored_prev != prev_id:
            reasons.append("prev_hash_mismatch")
        if reasons:
            broken.append(
                {
                    "index": index,
                    "id": stored_id,
                    "actor": event.get("actor"),
                    "action": event.get("action"),
                    "reasons": reasons,
                }
            )
        # Advance using the stored id so a single break is reported once rather
        # than cascading through every subsequent entry.
        prev_id = stored_id or expected_id

    return {
        "valid": not broken,
        "total": len(items),
        "chained": chained,
        "legacy": legacy,
        "broken": broken,
        "path": str(target),
    }


def export_events(*, output_format: str = "jsonl", path: Path | None = None) -> dict[str, Any]:
    """Return audit log export content."""

    items = _read(path)
    fmt = _clean(output_format, limit=20).lower() or "jsonl"
    if fmt == "json":
        content = json.dumps({"items": items}, ensure_ascii=False, indent=2)
    elif fmt == "jsonl":
        content = "\n".join(json.dumps(item, ensure_ascii=False) for item in items)
    else:
        raise ValueError(f"Unsupported audit export format: {output_format}")
    return {"format": fmt, "events": len(items), "content": content, "path": str(path or LOG_PATH)}
