"""Test execution evidence store for 1cAI delivery governance."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.audit_log import record_event
from src.services.rentgen import artifact_graph

ROOT = Path(__file__).resolve().parents[3]
STORE_PATH = ROOT / "data" / "test_runs.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean(value: Any, *, limit: int = 1000) -> str:
    return str(value or "").strip()[:limit]


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


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
            category="testing",
            metadata=metadata,
            path=_audit_path(path),
        )
    except Exception:
        return


def _artifact_path_for_store(
    path: Path | None, artifact_path: Path | None
) -> Path | None:
    if artifact_path is not None:
        return artifact_path
    if path is not None:
        return path.parent / "artifact_graph.json"
    return None


def _id(prefix: str, payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return f"{prefix}_" + hashlib.sha1(encoded).hexdigest()[:16]


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(item.get("status") or "unknown").lower() for item in results)
    failed = counts.get("failed", 0) + counts.get("error", 0)
    status = "passed"
    if failed:
        status = "failed"
    elif counts.get("skipped", 0):
        status = "warning"
    return {
        "status": status,
        "total": len(results),
        "passed": counts.get("passed", 0),
        "failed": counts.get("failed", 0),
        "error": counts.get("error", 0),
        "skipped": counts.get("skipped", 0),
        "by_status": dict(counts),
    }


def record_test_run(
    *,
    title: str,
    framework: str,
    results: list[dict[str, Any]],
    change_set_id: str | None = None,
    command: str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
    run_id: str | None = None,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Persist one test run and project it into Artifact Graph."""

    created_at = _now()
    normalized_results = [
        {
            "id": _clean(
                item.get("id") or item.get("name") or item.get("selector"), limit=260
            ),
            "name": _clean(
                item.get("name") or item.get("selector") or item.get("id"), limit=260
            ),
            "framework": _clean(item.get("framework") or framework, limit=80),
            "status": _clean(item.get("status") or "unknown", limit=40).lower(),
            "duration_ms": _float(item.get("duration_ms")),
            "message": _clean(item.get("message"), limit=2000),
            "path": _clean(item.get("path"), limit=500),
        }
        for item in results
    ]
    summary = _summary(normalized_results)
    record = {
        "id": run_id
        or _id("trun", {"title": title, "framework": framework, "at": created_at}),
        "title": _clean(title, limit=240),
        "framework": _clean(framework, limit=80),
        "status": summary["status"],
        "change_set_id": _clean(change_set_id, limit=160) or None,
        "command": _clean(command, limit=1000),
        "dry_run": bool(dry_run),
        "summary": summary,
        "results": normalized_results,
        "evidence": list(evidence or []),
        "created_at": created_at,
        "updated_at": created_at,
    }
    items = [item for item in _load(path) if item.get("id") != record["id"]]
    items.insert(0, record)
    _write(items[:500], path)
    record["artifact_sync"] = sync_test_run_to_artifacts(
        record, artifact_path=_artifact_path_for_store(path, artifact_path)
    )
    items[0] = record
    _write(items[:500], path)
    _audit(
        "test.run.record",
        target=record["id"],
        metadata={
            "status": record["status"],
            "framework": record["framework"],
            "change_set_id": record.get("change_set_id"),
        },
        path=path,
    )
    return record


def sync_test_run_to_artifacts(
    record: dict[str, Any], *, artifact_path: Path | None = None
) -> dict[str, Any]:
    sync = {"artifact_id": record["id"], "artifacts": 1, "links": 0, "errors": []}
    try:
        artifact_graph.create_artifact(
            {
                "id": record["id"],
                "type": "test_run",
                "title": record["title"],
                "description": record.get("command") or "",
                "status": record.get("status") or "unknown",
                "source": "test_evidence",
                "attributes": {
                    "framework": record.get("framework"),
                    "summary": record.get("summary", {}),
                    "dry_run": record.get("dry_run"),
                    "change_set_id": record.get("change_set_id"),
                },
            },
            path=artifact_path,
        )
        if record.get("change_set_id") and artifact_graph.get_artifact(
            record["change_set_id"], path=artifact_path
        ):
            artifact_graph.link_artifacts(
                source_id=record["change_set_id"],
                target_id=record["id"],
                link_type="tested_by",
                rationale="Change set has stored test-run evidence.",
                path=artifact_path,
            )
            sync["links"] += 1
        for result in record.get("results", []):
            case_id = result.get("id") or result.get("name")
            if not case_id:
                continue
            artifact_id = _id("test", case_id)
            artifact_graph.create_artifact(
                {
                    "id": artifact_id,
                    "type": "test_case",
                    "title": result.get("name") or case_id,
                    "status": result.get("status") or "unknown",
                    "source": "test_evidence",
                    "attributes": result,
                },
                path=artifact_path,
            )
            sync["artifacts"] += 1
            artifact_graph.link_artifacts(
                source_id=record["id"],
                target_id=artifact_id,
                link_type="relates_to",
                rationale="Test run contains this test case result.",
                path=artifact_path,
            )
            sync["links"] += 1
    except (KeyError, ValueError) as exc:
        sync["errors"].append(str(exc))
    return sync


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _first_child(element: ET.Element, *names: str) -> ET.Element | None:
    wanted = set(names)
    for child in list(element):
        if _local_name(child.tag) in wanted:
            return child
    return None


def import_junit_xml(
    *,
    xml_text: str,
    title: str = "JUnit import",
    framework: str = "JUnit",
    change_set_id: str | None = None,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Import JUnit XML content into the test evidence store."""

    root = ET.fromstring(xml_text)
    cases = [
        element for element in root.iter() if _local_name(element.tag) == "testcase"
    ]
    results = []
    for case in cases:
        name = case.attrib.get("name") or case.attrib.get("classname") or "testcase"
        status = "passed"
        message = ""
        failure = _first_child(case, "failure")
        error = _first_child(case, "error")
        skipped = _first_child(case, "skipped")
        if failure is not None:
            status = "failed"
            message = failure.attrib.get("message", "") or (failure.text or "")
        elif error is not None:
            status = "error"
            message = error.attrib.get("message", "") or (error.text or "")
        elif skipped is not None:
            status = "skipped"
            message = skipped.attrib.get("message", "") or (skipped.text or "")
        results.append(
            {
                "id": f"{case.attrib.get('classname', '')}::{name}",
                "name": name,
                "framework": framework,
                "status": status,
                "duration_ms": _float(case.attrib.get("time")) * 1000,
                "message": message,
            }
        )
    return record_test_run(
        title=title,
        framework=framework,
        results=results,
        change_set_id=change_set_id,
        evidence=[{"kind": "junit_xml", "cases": len(results)}],
        path=path,
        artifact_path=artifact_path,
    )


def list_test_runs(
    *,
    status: str | None = None,
    change_set_id: str | None = None,
    limit: int = 100,
    path: Path | None = None,
) -> dict[str, Any]:
    items = _load(path)
    if status:
        items = [item for item in items if item.get("status") == status]
    if change_set_id:
        items = [item for item in items if item.get("change_set_id") == change_set_id]
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {
        "items": items[: max(1, limit)],
        "total": len(items),
        "path": str(path or STORE_PATH),
    }


def get_test_run(run_id: str, *, path: Path | None = None) -> dict[str, Any] | None:
    for item in _load(path):
        if item.get("id") == run_id:
            return item
    return None


def summarize_test_evidence(
    *, change_set_id: str | None = None, path: Path | None = None
) -> dict[str, Any]:
    """Summarize stored test-run evidence for policy and release gates."""

    items = _load(path)
    if change_set_id:
        items = [item for item in items if item.get("change_set_id") == change_set_id]
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    counts = Counter(str(item.get("status") or "unknown") for item in items)
    total_results = sum(
        int((item.get("summary") or {}).get("total") or 0) for item in items
    )
    failed_results = sum(
        int((item.get("summary") or {}).get("failed") or 0)
        + int((item.get("summary") or {}).get("error") or 0)
        for item in items
    )
    latest = items[0] if items else None
    return {
        "runs": len(items),
        "latest_run_id": latest.get("id") if latest else None,
        "latest_status": latest.get("status") if latest else None,
        "passed_runs": counts.get("passed", 0),
        "warning_runs": counts.get("warning", 0),
        "failed_runs": counts.get("failed", 0),
        "total_results": total_results,
        "failed_results": failed_results,
        "path": str(path or STORE_PATH),
    }
