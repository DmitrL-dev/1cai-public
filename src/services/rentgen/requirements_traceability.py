"""Requirement traceability records for BA -> architecture -> code -> tests."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen import artifact_graph

ROOT = Path(__file__).resolve().parents[3]
STORE_PATH = ROOT / "data" / "requirements_traces.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_lines(values: list[str] | None) -> list[str]:
    return [value.strip() for value in values or [] if value and value.strip()]


def _trace_id(text: str, acceptance_criteria: list[str]) -> str:
    source = "\n".join([text.strip(), *_clean_lines(acceptance_criteria)])
    return "req_" + hashlib.sha1(source.encode("utf-8")).hexdigest()[:16]


def _short_title(text: str) -> str:
    compact = " ".join(text.split())
    return compact[:117] + "..." if len(compact) > 120 else compact


def _load(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or STORE_PATH
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        items = payload.get("items", [])
    else:
        items = payload
    return items if isinstance(items, list) else []


def _write(items: list[dict[str, Any]], path: Path | None = None) -> None:
    target = path or STORE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(target)


def _artifact_path_for_trace_store(
    path: Path | None, artifact_path: Path | None
) -> Path | None:
    if artifact_path is not None:
        return artifact_path
    if path is not None:
        return path.parent / "artifact_graph.json"
    return None


def _stable_artifact_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _candidate_by_module(candidates: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("module_path", ""): item for item in candidates}


def _module_tests(module: dict[str, Any]) -> list[dict[str, Any]]:
    tests = []
    for test in module.get("covering_tests", []):
        tests.append(
            {
                "id": test.get("id") or test.get("selector"),
                "selector": test.get("selector"),
                "framework": test.get("framework"),
                "priority": test.get("priority"),
                "status": test.get("status"),
                "confidence": test.get("confidence"),
                "command": test.get("command"),
                "reason": test.get("reason"),
                "path": test.get("path"),
            }
        )
    return tests


def _unique(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        value = item.get(key)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


def _trace_matrix(
    requirement_title: str,
    candidates: list[dict[str, Any]],
    change_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    by_module = _candidate_by_module(candidates)
    rows = []
    for module in change_plan.get("modules", []):
        module_path = module.get("module_path", "")
        candidate = by_module.get(module_path, {})
        tests = _module_tests(module)
        canonical = module.get("canonical") or {}
        rows.append(
            {
                "requirement": requirement_title,
                "module_path": module_path,
                "metadata_object": canonical.get("object_name") or "",
                "module_kind": canonical.get("module_kind") or "",
                "match_terms": candidate.get("match_terms", []),
                "match_score": candidate.get("score", 0),
                "impact_edges": module.get("impact_total", 0),
                "risk": (module.get("quality") or {}).get("risk", 0),
                "tests": [
                    test.get("selector") for test in tests if test.get("selector")
                ],
                "coverage": "mapped"
                if any(test.get("status") == "mapped" for test in tests)
                else ("planned" if tests else "missing"),
            }
        )
    return rows


def _risk_summary(
    change_plan: dict[str, Any], matrix: list[dict[str, Any]]
) -> dict[str, Any]:
    modules = change_plan.get("modules", [])
    max_risk = max([int(row.get("risk") or 0) for row in matrix] or [0])
    high_risk_modules = sum(1 for row in matrix if int(row.get("risk") or 0) >= 70)
    all_tests = [test for module in modules for test in _module_tests(module)]
    mapped_tests = sum(1 for test in all_tests if test.get("status") == "mapped")
    return {
        "modules": len(modules),
        "metadata_objects": len(
            {row["metadata_object"] for row in matrix if row["metadata_object"]}
        ),
        "total_impact_edges": change_plan.get("total_impact_edges", 0),
        "total_impacted_modules": change_plan.get("total_impacted_modules", 0),
        "max_risk": max_risk,
        "high_risk_modules": high_risk_modules,
        "test_actions": len(all_tests),
        "mapped_tests": mapped_tests,
    }


def _next_actions(
    matrix: list[dict[str, Any]], summary: dict[str, Any]
) -> list[dict[str, Any]]:
    actions = [
        {
            "owner": "ba",
            "severity": "medium",
            "title": "Validate candidate modules against acceptance criteria",
            "target": None,
        }
    ]
    if summary["total_impact_edges"] >= 300 or summary["high_risk_modules"]:
        actions.append(
            {
                "owner": "architect",
                "severity": "high",
                "title": "Review blast radius and split risky scope before implementation",
                "target": None,
            }
        )
    for row in matrix:
        if row["coverage"] != "mapped":
            actions.append(
                {
                    "owner": "qa",
                    "severity": "medium",
                    "title": "Confirm or add focused regression test coverage",
                    "target": row["module_path"],
                }
            )
    return actions[:12]


def _markdown(record: dict[str, Any]) -> str:
    lines = [
        "# Requirement Trace",
        "",
        f"ID: `{record['id']}`",
        f"Status: **{record['status']}**",
        "",
        "## Requirement",
        "",
        record["requirement"],
        "",
    ]
    if record["acceptance_criteria"]:
        lines.extend(["## Acceptance Criteria", ""])
        lines.extend(f"- {item}" for item in record["acceptance_criteria"])
        lines.append("")

    summary = record["risk_summary"]
    lines.extend(
        [
            "## Engineering Scope",
            "",
            f"- Candidate modules: {summary['modules']}",
            f"- Metadata objects: {summary['metadata_objects']}",
            f"- Impact edges: {summary['total_impact_edges']}",
            f"- Max risk: {summary['max_risk']}",
            f"- Test actions: {summary['test_actions']}",
            "",
            "## Trace Matrix",
            "",
        ]
    )
    for row in record["trace_matrix"]:
        lines.append(
            f"- `{row['module_path']}` -> {row['metadata_object'] or 'unmapped'}; "
            f"impact={row['impact_edges']}; risk={row['risk']}; coverage={row['coverage']}"
        )

    if record["next_actions"]:
        lines.extend(["", "## Next Actions", ""])
        for action in record["next_actions"]:
            target = f" `{action['target']}`" if action.get("target") else ""
            lines.append(f"- **{action['owner']}**{target}: {action['title']}")

    return "\n".join(lines)


def build_trace_record(
    *,
    requirement: str,
    candidate_modules: list[dict[str, Any]],
    change_plan: dict[str, Any],
    its_context: list[dict[str, Any]] | None = None,
    acceptance_criteria: list[str] | None = None,
    title: str | None = None,
    caveats: list[str] | None = None,
) -> dict[str, Any]:
    """Create a serializable traceability record from a requirement impact report."""

    criteria = _clean_lines(acceptance_criteria)
    trace_title = (title or "").strip() or _short_title(requirement)
    matrix = _trace_matrix(trace_title, candidate_modules, change_plan)
    summary = _risk_summary(change_plan, matrix)
    modules = [
        {
            "module_path": row["module_path"],
            "metadata_object": row["metadata_object"],
            "module_kind": row["module_kind"],
            "impact_edges": row["impact_edges"],
            "risk": row["risk"],
            "coverage": row["coverage"],
        }
        for row in matrix
    ]
    tests = _unique(
        [
            test
            for module in change_plan.get("modules", [])
            for test in _module_tests(module)
        ],
        "id",
    )
    its_links = [
        {
            "section_title": item.get("section_title"),
            "source_file": item.get("source_file"),
            "score": item.get("score"),
        }
        for item in its_context or []
    ]
    now = _now()
    status = (
        "needs_review"
        if summary["high_risk_modules"] or summary["total_impact_edges"] >= 300
        else "draft"
    )
    record = {
        "id": _trace_id(requirement, criteria),
        "title": trace_title,
        "requirement": requirement,
        "acceptance_criteria": criteria,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "candidate_modules": candidate_modules,
        "change_plan": change_plan,
        "trace_matrix": matrix,
        "links": {
            "modules": modules,
            "metadata_objects": _unique(
                [
                    {"ref": row["metadata_object"], "module_kind": row["module_kind"]}
                    for row in matrix
                    if row["metadata_object"]
                ],
                "ref",
            ),
            "tests": tests,
            "its": its_links,
        },
        "risk_summary": summary,
        "next_actions": _next_actions(matrix, summary),
        "caveats": caveats or [],
    }
    record["markdown"] = _markdown(record)
    return record


def save_trace(record: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Upsert a trace record in the local JSON store."""

    items = _load(path)
    saved = dict(record)
    saved["artifact_sync"] = sync_trace_to_artifacts(
        saved,
        artifact_path=_artifact_path_for_trace_store(path, None),
    )
    for index, item in enumerate(items):
        if item.get("id") == saved["id"]:
            saved["created_at"] = item.get("created_at") or saved["created_at"]
            items[index] = saved
            break
    else:
        items.insert(0, saved)
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    _write(items, path)
    return saved


def sync_trace_to_artifacts(
    record: dict[str, Any],
    *,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Project a requirement trace into the internal ALM artifact graph."""

    req_artifact = artifact_graph.create_artifact(
        {
            "id": record["id"],
            "type": "requirement",
            "title": record.get("title") or record["id"],
            "description": record.get("requirement") or "",
            "status": record.get("status") or "draft",
            "owner": "ba",
            "risk": str((record.get("risk_summary") or {}).get("max_risk") or ""),
            "priority": "high"
            if int((record.get("risk_summary") or {}).get("max_risk") or 0) >= 70
            else "medium",
            "tags": ["requirement", "traceability"],
            "source": "requirements_traceability",
            "attributes": {
                "acceptance_criteria": record.get("acceptance_criteria", []),
                "risk_summary": record.get("risk_summary", {}),
                "trace_record_id": record["id"],
            },
        },
        path=artifact_path,
    )

    created = {
        "artifacts": 1,
        "links": 0,
        "artifact_id": req_artifact["id"],
        "errors": [],
    }

    def create_and_link(
        *,
        artifact_id: str,
        artifact_type: str,
        title: str,
        link_type: str,
        attributes: dict[str, Any] | None = None,
        rationale: str | None = None,
    ) -> None:
        try:
            artifact_graph.create_artifact(
                {
                    "id": artifact_id,
                    "type": artifact_type,
                    "title": title,
                    "status": "linked",
                    "source": "requirements_traceability",
                    "attributes": attributes or {},
                },
                path=artifact_path,
            )
            created["artifacts"] += 1
            artifact_graph.link_artifacts(
                source_id=req_artifact["id"],
                target_id=artifact_id,
                link_type=link_type,
                rationale=rationale,
                path=artifact_path,
            )
            created["links"] += 1
        except (KeyError, ValueError) as exc:
            created["errors"].append(str(exc))

    for module in (record.get("links") or {}).get("modules", []):
        module_path = module.get("module_path")
        if not module_path:
            continue
        create_and_link(
            artifact_id=_stable_artifact_id("bsl", str(module_path)),
            artifact_type="bsl_module",
            title=str(module_path),
            link_type="implements",
            attributes=module,
            rationale="Requirement trace candidate module.",
        )

    for metadata in (record.get("links") or {}).get("metadata_objects", []):
        ref = metadata.get("ref")
        if not ref:
            continue
        create_and_link(
            artifact_id=_stable_artifact_id("meta", str(ref)),
            artifact_type="metadata_object",
            title=str(ref),
            link_type="impacts",
            attributes=metadata,
            rationale="Requirement trace candidate metadata object.",
        )

    for test in (record.get("links") or {}).get("tests", []):
        selector = test.get("selector") or test.get("id") or test.get("path")
        if not selector:
            continue
        create_and_link(
            artifact_id=_stable_artifact_id("test", str(selector)),
            artifact_type="test_case",
            title=str(selector),
            link_type="tested_by",
            attributes=test,
            rationale="Requirement trace candidate verification test.",
        )

    return created


def transition_trace(
    trace_id: str,
    *,
    status: str,
    actor: str,
    reason: str | None = None,
    path: Path | None = None,
    artifact_path: Path | None = None,
) -> dict[str, Any]:
    """Move a stored requirement trace through the internal review lifecycle."""

    clean_status = status.strip()
    if clean_status not in {
        "draft",
        "needs_review",
        "reviewed",
        "approved",
        "baselined",
        "changed",
        "deprecated",
        "rejected",
    }:
        raise ValueError(f"Unsupported requirement trace status: {status}")

    items = _load(path)
    now = _now()
    for index, item in enumerate(items):
        if item.get("id") != trace_id:
            continue
        updated = dict(item)
        updated["status"] = clean_status
        updated["updated_at"] = now
        decisions = list(updated.get("decision_log") or [])
        decisions.insert(
            0,
            {
                "at": now,
                "actor": actor.strip() or "system",
                "status": clean_status,
                "reason": (reason or "").strip(),
            },
        )
        updated["decision_log"] = decisions
        sync = sync_trace_to_artifacts(
            updated,
            artifact_path=_artifact_path_for_trace_store(path, artifact_path),
        )
        updated["artifact_sync"] = sync
        items[index] = updated
        items.sort(key=lambda row: row.get("updated_at", ""), reverse=True)
        _write(items, path)
        return updated
    raise KeyError(f"Requirement trace not found: {trace_id}")


def list_traces(*, limit: int = 50, path: Path | None = None) -> dict[str, Any]:
    """List stored requirement traces without returning heavy change-plan payloads."""

    target = path or STORE_PATH
    items = _load(target)
    summaries = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "status": item.get("status"),
            "updated_at": item.get("updated_at"),
            "risk_summary": item.get("risk_summary", {}),
            "next_actions": item.get("next_actions", [])[:3],
        }
        for item in items[: max(1, limit)]
    ]
    return {"items": summaries, "total": len(items), "path": str(target)}


def get_trace(trace_id: str, path: Path | None = None) -> dict[str, Any] | None:
    """Return one stored requirement trace by id."""

    for item in _load(path):
        if item.get("id") == trace_id:
            return item
    return None
