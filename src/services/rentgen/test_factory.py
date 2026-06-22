"""Test Factory turns changed 1C modules into an executable test package."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.change_plan import dedupe, extract_diff_modules
from src.services.rentgen.test_coverage_matrix import build_test_coverage_matrix
from src.services.rentgen.test_inventory import inventory_summary


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return text[:80] or "ChangedModule"


def _object_name(row: dict[str, Any]) -> str:
    canonical = row.get("canonical") or {}
    return str(
        canonical.get("object_name") or row.get("module_path") or "changed module"
    )


def _impact_measured(row: dict[str, Any]) -> bool:
    return row.get("impact_measured") is not False


def _impact_reason(row: dict[str, Any]) -> str:
    if not _impact_measured(row):
        return "impact not measured"
    return f"impact {row.get('impact_total', 0)}"


def _status(summary: dict[str, int]) -> str:
    if summary.get("gaps", 0) > 0 or summary.get("unmeasured_impact", 0) > 0:
        return "risk"
    if summary.get("planned", 0) > 0 or summary.get("high_priority", 0) > 0:
        return "watch"
    return "ready"


def _score(summary: dict[str, int]) -> int:
    score = (
        100
        - summary.get("gaps", 0) * 18
        - summary.get("unmeasured_impact", 0) * 12
        - summary.get("planned", 0) * 7
        - summary.get("high_priority", 0) * 3
    )
    return max(0, min(100, score))


def _run_now(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in matrix.get("modules", []):
        priority = row.get("priority")
        if priority != "high" and row.get("coverage_status") == "covered":
            continue
        rows.append(
            {
                "module_path": row["module_path"],
                "object_name": _object_name(row),
                "priority": priority,
                "coverage_status": row.get("coverage_status"),
                "command": (
                    row.get("commands") or ["Create focused YAxUnit/Vanessa test"]
                )[0],
                "reason": f"risk {row.get('risk', 0)}, {_impact_reason(row)}",
                "route": "/testing",
            }
        )
    return rows


def _regression_pack(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in matrix.get("modules", []):
        exact = row.get("exact_tests") or []
        planned = row.get("planned_tests") or []
        if not exact and not planned:
            continue
        rows.append(
            {
                "module_path": row["module_path"],
                "object_name": _object_name(row),
                "exact_tests": len(exact),
                "planned_tests": len(planned),
                "commands": row.get("commands") or [],
                "acceptance": "Exact mapped tests run cleanly or planned selectors become explicit test cases.",
                "route": "/testing",
            }
        )
    return rows


def _manual_checks(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for row in matrix.get("modules", []):
        object_name = _object_name(row)
        if not _impact_measured(row):
            checks.append(
                {
                    "module_path": row["module_path"],
                    "title": f"Impact coverage proof for {object_name}",
                    "owner": "architect",
                    "reason": row.get("coverage_caveat")
                    or "Blast radius was not measured; this cannot be accepted as a zero-impact change.",
                    "steps": [
                        "Resolve the module into the Rentgen call graph or attach an explicit manual impact review.",
                        "Confirm the nearest metadata object, form/event entry points and affected critical paths.",
                        "Record the caveat and owner decision in the Evidence Bundle.",
                    ],
                    "route": "/change",
                }
            )
        if row.get("coverage_status") != "covered":
            checks.append(
                {
                    "module_path": row["module_path"],
                    "title": f"Manual acceptance for {object_name}",
                    "owner": "QA / analyst",
                    "reason": "No exact executable local test fully covers the changed module.",
                    "steps": [
                        "Open the changed business object or form.",
                        "Run the primary create/update/posting scenario.",
                        "Check negative validation and visible user message.",
                        "Attach screenshot or protocol to Evidence Bundle.",
                    ],
                    "route": "/testing",
                }
            )
        if (
            row.get("risk", 0) >= 70
            or row.get("impact_total", 0) >= 300
            or not _impact_measured(row)
        ):
            checks.append(
                {
                    "module_path": row["module_path"],
                    "title": f"Critical-path smoke for {object_name}",
                    "owner": "release owner",
                    "reason": "High risk, wide blast radius or unmeasured impact needs a visible release smoke.",
                    "steps": [
                        "Run the shortest happy path around the changed object.",
                        "Verify permissions for the primary role.",
                        "Record runtime errors, lock symptoms and failed validations.",
                    ],
                    "route": "/release-readiness",
                }
            )
    return checks


def _yaxunit_skeleton(row: dict[str, Any]) -> str:
    name = _safe_id(_object_name(row))
    return "\n".join(
        [
            f"Procedure Test_{name}_ChangedBehavior() Export",
            "    // Arrange: create or load the changed business object.",
            "    // Act: execute the changed command/procedure.",
            "    // Assert: verify the observable result and negative branch.",
            "EndProcedure",
        ]
    )


def _vanessa_skeleton(row: dict[str, Any]) -> str:
    object_name = _object_name(row)
    return "\n".join(
        [
            f"Feature: {object_name} changed behavior",
            "  Scenario: primary path remains stable after change",
            f"    Given a prepared {object_name} test object",
            "    When the changed business action is executed",
            "    Then the expected result is visible",
            "    And the negative branch is checked",
        ]
    )


def _generation_tasks(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for row in matrix.get("modules", []):
        if row.get("coverage_status") == "covered":
            continue
        tasks.append(
            {
                "module_path": row["module_path"],
                "object_name": _object_name(row),
                "priority": row.get("priority"),
                "frameworks": ["YAxUnit", "Vanessa"],
                "reason": (
                    "Coverage is planned/missing or impact is unmeasured; generate an executable local test before release."
                ),
                "yaxunit_skeleton": _yaxunit_skeleton(row),
                "vanessa_scenario": _vanessa_skeleton(row),
                "route": "/testing",
            }
        )
    return tasks


def _test_data_plan(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in matrix.get("modules", []):
        for blueprint in row.get("test_data_blueprint", []):
            items.append(
                {
                    "module_path": row["module_path"],
                    "object_name": _object_name(row),
                    **blueprint,
                }
            )
    return items


def _evidence_packet() -> list[dict[str, str]]:
    return [
        {
            "title": "Test Factory markdown",
            "filename": "rentgen-test-factory.md",
            "route": "/testing",
        },
        {
            "title": "Coverage matrix JSON",
            "filename": "test-coverage-matrix.json",
            "route": "/testing",
        },
        {
            "title": "YAxUnit skeletons",
            "filename": "generated-yaxunit-tests.bsl",
            "route": "/testing",
        },
        {
            "title": "Vanessa scenarios",
            "filename": "generated-vanessa.feature",
            "route": "/testing",
        },
        {
            "title": "Release evidence",
            "filename": "release-readiness.md",
            "route": "/release-readiness",
        },
        {
            "title": "Evidence Bundle",
            "filename": "evidence-bundle-manifest.json",
            "route": "/evidence-bundle",
        },
    ]


def _commands(matrix: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for row in matrix.get("modules", []):
        values.extend(row.get("commands") or [])
    values.append("python scripts/tests/run_bsl_tests.py")
    return list(dict.fromkeys(values))


def _fallback_matrix(modules: list[str]) -> dict[str, Any]:
    rows = [
        {
            "module_path": module_path,
            "canonical": {},
            "risk": 0,
            "impact_total": 0,
            "impact_measured": False,
            "coverage": "no_store",
            "coverage_caveat": "Rentgen graph store is unavailable; impact and exact mapping were not measured.",
            "coverage_status": "gap",
            "priority": "high",
            "exact_tests": [],
            "planned_tests": [],
            "commands": [
                f"YAxUnit/Vanessa: create and run focused tests for '{module_path}'"
            ],
            "test_data_blueprint": [
                {
                    "name": "main_object",
                    "target": module_path,
                    "purpose": "Create or select the changed business object with boundary values.",
                    "required_when": True,
                },
                {
                    "name": "negative_case",
                    "target": module_path,
                    "purpose": "Verify validation/error branch and observable failure message.",
                    "required_when": True,
                },
            ],
            "gaps": [
                {
                    "kind": "rentgen_store_missing",
                    "severity": "high",
                    "message": "Rentgen graph store is unavailable; impact and exact mapping were not measured.",
                }
            ],
        }
        for module_path in modules
    ]
    summary = {
        "changed_modules": len(modules),
        "covered": 0,
        "planned": 0,
        "gaps": len(modules),
        "high_priority": len(modules),
        "exact_tests": 0,
        "planned_tests": 0,
        "total_impact_edges": 0,
        "total_impacted_modules": 0,
        "unmeasured_impact": len(modules),
    }
    report = {
        "changed_modules": modules,
        "summary": summary,
        "inventory": inventory_summary(),
        "modules": rows,
        "change_plan": {
            "changed_modules": modules,
            "modules": [],
            "total_impact_edges": 0,
            "total_impacted_modules": 0,
            "unmeasured_modules": modules,
            "caveats": [
                "Rentgen graph store is unavailable; all changed modules are treated as test gaps."
            ],
        },
        "caveats": [
            "Rentgen graph store is unavailable; all changed modules are treated as test gaps."
        ],
    }
    report[
        "markdown"
    ] = "Risk-Driven Test Coverage Matrix\n\nStore is unavailable; all modules are gaps."
    return report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Test Factory",
        "",
        f"Client: **{report['client']['name']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Changed modules: **{report['summary']['changed_modules']}**",
        f"Run now: **{report['summary']['run_now']}**",
        f"Generation tasks: **{report['summary']['generation_tasks']}**",
        "",
        "## Run Now",
        "",
    ]
    for item in report["run_now"]:
        lines.append(f"- `{item['module_path']}`: {item['command']} ({item['reason']})")
    lines.extend(["", "## Generation Tasks", ""])
    for item in report["generation_tasks"]:
        lines.append(
            f"- `{item['module_path']}`: {', '.join(item['frameworks'])} / {item['priority']}"
        )
    lines.extend(["", "## Manual Checks", ""])
    for item in report["manual_checks"]:
        lines.append(f"- **{item['title']}**: {item['reason']}")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_test_factory(
    store,
    *,
    changed_modules: list[str] | None = None,
    diff: str | None = None,
    client_name: str = "Demo client",
    release_name: str | None = None,
    max_depth: int = 5,
    max_edges: int = 600,
    hotspot_limit: int = 10,
    match_limit: int = 10,
) -> dict[str, Any]:
    """Build a release-ready YAxUnit/Vanessa plan from changed modules or diff."""

    modules = dedupe(list(changed_modules or []) + extract_diff_modules(diff))
    matrix = (
        _fallback_matrix(modules)
        if store is None and modules
        else build_test_coverage_matrix(
            store,
            changed_modules=modules,
            max_depth=max_depth,
            max_edges=max_edges,
            hotspot_limit=hotspot_limit,
            match_limit=match_limit,
        )
    )
    run_now = _run_now(matrix)
    regression_pack = _regression_pack(matrix)
    manual_checks = _manual_checks(matrix)
    generation_tasks = _generation_tasks(matrix)
    test_data_plan = _test_data_plan(matrix)
    commands = _commands(matrix)
    summary = {
        "changed_modules": matrix["summary"]["changed_modules"],
        "run_now": len(run_now),
        "regression_tests": len(regression_pack),
        "manual_checks": len(manual_checks),
        "generation_tasks": len(generation_tasks),
        "test_data_items": len(test_data_plan),
        "gaps": matrix["summary"]["gaps"],
        "unmeasured_impact": matrix["summary"].get("unmeasured_impact", 0),
        "exact_tests": matrix["summary"]["exact_tests"],
        "planned_tests": matrix["summary"]["planned_tests"],
        "commands": len(commands),
    }
    decision_status = "watch" if not modules else _status(matrix["summary"])
    exact_tests = summary["exact_tests"]
    scaffolds = summary["generation_tasks"]
    if not modules:
        headline = "Test Factory is waiting for changed modules or a diff."
    elif exact_tests > 0:
        headline = (
            f"Test Factory mapped {exact_tests} executable YAxUnit/Vanessa "
            f"test(s) and generated {scaffolds} scaffold(s) to complete."
        )
    else:
        headline = (
            f"Test Factory generated {scaffolds} test scaffold(s) — "
            "comment-only skeletons to complete; not yet executable."
        )
    report: dict[str, Any] = {
        "generated_at": _now(),
        "client": {"name": client_name},
        "release": {"name": release_name or ""},
        "decision": {
            "status": decision_status,
            "score": 60 if not modules else _score(matrix["summary"]),
            "headline": headline,
        },
        "summary": summary,
        "run_now": run_now,
        "regression_pack": regression_pack,
        "manual_checks": manual_checks,
        "generation_tasks": generation_tasks,
        "test_data_plan": test_data_plan,
        "commands": commands,
        "evidence_packet": _evidence_packet(),
        "matrix": matrix,
        "proof_routes": ["/testing", "/release-readiness", "/evidence-bundle"],
        "caveats": [
            *matrix.get("caveats", []),
            "Generated skeletons are deterministic starting points; they require customer fixtures and acceptance data before live release gates.",
        ],
        "download_name": "rentgen-test-factory.md",
    }
    report["markdown"] = _markdown(report)
    return report
