"""Risk-driven test coverage matrix for changed 1C modules."""

from __future__ import annotations

from typing import Any

from src.services.rentgen.change_plan import (
    build_change_plan,
    dedupe,
    extract_diff_modules,
)
from src.services.rentgen.test_inventory import (
    inventory_summary,
    match_tests_for_module,
)


def _priority(risk: int, impact: int, status: str, impact_measured: bool) -> str:
    if not impact_measured or status == "gap" or risk >= 70 or impact >= 300:
        return "high"
    if risk >= 40 or impact >= 100:
        return "medium"
    return "low"


def _status(exact: list[dict[str, Any]], planned: list[dict[str, Any]]) -> str:
    if exact or any(item.get("status") == "mapped" for item in planned):
        return "covered"
    if planned:
        return "planned"
    return "gap"


def _test_data_blueprint(
    module_path: str, canonical: dict[str, Any], status: str
) -> list[dict[str, Any]]:
    object_name = canonical.get("object_name") or module_path
    return [
        {
            "name": "main_object",
            "target": object_name,
            "purpose": "Create or select the changed business object with boundary values.",
            "required_when": status in {"planned", "gap", "covered"},
        },
        {
            "name": "negative_case",
            "target": object_name,
            "purpose": "Verify validation/error branch and observable failure message.",
            "required_when": status in {"planned", "gap"},
        },
    ]


def _commands(
    exact: list[dict[str, Any]], planned: list[dict[str, Any]], module_path: str
) -> list[str]:
    values = []
    for item in exact:
        selector = item.get("selector") or item.get("name")
        if selector:
            values.append(f"YAxUnit/Vanessa: run tests matching selector '{selector}'")
    for item in planned:
        command = item.get("command")
        if command:
            values.append(command)
    if not values:
        values.append(
            f"YAxUnit/Vanessa: create and run focused tests for '{module_path}'"
        )
    return list(dict.fromkeys(values))


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Risk-Driven Test Coverage Matrix",
        "",
        f"Changed modules: **{report['summary']['changed_modules']}**",
        f"Covered: **{report['summary']['covered']}**",
        f"Planned: **{report['summary']['planned']}**",
        f"Gaps: **{report['summary']['gaps']}**",
        f"Unmeasured impact: **{report['summary'].get('unmeasured_impact', 0)}**",
        "",
        "## Modules",
        "",
    ]
    for item in report["modules"]:
        if item.get("impact_measured") is False:
            impact_line = f"- Impact edges: NOT MEASURED - {item.get('coverage_caveat') or 'coverage is incomplete'}"
        else:
            impact_line = f"- Impact edges: {item['impact_total']}"
        lines.extend(
            [
                f"### `{item['module_path']}`",
                "",
                f"- Status: {item['coverage_status']}",
                f"- Priority: {item['priority']}",
                f"- Risk: {item['risk']}",
                impact_line,
                f"- Exact tests: {len(item['exact_tests'])}",
                f"- Planned tests: {len(item['planned_tests'])}",
                "",
            ]
        )
    return "\n".join(lines)


def build_test_coverage_matrix(
    store,
    *,
    changed_modules: list[str] | None = None,
    diff: str | None = None,
    max_depth: int = 5,
    max_edges: int = 600,
    hotspot_limit: int = 10,
    match_limit: int = 10,
) -> dict[str, Any]:
    """Build exact/planned/gap test coverage for changed modules."""

    modules = dedupe(list(changed_modules or []) + extract_diff_modules(diff))
    plan = (
        build_change_plan(
            store,
            modules,
            max_depth=max_depth,
            max_edges=max_edges,
            hotspot_limit=hotspot_limit,
        )
        if modules
        else {
            "changed_modules": [],
            "modules": [],
            "total_impact_edges": 0,
            "total_impacted_modules": 0,
            "caveats": [],
        }
    )

    rows = []
    for item in plan["modules"]:
        module_path = item["module_path"]
        canonical = item.get("canonical") or {}
        object_name = canonical.get("object_name") or ""
        exact = match_tests_for_module(
            module_path, object_name=object_name, limit=match_limit
        )
        planned = item.get("covering_tests", [])
        status = _status(exact, planned)
        risk = int((item.get("quality") or {}).get("risk") or 0)
        impact = int(item.get("impact_total") or 0)
        impact_measured = item.get("impact_measured") is not False
        gaps = (
            []
            if status == "covered"
            else [
                {
                    "kind": "missing_exact_mapping",
                    "severity": "high" if status == "gap" else "medium",
                    "message": "No exact local test mapping was found for the changed module/object.",
                }
            ]
        )
        if not impact_measured:
            gaps.append(
                {
                    "kind": "unmeasured_impact",
                    "severity": "high",
                    "message": item.get("coverage_caveat")
                    or "Blast radius is not measured; impact_total=0 must not be read as safe.",
                }
            )
        rows.append(
            {
                "module_path": module_path,
                "canonical": canonical,
                "risk": risk,
                "impact_total": impact,
                "impact_measured": impact_measured,
                "coverage": item.get("coverage") or "in_graph",
                "coverage_caveat": item.get("coverage_caveat"),
                "coverage_status": status,
                "priority": _priority(risk, impact, status, impact_measured),
                "exact_tests": exact,
                "planned_tests": planned,
                "commands": _commands(exact, planned, module_path),
                "test_data_blueprint": _test_data_blueprint(
                    module_path, canonical, status
                ),
                "gaps": gaps,
            }
        )

    summary = {
        "changed_modules": len(modules),
        "covered": sum(1 for row in rows if row["coverage_status"] == "covered"),
        "planned": sum(1 for row in rows if row["coverage_status"] == "planned"),
        "gaps": sum(1 for row in rows if row["coverage_status"] == "gap"),
        "high_priority": sum(1 for row in rows if row["priority"] == "high"),
        "exact_tests": sum(len(row["exact_tests"]) for row in rows),
        "planned_tests": sum(len(row["planned_tests"]) for row in rows),
        "total_impact_edges": plan.get("total_impact_edges", 0),
        "total_impacted_modules": plan.get("total_impacted_modules", 0),
        "unmeasured_impact": sum(1 for row in rows if row["impact_measured"] is False),
    }
    report = {
        "changed_modules": modules,
        "summary": summary,
        "inventory": inventory_summary(),
        "modules": rows,
        "change_plan": plan,
        "caveats": [
            *plan.get("caveats", []),
            "Exact mappings come from local tests/bsl inventory; planned mappings are deterministic risk-based selectors.",
        ],
    }
    report["markdown"] = _markdown(report)
    return report
