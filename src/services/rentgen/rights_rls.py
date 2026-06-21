"""Rights & RLS simulator over EDT Role/Rights.xml metadata."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen.metadata_graph import DEFAULT_CONFIG_PATH, build_metadata_graph
from src.services.rentgen.path_safety import confine_path


DANGEROUS_RIGHTS = {
    "Delete",
    "InteractiveDelete",
    "Update",
    "Edit",
    "Administration",
    "InteractiveMarkForDeletion",
    "InteractiveClearDeletionMark",
}
WRITE_RIGHTS = DANGEROUS_RIGHTS | {"Insert", "InteractiveInsert", "Posting", "UndoPosting"}
# Allow-list of recognized EDT Rights.xml RLS row-restriction elements. In the
# 1C roles schema (xmlns="http://v8.1c.ru/8.2/roles") a row-level restriction is
# carried by a <restrictionByCondition> (nested in a <right>) holding a
# <condition>, or by a <restriction> element. Detection is by the actual XML
# element tag (namespace-stripped, case-insensitive) — never by substring-
# matching raw text, which both misses real restrictions and false-positives on
# unrelated content. Unknown/unparseable formats stay "not confirmed".
RLS_CONDITION_TAGS = frozenset({"restrictionbycondition", "restriction", "condition"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _safe_parse(path: Path) -> ET.Element | None:
    try:
        return ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None


def _first_text(element: ET.Element, name: str) -> str:
    for child in element.iter():
        if _local(child.tag) == name and child.text:
            value = child.text.strip()
            if value:
                return value
    return ""


def _enabled_rights(object_element: ET.Element) -> list[str]:
    rights: list[str] = []
    for right in object_element:
        if _local(right.tag) != "right":
            continue
        right_name = _first_text(right, "name")
        value = _first_text(right, "value").casefold()
        if right_name and value == "true":
            rights.append(right_name)
    return rights


def _rls_rules(object_element: ET.Element, limit: int = 8) -> list[dict[str, str]]:
    """Detect RLS row-restrictions by recognized XML element tag, not text.

    A restriction is confirmed only when an element's local tag is on the
    ``RLS_CONDITION_TAGS`` allow-list. The condition text (if any) is captured
    for context, but its presence/content is never used to decide whether a
    restriction exists — so an empty-bodied ``<restrictionByCondition>`` still
    counts and unrelated prose never false-positives.

    In the EDT schema a row restriction is a ``<restrictionByCondition>`` /
    ``<restriction>`` wrapper holding a ``<condition>``. We count each wrapper
    once (reading its nested ``<condition>`` text) and only treat a bare
    ``<condition>`` as its own rule when it is not already inside a counted
    wrapper, so one logical restriction is not double-counted.
    """
    wrapper_tags = {"restrictionbycondition", "restriction"}
    counted_conditions: set[int] = set()
    rules: list[dict[str, str]] = []
    for node in object_element.iter():
        local = _local(node.tag).casefold()
        if local not in RLS_CONDITION_TAGS:
            continue
        if local in wrapper_tags:
            text = (node.text or "").strip()
            for child in node.iter():
                if _local(child.tag).casefold() == "condition":
                    counted_conditions.add(id(child))
                    if not text and child.text and child.text.strip():
                        text = child.text.strip()
            rules.append({"tag": _local(node.tag), "text": text[:220]})
        elif id(node) not in counted_conditions:
            text = (node.text or "").strip()
            rules.append({"tag": _local(node.tag), "text": text[:220]})
        if len(rules) >= limit:
            break
    return rules


def _parse_role_rights(
    *,
    config_path: Path,
    role: dict[str, Any],
    object_limit: int,
) -> dict[str, Any]:
    role_path = config_path / str(role.get("path", ""))
    rights_path = role_path.with_suffix("") / "Ext" / "Rights.xml"
    if not rights_path.exists():
        return {
            "role": role.get("ref"),
            "name": role.get("name"),
            "path": role.get("path"),
            "rights_path": None,
            "objects": 0,
            "rights": 0,
            "dangerous_rights": 0,
            "rls_rules": 0,
            "matrix": [],
            "missing_rights_xml": True,
        }

    root = _safe_parse(rights_path)
    if root is None:
        return {
            "role": role.get("ref"),
            "name": role.get("name"),
            "path": role.get("path"),
            "rights_path": rights_path.relative_to(config_path).as_posix(),
            "objects": 0,
            "rights": 0,
            "dangerous_rights": 0,
            "rls_rules": 0,
            "matrix": [],
            "parse_error": True,
        }

    matrix: list[dict[str, Any]] = []
    rights_total = 0
    dangerous_total = 0
    rls_total = 0
    by_right: Counter[str] = Counter()

    for object_element in root.iter():
        if _local(object_element.tag) != "object":
            continue
        object_name = _first_text(object_element, "name") or "unknown"
        rights = _enabled_rights(object_element)
        rls = _rls_rules(object_element)
        dangerous = [right for right in rights if right in DANGEROUS_RIGHTS]
        rights_total += len(rights)
        dangerous_total += len(dangerous)
        rls_total += len(rls)
        by_right.update(rights)
        if len(matrix) < object_limit:
            matrix.append(
                {
                    "role": role.get("ref"),
                    "object": object_name,
                    "rights": rights,
                    "dangerous": dangerous,
                    "can_read": "Read" in rights,
                    "can_write": any(right in WRITE_RIGHTS for right in rights),
                    "can_admin": "Administration" in rights,
                    "rls": rls,
                }
            )

    return {
        "role": role.get("ref"),
        "name": role.get("name"),
        "path": role.get("path"),
        "rights_path": rights_path.relative_to(config_path).as_posix(),
        "objects": sum(1 for _ in root.iter() if _local(_.tag) == "object"),
        "rights": rights_total,
        "dangerous_rights": dangerous_total,
        "rls_rules": rls_total,
        "by_right": dict(by_right.most_common(20)),
        "matrix": matrix,
        "missing_rights_xml": False,
    }


def _findings(role_reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for role in role_reports:
        if role.get("missing_rights_xml"):
            findings.append(
                {
                    "severity": "low",
                    "code": "role-without-rights",
                    "role": role["role"],
                    "message": "Role has no Rights.xml or rights could not be parsed.",
                    "details": {"path": role.get("path")},
                }
            )
        if role.get("parse_error"):
            findings.append(
                {
                    "severity": "medium",
                    "code": "rights-parse-error",
                    "role": role["role"],
                    "message": "Rights.xml could not be parsed.",
                    "details": {"rights_path": role.get("rights_path")},
                }
            )
        if int(role.get("dangerous_rights") or 0):
            findings.append(
                {
                    "severity": "high",
                    "code": "dangerous-rights",
                    "role": role["role"],
                    "message": "Role grants write/delete/admin-class rights.",
                    "details": {
                        "dangerous_rights": role["dangerous_rights"],
                        "rights_path": role.get("rights_path"),
                    },
                }
            )
        if int(role.get("rights") or 0) > 5000:
            findings.append(
                {
                    "severity": "medium",
                    "code": "broad-role",
                    "role": role["role"],
                    "message": "Role grants a very broad rights surface.",
                    "details": {"rights": role["rights"], "objects": role.get("objects", 0)},
                }
            )
        if int(role.get("rls_rules") or 0) == 0 and int(role.get("rights") or 0) > 0:
            findings.append(
                {
                    "severity": "medium",
                    "code": "rls-not-detected",
                    "role": role["role"],
                    "message": "Role has object rights but no RLS restrictions were detected in Rights.xml.",
                    "details": {"rights": role["rights"]},
                }
            )
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda item: (order.get(item["severity"], 9), item["role"], item["code"]))
    return findings


def _scan_role_reports(
    *,
    root: Path,
    role_limit: int,
    object_limit: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    graph = build_metadata_graph(str(root))
    roles = [obj for obj in graph.get("objects", []) if obj.get("type") == "Role"][:role_limit]
    role_reports = [
        _parse_role_rights(config_path=root, role=role, object_limit=object_limit)
        for role in roles
    ]
    matrix = [row for role in role_reports for row in role.get("matrix", [])]
    return graph, roles, role_reports, matrix


def _rights_fingerprint(role_reports: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for role in role_reports:
        role_name = str(role.get("role") or role.get("name") or "unknown")
        for matrix_row in role.get("matrix", []):
            object_name = str(matrix_row.get("object") or "unknown")
            for right in matrix_row.get("rights") or []:
                key = (role_name, object_name, str(right))
                rows[key] = {
                    "role": role_name,
                    "object": object_name,
                    "right": str(right),
                    "dangerous": str(right) in DANGEROUS_RIGHTS,
                    "can_write": str(right) in WRITE_RIGHTS,
                }
    return rows


def _rights_diff(
    *,
    baseline_root: Path | None,
    current_role_reports: list[dict[str, Any]],
    role_limit: int,
    object_limit: int,
) -> dict[str, Any]:
    if baseline_root is None:
        return {
            "enabled": False,
            "status": "not_provided",
            "baseline_path": None,
            "summary": {
                "added_rights": 0,
                "removed_rights": 0,
                "added_dangerous_rights": 0,
                "removed_dangerous_rights": 0,
                "changed_roles": 0,
            },
            "changes": [],
            "caveat": "Pass baseline_config_path to compare Rights.xml snapshots.",
        }

    baseline_graph, _, baseline_reports, _ = _scan_role_reports(
        root=baseline_root,
        role_limit=role_limit,
        object_limit=object_limit,
    )
    baseline = _rights_fingerprint(baseline_reports)
    current = _rights_fingerprint(current_role_reports)
    added_keys = sorted(set(current) - set(baseline))
    removed_keys = sorted(set(baseline) - set(current))
    changes: list[dict[str, Any]] = []
    for key in added_keys:
        row = current[key]
        changes.append({"change": "added", **row})
    for key in removed_keys:
        row = baseline[key]
        changes.append({"change": "removed", **row})
    changed_roles = {row["role"] for row in changes}
    added_dangerous = sum(1 for key in added_keys if current[key]["dangerous"])
    removed_dangerous = sum(1 for key in removed_keys if baseline[key]["dangerous"])
    if added_dangerous:
        status = "risk"
    elif changes:
        status = "watch"
    else:
        status = "ready"
    caveat = None
    if not baseline_graph.get("available"):
        status = "risk"
        caveat = "Baseline configuration source is not available; rights diff is incomplete."
    return {
        "enabled": True,
        "status": status,
        "baseline_path": str(baseline_root),
        "summary": {
            "added_rights": len(added_keys),
            "removed_rights": len(removed_keys),
            "added_dangerous_rights": added_dangerous,
            "removed_dangerous_rights": removed_dangerous,
            "changed_roles": len(changed_roles),
        },
        "changes": changes[:200],
        "caveat": caveat,
    }


def _decision(summary: dict[str, Any], findings: list[dict[str, Any]]) -> dict[str, Any]:
    high = sum(1 for item in findings if item["severity"] == "high")
    medium = sum(1 for item in findings if item["severity"] == "medium")
    score = max(0, 100 - high * 16 - medium * 7 - summary["roles_without_rights"] * 3)
    if high:
        status = "risk"
        headline = "Есть роли с опасными правами; релиз/обновление требует security gate."
    elif medium:
        status = "watch"
        headline = "Матрица прав собрана, но RLS/широкие роли требуют подтверждения."
    else:
        status = "ready"
        headline = "Критичных находок по правам не найдено в локальных Rights.xml."
    return {"status": status, "score": score, "headline": headline}


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rights & RLS Simulator",
        "",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Roles: **{report['summary']['roles']}**",
        f"Dangerous rights: **{report['summary']['dangerous_rights']}**",
        f"RLS rules detected: **{report['summary']['rls_rules']}**",
        "",
        "## Findings",
        "",
    ]
    if report["findings"]:
        for item in report["findings"][:30]:
            lines.append(f"- **{item['severity']}** {item['role']}: {item['message']}")
    else:
        lines.append("- No findings.")
    lines.extend(["", "## Actions", ""])
    for item in report["recommended_actions"]:
        lines.append(f"- **{item['owner']}** [{item['severity']}] {item['title']}")
    diff = report.get("diff") or {}
    if diff.get("enabled"):
        diff_summary = diff.get("summary") or {}
        lines.extend(["", "## Rights Diff", ""])
        lines.append(f"- Status: **{diff.get('status', 'unknown')}**")
        lines.append(
            f"- Added rights: {diff_summary.get('added_rights', 0)}, "
            f"added dangerous: {diff_summary.get('added_dangerous_rights', 0)}, "
            f"changed roles: {diff_summary.get('changed_roles', 0)}"
        )
    return "\n".join(lines)


def build_rights_rls(
    *,
    config_path: str | None = None,
    baseline_config_path: str | None = None,
    role_limit: int = 120,
    object_limit: int = 400,
) -> dict[str, Any]:
    """Build a role/object/action matrix and security gate from local Rights.xml files."""

    # Caller-supplied paths are read off disk, so they must be confined to the
    # allowed data roots — otherwise an authenticated caller can point the
    # analyzer at C:\Windows / secrets and have file content reflected back.
    # ``confine_path`` raises ValueError on traversal; the API maps it to 400.
    root = (
        confine_path(config_path, label="config_path")
        if config_path
        else DEFAULT_CONFIG_PATH.resolve()
    )
    baseline_root = (
        confine_path(baseline_config_path, label="baseline_config_path")
        if baseline_config_path
        else None
    )
    graph, roles, role_reports, matrix = _scan_role_reports(
        root=root,
        role_limit=role_limit,
        object_limit=object_limit,
    )
    findings = _findings(role_reports)
    if not graph.get("available"):
        findings.append(
            {
                "severity": "high",
                "code": "metadata-source-missing",
                "role": "configuration",
                "message": "EDT/XML configuration source is not available.",
                "details": {"config_path": str(root)},
            }
        )
    # Honest-coverage invariant: zero analyzed roles is NOT a clean bill of
    # health — the source was empty/unreadable or has no Roles, so nothing was
    # certified. Emit a high finding (which forces decision status -> risk, so
    # the gate fails and the score is reduced below 100) instead of fabricating
    # a safe-zero (status:ready / score:100 / gate:pass).
    if len(roles) == 0:
        findings.append(
            {
                "severity": "high",
                "code": "no-roles-analyzed",
                "role": "configuration",
                "message": (
                    "No Roles were parsed from the configuration source; rights "
                    "cannot be certified. The path may be empty, unreadable, or "
                    "missing a Roles/ metadata folder."
                ),
                "details": {"config_path": str(root), "roles": 0},
            }
        )
    by_right: Counter[str] = Counter()
    for role in role_reports:
        by_right.update(role.get("by_right") or {})

    summary = {
        "roles": len(roles),
        "roles_scanned": len(role_reports),
        "roles_with_rights": sum(1 for role in role_reports if int(role.get("rights") or 0)),
        "roles_without_rights": sum(1 for role in role_reports if role.get("missing_rights_xml")),
        "objects": sum(int(role.get("objects") or 0) for role in role_reports),
        "total_rights": sum(int(role.get("rights") or 0) for role in role_reports),
        "dangerous_rights": sum(int(role.get("dangerous_rights") or 0) for role in role_reports),
        "rls_rules": sum(int(role.get("rls_rules") or 0) for role in role_reports),
        "findings": len(findings),
        "by_right": dict(by_right.most_common(20)),
        "matrix_rows": len(matrix),
        "role_limit": role_limit,
        "object_limit": object_limit,
    }
    diff = _rights_diff(
        baseline_root=baseline_root,
        current_role_reports=role_reports,
        role_limit=role_limit,
        object_limit=object_limit,
    )
    if diff["summary"]["added_dangerous_rights"]:
        findings.append(
            {
                "severity": "high",
                "code": "rights-diff-added-dangerous",
                "role": "diff",
                "message": "Rights diff adds dangerous write/delete/admin-class rights.",
                "details": diff["summary"],
            }
        )
        summary["findings"] = len(findings)
    decision = _decision(summary, findings)
    # Hard guard for the fake-safe-zero invariant: even if scoring weights ever
    # change, zero analyzed roles must never certify. Force a non-pass status
    # and cap the score so the gate below cannot resolve to pass/score:100.
    if len(roles) == 0 and decision["status"] == "ready":
        decision = {
            "status": "watch",
            "score": min(decision["score"], 50),
            "headline": "Источник прав пуст/недоступен — нет ролей для сертификации.",
        }
    recommended_actions = [
        {
            "owner": "security",
            "severity": "high",
            "title": "Разобрать роли с Delete/Update/Administration перед релизом.",
            "details": {"dangerous_rights": summary["dangerous_rights"]},
        },
        {
            "owner": "architect",
            "severity": "medium",
            "title": "Сопоставить RLS restrictions с affected documents/registers.",
            "details": {"rls_rules": summary["rls_rules"]},
        },
        {
            "owner": "qa",
            "severity": "medium",
            "title": "Добавить negative access tests для ролей с широкими правами.",
            "details": {"roles_with_rights": summary["roles_with_rights"]},
        },
    ]
    report: dict[str, Any] = {
        "available": bool(graph.get("available")),
        "generated_at": _now(),
        "config_path": str(root),
        "configuration": graph.get("configuration", {}),
        "decision": decision,
        "summary": summary,
        "roles": role_reports,
        "diff": diff,
        "matrix": matrix[:object_limit],
        "findings": findings[:200],
        "gate": {
            "status": "fail" if decision["status"] == "risk" else "warn" if decision["status"] == "watch" else "pass",
            "block_release": decision["status"] == "risk",
            "reasons": [item["message"] for item in findings[:10]],
        },
        "recommended_actions": recommended_actions,
        "caveats": [
            "Rights & RLS Simulator v1 reads local EDT Rights.xml only; runtime session parameters and custom privileged code require separate validation.",
            "RLS detection is conservative: unknown XML restriction formats are surfaced as caveats or missing-RLS findings.",
            "Admin/service roles may intentionally carry dangerous rights; whitelist/SoD policy is a next hardening layer.",
        ],
    }
    report["markdown"] = _markdown(report)
    return report
