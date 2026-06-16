"""Release-readiness report for enterprise 1C change delivery."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any

from src.services.bsl_diagnostics import analyze_bsl
from src.services.rentgen.change_plan import (
    assess_ci_gate,
    build_change_plan,
    dedupe,
    extract_added_code,
    extract_diff_modules,
    render_markdown_report,
)
from src.services.rentgen.metadata_graph import FOLDER_TO_TYPE, get_metadata_object
from src.services.rentgen.metadata_insights import (
    diff_metadata_snapshot,
    review_forms,
    security_review,
)


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("severity") or "info") for item in findings)
    return {
        "high": counts.get("high", 0),
        "medium": counts.get("medium", 0),
        "low": counts.get("low", 0),
        "info": counts.get("info", 0),
    }


def _metadata_identifier(module_path: str, item: dict[str, Any]) -> str | None:
    path = PurePosixPath(module_path.replace("\\", "/"))
    parts = path.parts
    if len(parts) >= 2:
        metadata_type = FOLDER_TO_TYPE.get(parts[0])
        if metadata_type:
            return f"{metadata_type}.{parts[1]}"

    canonical = item.get("canonical") or {}
    object_name = canonical.get("object_name")
    if object_name:
        return str(object_name)
    return None


def _standards_findings_from_diff(diff: str | None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for module_path, code in extract_added_code(diff).items():
        result = analyze_bsl(code, module_path=module_path)
        for diagnostic in result["diagnostics"]:
            findings.append(
                {
                    "module_path": module_path,
                    "source": diagnostic["source"],
                    "severity": diagnostic["severity"],
                    "code": diagnostic["code"],
                    "line": diagnostic["line"],
                    "message": diagnostic["message"],
                    "details": diagnostic.get("details", {}),
                }
            )
    findings.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity")), 9),
            str(item.get("module_path") or ""),
            int(item.get("line") or 0),
            str(item.get("code") or ""),
        )
    )
    return findings


def _metadata_surface(plan: dict[str, Any]) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in plan.get("modules", []):
        identifier = _metadata_identifier(item["module_path"], item)
        if not identifier or identifier.casefold() in seen:
            continue
        seen.add(identifier.casefold())
        obj = get_metadata_object(identifier)
        if obj is None:
            objects.append(
                {
                    "identifier": identifier,
                    "found": False,
                    "module_path": item["module_path"],
                }
            )
            continue
        objects.append(
            {
                "identifier": identifier,
                "found": True,
                "type": obj["type"],
                "name": obj["name"],
                "ref": obj["ref"],
                "path": obj["path"],
                "counts": obj["counts"],
                "modules": [module["path"] for module in obj.get("modules", [])],
                "forms": [form["path"] for form in obj.get("forms", [])],
                "references": obj.get("references", [])[:20],
            }
        )

    return {
        "objects": objects,
        "summary": {
            "objects": len(objects),
            "found": sum(1 for item in objects if item.get("found")),
            "forms": sum(int((item.get("counts") or {}).get("forms") or 0) for item in objects),
            "rights": sum(int((item.get("counts") or {}).get("rights") or 0) for item in objects),
            "references": sum(len(item.get("references") or []) for item in objects),
        },
    }


def _form_reviews_for_metadata(
    metadata: dict[str, Any],
    *,
    enabled: bool,
    object_limit: int,
) -> dict[str, Any]:
    if not enabled:
        return {"included": False, "items": [], "summary": {"objects": 0, "forms": 0, "findings": 0}}

    items: list[dict[str, Any]] = []
    for obj in metadata.get("objects", []):
        if not obj.get("found") or not int((obj.get("counts") or {}).get("forms") or 0):
            continue
        if len(items) >= object_limit:
            break
        try:
            review = review_forms(obj["ref"])
        except ValueError as exc:
            items.append({"identifier": obj["identifier"], "error": str(exc), "forms": [], "summary": {"findings": 0}})
            continue
        items.append(review)

    return {
        "included": True,
        "items": items,
        "summary": {
            "objects": len(items),
            "forms": sum(int((item.get("summary") or {}).get("forms_reviewed") or 0) for item in items),
            "findings": sum(int((item.get("summary") or {}).get("findings") or 0) for item in items),
        },
    }


def _collect_form_findings(form_reviews: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for review in form_reviews.get("items", []):
        obj = review.get("object") or {}
        for form in review.get("forms", []):
            form_name = (form.get("form") or {}).get("name")
            for finding in form.get("findings", []):
                findings.append(
                    {
                        "object": obj.get("ref"),
                        "form": form_name,
                        "severity": finding.get("severity", "info"),
                        "code": finding.get("code"),
                        "message": finding.get("message"),
                        "details": finding.get("details", {}),
                    }
                )
    findings.sort(
        key=lambda item: (
            SEVERITY_ORDER.get(str(item.get("severity")), 9),
            str(item.get("object") or ""),
            str(item.get("form") or ""),
            str(item.get("code") or ""),
        )
    )
    return findings


def _test_summary(plan: dict[str, Any]) -> dict[str, Any]:
    tests: list[dict[str, Any]] = []
    for item in plan.get("modules", []):
        for test in item.get("covering_tests", []):
            tests.append({"module_path": item["module_path"], **test})

    by_status = Counter(str(item.get("status") or "unknown") for item in tests)
    high_priority = [item for item in tests if item.get("priority") == "high"]
    mapped = [item for item in tests if item.get("status") == "mapped"]
    return {
        "total": len(tests),
        "high_priority": len(high_priority),
        "mapped": len(mapped),
        "by_status": dict(by_status),
        "items": tests[:80],
    }


def _recommended_actions(
    *,
    gate: dict[str, Any],
    standards_findings: list[dict[str, Any]],
    form_findings: list[dict[str, Any]],
    security: dict[str, Any] | None,
    tests: dict[str, Any],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    for violation in gate.get("violations", [])[:20]:
        actions.append(
            {
                "owner": "lead",
                "severity": "high",
                "kind": "gate",
                "title": "Resolve release gate violation",
                "target": violation.get("module_path"),
                "details": violation,
            }
        )

    for finding in standards_findings[:20]:
        actions.append(
            {
                "owner": "developer",
                "severity": finding.get("severity", "info"),
                "kind": "code-review",
                "title": finding.get("message"),
                "target": finding.get("module_path"),
                "details": finding,
            }
        )

    for finding in form_findings[:20]:
        actions.append(
            {
                "owner": "architect",
                "severity": finding.get("severity", "info"),
                "kind": "form-review",
                "title": finding.get("message"),
                "target": finding.get("object"),
                "details": finding,
            }
        )

    if security:
        for finding in security.get("findings", [])[:20]:
            actions.append(
                {
                    "owner": "security",
                    "severity": finding.get("severity", "info"),
                    "kind": "security",
                    "title": finding.get("message"),
                    "target": finding.get("role"),
                    "details": finding,
                }
            )

    if tests.get("mapped", 0) == 0 and tests.get("total", 0):
        actions.append(
            {
                "owner": "qa",
                "severity": "medium",
                "kind": "tests",
                "title": "Confirm or add exact YAxUnit/Vanessa mapping for this change",
                "target": None,
                "details": {"test_summary": {k: v for k, v in tests.items() if k != "items"}},
            }
        )

    actions.sort(key=lambda item: SEVERITY_ORDER.get(str(item.get("severity")), 9))
    return actions[:60]


def _decision(
    *,
    gate: dict[str, Any],
    standards_counts: dict[str, int],
    form_counts: dict[str, int],
    security_counts: dict[str, int],
    metadata_diff: dict[str, Any] | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []

    if gate.get("status") == "fail":
        blockers.append("CI gate has high-risk violations.")
    if standards_counts.get("high", 0):
        blockers.append("Diff diagnostics include high-severity findings.")
    if security_counts.get("high", 0):
        blockers.append("Security review includes high-severity rights findings.")
    if form_counts.get("high", 0):
        blockers.append("Form review includes high-severity findings.")

    if gate.get("status") == "warn":
        warnings.append("CI gate is in warning mode.")
    if standards_counts.get("medium", 0):
        warnings.append("Diff diagnostics include medium-severity findings.")
    if form_counts.get("medium", 0):
        warnings.append("Form review includes medium-severity findings.")
    if security_counts.get("medium", 0):
        warnings.append("Security review includes medium-severity findings.")
    if metadata_diff and int((metadata_diff.get("summary") or {}).get("removed") or 0):
        warnings.append("Metadata snapshot diff contains removed objects.")
    if metadata_diff and int((metadata_diff.get("summary") or {}).get("changed") or 0):
        warnings.append("Metadata snapshot diff contains changed objects.")

    status = "pass"
    if blockers:
        status = "fail"
    elif warnings or gate.get("violations"):
        status = "warn"

    penalty = 0
    penalty += 20 * len(blockers)
    penalty += 8 * len(warnings)
    penalty += 4 * int(gate.get("summary", {}).get("violation_count") or 0)
    penalty += 8 * standards_counts.get("high", 0) + 3 * standards_counts.get("medium", 0)
    penalty += 5 * form_counts.get("medium", 0) + 10 * form_counts.get("high", 0)
    penalty += 8 * security_counts.get("high", 0) + 3 * security_counts.get("medium", 0)

    return {
        "status": status,
        "score": max(0, 100 - min(100, penalty)),
        "blockers": blockers,
        "warnings": warnings,
    }


def _persona_summaries(
    *,
    decision: dict[str, Any],
    plan: dict[str, Any],
    gate: dict[str, Any],
    standards_findings: list[dict[str, Any]],
    metadata: dict[str, Any],
    tests: dict[str, Any],
    security: dict[str, Any] | None,
    form_reviews: dict[str, Any],
) -> dict[str, Any]:
    module_risks = []
    for item in plan.get("modules", []):
        quality = item.get("quality") or {}
        module_risks.append(
            {
                "module_path": item["module_path"],
                "risk": int(quality.get("risk") or 0),
                "impact_total": int(item.get("impact_total") or 0),
                "hotspots": len(item.get("impacted_hotspots") or []),
            }
        )
    module_risks.sort(key=lambda item: (item["risk"], item["impact_total"]), reverse=True)

    return {
        "developer": {
            "changed_modules": len(plan.get("changed_modules", [])),
            "standards_findings": len(standards_findings),
            "top_module_risks": module_risks[:10],
        },
        "architect": {
            "total_impact_edges": plan.get("total_impact_edges", 0),
            "total_impacted_modules": plan.get("total_impacted_modules", 0),
            "metadata_objects": metadata.get("summary", {}).get("found", 0),
            "form_findings": form_reviews.get("summary", {}).get("findings", 0),
        },
        "qa": {
            "test_actions": tests.get("total", 0),
            "high_priority": tests.get("high_priority", 0),
            "mapped": tests.get("mapped", 0),
            "by_status": tests.get("by_status", {}),
        },
        "security": {
            "included": security is not None,
            "findings": (security or {}).get("summary", {}).get("findings", 0),
            "dangerous_rights": (security or {}).get("summary", {}).get("dangerous_rights", 0),
        },
        "manager": {
            "status": decision["status"],
            "score": decision["score"],
            "gate_status": gate.get("status"),
            "blockers": len(decision["blockers"]),
            "warnings": len(decision["warnings"]),
        },
    }


def render_release_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1cAI Release Readiness",
        "",
        f"Release: **{report['release_name']}**",
        f"Status: **{report['decision']['status'].upper()}**",
        f"Score: **{report['decision']['score']}**",
        "",
        "## Summary",
        "",
        f"- Changed modules: {report['summary']['changed_modules']}",
        f"- Impact edges: {report['summary']['total_impact_edges']}",
        f"- Impacted modules: {report['summary']['total_impacted_modules']}",
        f"- Gate violations: {report['summary']['gate_violations']}",
        f"- Standards findings: {report['summary']['standards_findings']}",
        f"- Form findings: {report['summary']['form_findings']}",
        f"- Security findings: {report['summary']['security_findings']}",
        f"- Test actions: {report['summary']['test_actions']}",
        "",
    ]

    if report["decision"]["blockers"]:
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {item}" for item in report["decision"]["blockers"])
        lines.append("")

    if report["decision"]["warnings"]:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {item}" for item in report["decision"]["warnings"])
        lines.append("")

    if report["recommended_actions"]:
        lines.extend(["## Recommended Actions", ""])
        for action in report["recommended_actions"][:20]:
            target = f" `{action['target']}`" if action.get("target") else ""
            lines.append(f"- **{action['owner']}** [{action['severity']}] {action['title']}{target}")
        lines.append("")

    lines.append(render_markdown_report(report["change_plan"], report["gate"]))
    return "\n".join(lines)


def build_release_readiness(
    store,
    *,
    changed_modules: list[str] | None = None,
    diff: str | None = None,
    release_name: str | None = None,
    snapshot_id: str | None = None,
    include_security: bool = False,
    include_forms: bool = True,
    form_object_limit: int = 4,
    security_limit: int = 100,
    max_depth: int = 5,
    max_edges: int = 600,
    hotspot_limit: int = 10,
    risk_threshold: int = 70,
    impact_threshold: int = 300,
    fail_on_high: bool = True,
) -> dict[str, Any]:
    modules = dedupe(list(changed_modules or []) + extract_diff_modules(diff))
    if not modules:
        raise ValueError("Provide changed_modules or unified diff with .bsl paths.")

    plan = build_change_plan(
        store,
        modules,
        max_depth=max_depth,
        max_edges=max_edges,
        hotspot_limit=hotspot_limit,
    )
    gate = assess_ci_gate(
        plan,
        risk_threshold=risk_threshold,
        impact_threshold=impact_threshold,
        fail_on_high=fail_on_high,
    )
    standards_findings = _standards_findings_from_diff(diff)
    standards_counts = _severity_counts(standards_findings)

    metadata = _metadata_surface(plan)
    metadata_diff = diff_metadata_snapshot(snapshot_id, limit=100) if snapshot_id else None
    form_reviews = _form_reviews_for_metadata(
        metadata,
        enabled=include_forms,
        object_limit=max(0, form_object_limit),
    )
    form_findings = _collect_form_findings(form_reviews)
    form_counts = _severity_counts(form_findings)

    security = security_review(limit=security_limit) if include_security else None
    security_counts = _severity_counts((security or {}).get("findings", []))

    tests = _test_summary(plan)
    decision = _decision(
        gate=gate,
        standards_counts=standards_counts,
        form_counts=form_counts,
        security_counts=security_counts,
        metadata_diff=metadata_diff,
    )
    actions = _recommended_actions(
        gate=gate,
        standards_findings=standards_findings,
        form_findings=form_findings,
        security=security,
        tests=tests,
    )

    report: dict[str, Any] = {
        "release_name": release_name or f"release-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at": _now(),
        "decision": decision,
        "summary": {
            "changed_modules": len(plan.get("changed_modules", [])),
            "total_impact_edges": plan.get("total_impact_edges", 0),
            "total_impacted_modules": plan.get("total_impacted_modules", 0),
            "gate_violations": int((gate.get("summary") or {}).get("violation_count") or 0),
            "standards_findings": len(standards_findings),
            "form_findings": len(form_findings),
            "security_findings": int((security or {}).get("summary", {}).get("findings") or 0),
            "test_actions": tests.get("total", 0),
            "metadata_objects": metadata.get("summary", {}).get("found", 0),
        },
        "gate": gate,
        "change_plan": plan,
        "standards": {
            "summary": standards_counts,
            "findings": standards_findings[:100],
        },
        "metadata": {
            "surface": metadata,
            "snapshot_diff": metadata_diff,
            "form_reviews": form_reviews,
            "security_review": security if include_security else {"included": False},
        },
        "tests": tests,
        "personas": _persona_summaries(
            decision=decision,
            plan=plan,
            gate=gate,
            standards_findings=standards_findings,
            metadata=metadata,
            tests=tests,
            security=security,
            form_reviews=form_reviews,
        ),
        "recommended_actions": actions,
        "caveats": [
            *plan.get("caveats", []),
            "Release readiness is deterministic static analysis; runtime user acceptance and data migration rehearsals remain separate gates.",
            "Security review is optional because full role/Rights.xml analysis can be expensive on large ERP/UH configurations.",
        ],
    }
    report["markdown"] = render_release_markdown(report)
    return report
