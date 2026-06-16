"""Static 1C security posture over EDT metadata and BSL code."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
import re

from src.services.rentgen.metadata_data_governance import EXCHANGE_TYPES
from src.services.rentgen.metadata_graph import DEFAULT_CONFIG_PATH, _enrich_object, build_metadata_graph
from src.services.rentgen.metadata_insights import (
    diff_metadata_snapshot,
    list_metadata_snapshots,
)


SECURITY_RULES: list[dict[str, Any]] = [
    {
        "id": "privileged-mode",
        "category": "privileged_code_paths",
        "severity": "high",
        "title": "Privileged mode call",
        "needles": ("установитьпривилегированныйрежим", "setprivilegedmode"),
        "recommendation": "Verify the caller, narrow privileged scope and add explicit tests for denied access.",
    },
    {
        "id": "dynamic-execute",
        "category": "dynamic_execute_paths",
        "severity": "high",
        "title": "Dynamic code execution",
        "needles": ("выполнить(", "execute("),
        "recommendation": "Replace dynamic execution with typed calls or whitelist-controlled dispatch.",
    },
    {
        "id": "http-client",
        "category": "integration_code_paths",
        "severity": "medium",
        "title": "HTTP client call",
        "needles": ("httpсоединение", "httpconnection", "httpзапрос", "httprequest"),
        "recommendation": "Document endpoint ownership, authentication and timeout/error handling.",
    },
    {
        "id": "web-service-client",
        "category": "integration_code_paths",
        "severity": "medium",
        "title": "Web service client call",
        "needles": ("wsпрокси", "wsproxy", "webservicedefinitions", "webservice"),
        "recommendation": "Review service contract, credentials storage and release compatibility.",
    },
    {
        "id": "external-process",
        "category": "integration_code_paths",
        "severity": "high",
        "title": "External process or COM call",
        "needles": ("comобъект", "comobject", "запуститьприложение", "runapp", "wscript.shell"),
        "recommendation": "Route through an approved integration boundary and audit command input.",
    },
]

DYNAMIC_EXECUTE_RE = re.compile(r"(?<![.\w])(?:выполнить|execute)\s*\(")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _config_path(config_path: str | None) -> Path:
    return Path(config_path).resolve() if config_path else DEFAULT_CONFIG_PATH.resolve()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_prefix(path: Path, max_file_bytes: int) -> str:
    try:
        with path.open("rb") as fh:
            data = fh.read(max_file_bytes)
    except OSError:
        return ""
    return data.decode("utf-8", errors="ignore")


def _append_limited(items: list[dict[str, Any]], item: dict[str, Any], limit: int) -> None:
    if len(items) < limit:
        items.append(item)


def _rule_matches(rule: dict[str, Any], folded_line: str) -> bool:
    if rule["id"] == "dynamic-execute":
        return bool(DYNAMIC_EXECUTE_RE.search(folded_line))
    return any(needle in folded_line for needle in rule["needles"])


def _scan_bsl_security(
    config_path: Path,
    *,
    limit: int,
    module_limit: int,
    max_file_bytes: int,
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "privileged_code_paths": [],
        "dynamic_execute_paths": [],
        "integration_code_paths": [],
    }
    totals: Counter[str] = Counter()
    by_rule: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()
    scanned = 0
    skipped_large = 0
    truncated = False

    if not config_path.exists():
        return {
            "scanned_modules": 0,
            "scan_limit": module_limit,
            "truncated": False,
            "max_file_bytes": max_file_bytes,
            "skipped_large": 0,
            "totals": dict(totals),
            "by_rule": dict(by_rule),
            "by_severity": dict(by_severity),
            **buckets,
        }

    for path in config_path.rglob("*.bsl"):
        if scanned >= module_limit:
            truncated = True
            break
        scanned += 1
        try:
            if path.stat().st_size > max_file_bytes:
                skipped_large += 1
        except OSError:
            continue

        text = _read_prefix(path, max_file_bytes)
        if not text:
            continue

        rel_path = _relative(path, config_path)
        seen_on_line: set[tuple[str, int]] = set()
        for line_no, line in enumerate(text.splitlines(), start=1):
            folded = line.casefold()
            for rule in SECURITY_RULES:
                if not _rule_matches(rule, folded):
                    continue
                key = (rule["id"], line_no)
                if key in seen_on_line:
                    continue
                seen_on_line.add(key)
                category = rule["category"]
                severity = rule["severity"]
                totals[category] += 1
                by_rule[rule["id"]] += 1
                by_severity[severity] += 1
                _append_limited(
                    buckets[category],
                    {
                        "module_path": rel_path,
                        "line": line_no,
                        "severity": severity,
                        "rule_id": rule["id"],
                        "title": rule["title"],
                        "snippet": line.strip()[:220],
                        "recommendation": rule["recommendation"],
                    },
                    limit,
                )

    return {
        "scanned_modules": scanned,
        "scan_limit": module_limit,
        "truncated": truncated,
        "max_file_bytes": max_file_bytes,
        "skipped_large": skipped_large,
        "totals": dict(totals),
        "by_rule": dict(by_rule),
        "by_severity": dict(by_severity),
        **buckets,
    }


def _exchange_objects(graph: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    objects = []
    for obj in graph.get("objects", []):
        if obj.get("type") not in EXCHANGE_TYPES:
            continue
        severity = "high" if obj["type"] in {"ExternalDataSource", "HTTPService", "WebService"} else "medium"
        objects.append(
            {
                "ref": obj["ref"],
                "type": obj["type"],
                "name": obj["name"],
                "path": obj["path"],
                "severity": severity,
                "message": "Metadata object exposes exchange or external integration surface.",
            }
        )
        if len(objects) >= limit:
            break
    return objects


def _bounded_role_review(graph: dict[str, Any], limit: int) -> dict[str, Any]:
    roles = [obj for obj in graph.get("objects", []) if obj.get("type") == "Role"]
    findings: list[dict[str, Any]] = []
    by_right: Counter[str] = Counter()
    roles_reviewed = 0
    roles_with_rights = 0
    total_rights = 0
    dangerous_total = 0

    for role in roles[:limit]:
        roles_reviewed += 1
        enriched = _enrich_object(graph, role)
        rights = (enriched or {}).get("rights")
        if not rights:
            findings.append(
                {
                    "role": role["ref"],
                    "severity": "low",
                    "code": "role-without-rights",
                    "message": "Role has no Rights.xml or rights could not be parsed.",
                    "details": {"path": role["path"]},
                }
            )
            continue

        roles_with_rights += 1
        total_rights += int(rights.get("rights") or 0)
        dangerous_total += int(rights.get("dangerous_total") or 0)
        by_right.update(rights.get("by_right") or {})

        if rights.get("dangerous_total"):
            findings.append(
                {
                    "role": role["ref"],
                    "severity": "high",
                    "code": "dangerous-rights",
                    "message": "Role grants write/delete/admin-class rights.",
                    "details": {
                        "dangerous_total": rights["dangerous_total"],
                        "examples": rights.get("dangerous", [])[:10],
                        "rights_path": rights.get("path"),
                    },
                }
            )
        if int(rights.get("rights") or 0) > 5000:
            findings.append(
                {
                    "role": role["ref"],
                    "severity": "medium",
                    "code": "broad-role",
                    "message": "Role grants a very broad rights surface.",
                    "details": {"rights": rights["rights"], "objects": rights.get("objects", 0)},
                }
            )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["role"], item["code"]))
    caveats = [
        "Security posture role review is static EDT rights analysis.",
    ]
    if len(roles) > roles_reviewed:
        caveats.append("Role review reached limit; increase limit for full role coverage.")

    return {
        "summary": {
            "roles": len(roles),
            "roles_reviewed": roles_reviewed,
            "roles_with_rights": roles_with_rights,
            "total_rights": total_rights,
            "dangerous_rights": dangerous_total,
            "findings": len(findings),
            "by_right": dict(by_right.most_common(20)),
        },
        "findings": findings[:limit],
        "caveats": caveats,
    }


def _role_diff(snapshot_id: str | None, *, config_path: Path, limit: int) -> dict[str, Any]:
    snapshots = list_metadata_snapshots()
    if not snapshot_id:
        return {
            "included": False,
            "available_snapshots": len(snapshots),
            "latest_snapshot": snapshots[0] if snapshots else None,
            "message": "Pass snapshot_id to compare role additions/removals and rights path changes.",
        }

    try:
        diff = diff_metadata_snapshot(snapshot_id, config_path=str(config_path), limit=limit)
    except FileNotFoundError as exc:
        return {
            "included": False,
            "available_snapshots": len(snapshots),
            "latest_snapshot": snapshots[0] if snapshots else None,
            "error": str(exc),
        }

    added = [item for item in diff.get("added", []) if item.get("type") == "Role"]
    removed = [item for item in diff.get("removed", []) if item.get("type") == "Role"]
    changed = [
        item
        for item in diff.get("changed", [])
        if item.get("type") == "Role" or "rights_path" in (item.get("changes") or {})
    ]
    return {
        "included": True,
        "snapshot": diff.get("snapshot"),
        "summary": {
            "added_roles": len(added),
            "removed_roles": len(removed),
            "changed_roles": len(changed),
        },
        "added_roles": added[:limit],
        "removed_roles": removed[:limit],
        "changed_roles": changed[:limit],
    }


def _decision(summary: dict[str, Any]) -> dict[str, Any]:
    high = int(summary["by_severity"].get("high", 0))
    medium = int(summary["by_severity"].get("medium", 0))
    low = int(summary["by_severity"].get("low", 0))
    score = max(0, 100 - high * 8 - medium * 3 - low)
    if high >= 50:
        status = "fail"
    elif high or medium or low:
        status = "warn"
    else:
        status = "pass"
    return {"status": status, "score": score, "high": high, "medium": medium, "low": low}


def _recommendations(report: dict[str, Any]) -> list[dict[str, Any]]:
    summary = report["summary"]
    items: list[dict[str, Any]] = []
    if summary["dangerous_rights"]:
        items.append(
            {
                "owner": "security",
                "severity": "high",
                "title": "Review dangerous role rights before release",
                "details": {"dangerous_rights": summary["dangerous_rights"]},
            }
        )
    if summary["privileged_code_paths"]:
        items.append(
            {
                "owner": "architect",
                "severity": "high",
                "title": "Constrain privileged mode scopes",
                "details": {"paths": summary["privileged_code_paths"]},
            }
        )
    if summary["dynamic_execute_paths"]:
        items.append(
            {
                "owner": "developer",
                "severity": "high",
                "title": "Replace dynamic execution paths",
                "details": {"paths": summary["dynamic_execute_paths"]},
            }
        )
    if summary["external_exposure"]:
        items.append(
            {
                "owner": "security",
                "severity": "medium",
                "title": "Validate external integration contracts and secrets",
                "details": {"exposure": summary["external_exposure"]},
            }
        )
    if not items:
        items.append(
            {
                "owner": "lead",
                "severity": "low",
                "title": "Keep security posture in release gate",
                "details": {"status": "no static high-risk findings"},
            }
        )
    return items


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1cAI 1C Security Posture",
        "",
        f"Status: **{report['decision']['status'].upper()}**",
        f"Score: **{report['decision']['score']}**",
        "",
        "## Summary",
        "",
    ]
    for key in (
        "roles",
        "dangerous_rights",
        "privileged_code_paths",
        "dynamic_execute_paths",
        "external_exposure",
        "findings",
    ):
        lines.append(f"- {key}: {report['summary'].get(key, 0)}")

    lines.extend(["", "## Actions", ""])
    for item in report["recommendations"]:
        lines.append(f"- **{item['severity']}** {item['owner']}: {item['title']}")

    lines.extend(["", "## Caveats", ""])
    for caveat in report["caveats"]:
        lines.append(f"- {caveat}")
    return "\n".join(lines)


@lru_cache(maxsize=8)
def build_security_posture(
    *,
    config_path: str | None = None,
    limit: int = 200,
    module_limit: int = 2500,
    max_file_bytes: int = 400_000,
    snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Build a local, explainable 1C security posture report."""

    config = _config_path(config_path)
    graph = build_metadata_graph(str(config))
    if not graph.get("available"):
        report = {
            "available": False,
            "generated_at": _now(),
            "config_path": str(config),
            "decision": {"status": "fail", "score": 0, "high": 0, "medium": 0, "low": 0},
            "summary": {"findings": 0, "by_severity": {}},
            "role_review": {"summary": {}, "findings": []},
            "role_diff": _role_diff(snapshot_id, config_path=config, limit=limit),
            "privileged_code_paths": [],
            "dynamic_execute_paths": [],
            "integration_exposure": {"metadata_objects": [], "code_paths": []},
            "code_scan": {"scanned_modules": 0, "truncated": False},
            "recommendations": [],
            "caveats": ["Metadata graph is unavailable; unpack EDT configuration first."],
        }
        report["markdown"] = _markdown({**report, "recommendations": report["recommendations"] or []})
        return report

    role_review = _bounded_role_review(graph, limit)
    code_scan = _scan_bsl_security(
        config,
        limit=limit,
        module_limit=module_limit,
        max_file_bytes=max_file_bytes,
    )
    exchange_objects = _exchange_objects(graph, limit)

    by_severity: Counter[str] = Counter(code_scan["by_severity"])
    for finding in role_review.get("findings", []):
        by_severity[finding.get("severity", "low")] += 1
    for item in exchange_objects:
        by_severity[item["severity"]] += 1

    role_summary = role_review.get("summary", {})
    summary = {
        "metadata_objects": graph["summary"].get("total_objects", 0),
        "roles": role_summary.get("roles", 0),
        "roles_with_rights": role_summary.get("roles_with_rights", 0),
        "dangerous_rights": role_summary.get("dangerous_rights", 0),
        "role_findings": len(role_review.get("findings", [])),
        "privileged_code_paths": int(code_scan["totals"].get("privileged_code_paths", 0)),
        "dynamic_execute_paths": int(code_scan["totals"].get("dynamic_execute_paths", 0)),
        "integration_code_paths": int(code_scan["totals"].get("integration_code_paths", 0)),
        "exchange_objects": len(exchange_objects),
        "external_exposure": len(exchange_objects) + int(code_scan["totals"].get("integration_code_paths", 0)),
        "scanned_modules": code_scan["scanned_modules"],
        "findings": (
            len(role_review.get("findings", []))
            + int(code_scan["totals"].get("privileged_code_paths", 0))
            + int(code_scan["totals"].get("dynamic_execute_paths", 0))
            + int(code_scan["totals"].get("integration_code_paths", 0))
            + len(exchange_objects)
        ),
        "by_severity": dict(by_severity),
    }

    role_diff = _role_diff(snapshot_id, config_path=config, limit=limit)
    report = {
        "available": True,
        "generated_at": _now(),
        "config_path": str(config),
        "decision": _decision(summary),
        "summary": summary,
        "role_review": role_review,
        "role_diff": role_diff,
        "privileged_code_paths": code_scan["privileged_code_paths"],
        "dynamic_execute_paths": code_scan["dynamic_execute_paths"],
        "integration_exposure": {
            "metadata_objects": exchange_objects,
            "code_paths": code_scan["integration_code_paths"],
            "by_type": dict(Counter(item["type"] for item in exchange_objects)),
        },
        "code_scan": {
            "scanned_modules": code_scan["scanned_modules"],
            "scan_limit": code_scan["scan_limit"],
            "truncated": code_scan["truncated"],
            "max_file_bytes": code_scan["max_file_bytes"],
            "skipped_large": code_scan["skipped_large"],
            "by_rule": code_scan["by_rule"],
        },
        "caveats": [
            "Static analysis does not prove runtime authorization or secret handling.",
            "Privileged mode and external calls can be legitimate; every finding needs owner-approved context.",
            "Code scan is bounded by module_limit and max_file_bytes for predictable runtime.",
        ],
    }
    if code_scan["truncated"]:
        report["caveats"].append("BSL scan reached module_limit; rerun with a higher limit for full coverage.")
    report["recommendations"] = _recommendations(report)
    report["markdown"] = _markdown(report)
    return report
