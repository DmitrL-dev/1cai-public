"""Safe Autopilot plan for read-only 1C change assistance."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.services.rentgen.change_plan import (
    assess_ci_gate,
    build_change_plan,
    dedupe,
    extract_diff_modules,
)

ONEC_ISNULL = "\u0415\u0441\u0442\u044cNULL"
ONEC_ISNULL_UPPER = "\u0415\u0421\u0422\u042cNULL"
ONEC_IS_NULL = "\u0415\u0421\u0422\u042c NULL"
LEFT_JOIN_RU = "\u041b\u0415\u0412\u041e\u0415 \u0421\u041e\u0415\u0414\u0418\u041d\u0415\u041d\u0418\u0415"
JOIN_ALIAS_RE = re.compile(
    r"(?:LEFT\s+JOIN|\u041b\u0415\u0412\u041e\u0415\s+\u0421\u041e\u0415\u0414\u0418\u041d\u0415\u041d\u0418\u0415)"
    r"\s+.+?\s+(?:AS|\u041a\u0410\u041a)\s+([A-Za-z_\u0400-\u04ff][\w\u0400-\u04ff]*)",
    re.IGNORECASE,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scenario(goal: str) -> dict[str, str]:
    lowered = goal.casefold()
    if any(
        token in lowered
        for token in (
            "null",
            "left join",
            "join",
            "\u0441\u043e\u0435\u0434\u0438\u043d",
        )
    ):
        return {
            "id": "query-null-guard",
            "title": "Guard nullable join fields",
            "route": "/quality",
            "why": "Fields coming from joins can produce unsafe NULL semantics unless they are guarded or the join is made strict.",
        }
    if any(token in lowered for token in ("test", "yaxunit", "vanessa")):
        return {
            "id": "test-proof",
            "title": "Build focused test proof",
            "route": "/testing",
            "why": "The buyer/developer needs executable proof, not only an explanation.",
        }
    if any(token in lowered for token in ("release", "upgrade", "platform")):
        return {
            "id": "release-gate",
            "title": "Prepare release gate",
            "route": "/release-readiness",
            "why": "Release and platform actions need impact, tests, rollback and evidence before approval.",
        }
    return {
        "id": "safe-change",
        "title": "Plan safe change",
        "route": "/change",
        "why": "Unknown 1C changes should be narrowed to impact, tests, diff and evidence before write actions.",
    }


def _impact(
    store: Any, modules: list[str], risk_threshold: int, impact_threshold: int
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    caveats: list[str] = []
    if not modules:
        caveats.append(
            "No changed modules or diff were provided; impact is not measured."
        )
        plan = {
            "changed_modules": [],
            "modules": [],
            "total_impact_edges": 0,
            "total_impacted_modules": 0,
            "unmeasured_modules": [],
            "caveats": [],
        }
        gate = {
            "status": "warn",
            "violations": [],
            "summary": {
                "changed_modules": 0,
                "total_impact_edges": 0,
                "total_impacted_modules": 0,
                "violation_count": 0,
            },
        }
        return plan, gate, caveats
    if store is None:
        caveats.append(
            "Rentgen store is not built; Safe Autopilot cannot measure blast radius yet."
        )
        plan = {
            "changed_modules": modules,
            "modules": [
                {
                    "module_path": module,
                    "coverage": "no_store",
                    "impact_measured": False,
                    "impact_total": 0,
                    "covering_tests": [],
                }
                for module in modules
            ],
            "total_impact_edges": 0,
            "total_impacted_modules": 0,
            "unmeasured_modules": modules,
            "caveats": ["Build Rentgen graph before treating impact as known."],
        }
        gate = {
            "status": "warn",
            "violations": [
                {
                    "module_path": module,
                    "kind": "coverage",
                    "severity": "warning",
                    "value": "no_store",
                    "threshold": "built Rentgen graph",
                    "message": "Impact is not measured because the local graph is unavailable.",
                }
                for module in modules
            ],
            "summary": {
                "changed_modules": len(modules),
                "total_impact_edges": 0,
                "total_impacted_modules": 0,
                "violation_count": len(modules),
            },
        }
        return plan, gate, caveats

    plan = build_change_plan(
        store, modules, max_depth=5, max_edges=700, hotspot_limit=12
    )
    gate = assess_ci_gate(
        plan,
        risk_threshold=risk_threshold,
        impact_threshold=impact_threshold,
        fail_on_high=False,
    )
    return plan, gate, caveats


def _steps(
    scenario: dict[str, str],
    modules: list[str],
    gate: dict[str, Any],
    write_requested: bool,
) -> list[dict[str, Any]]:
    gate_status = gate.get("status", "warn")
    return [
        {
            "id": "ask",
            "title": "Ask",
            "status": "ready",
            "owner": "developer",
            "action": f"Freeze goal as '{scenario['title']}' and attach the exact module or diff.",
            "evidence": {"modules": modules, "scenario": scenario["id"]},
        },
        {
            "id": "plan",
            "title": "Plan",
            "status": "ready" if modules else "watch",
            "owner": "developer",
            "action": "Split the work into inspect, patch blueprint, tests, evidence and approval.",
            "evidence": {"changed_modules": len(modules)},
        },
        {
            "id": "impact",
            "title": "Impact",
            "status": "ready" if gate_status == "pass" else "watch",
            "owner": "architect",
            "action": "Review blast radius and coverage warnings before accepting the diff.",
            "evidence": gate.get("summary", {}),
        },
        {
            "id": "diff",
            "title": "Diff",
            "status": "approval_required" if write_requested else "planned",
            "owner": "developer",
            "action": "Generate or apply code only after explicit approval, local branch and rollback point.",
            "evidence": {"write_requested": write_requested, "direct_apply": False},
        },
        {
            "id": "tests",
            "title": "Tests",
            "status": "watch" if gate_status != "pass" else "ready",
            "owner": "QA",
            "action": "Run mapped tests, generated skeletons or manual checks for every changed module.",
            "evidence": {"gate_status": gate_status},
        },
        {
            "id": "evidence",
            "title": "Evidence",
            "status": "planned",
            "owner": "release lead",
            "action": "Attach change plan, tests, approval and proof packet to Evidence Bundle.",
            "evidence": {"route": "/evidence-bundle"},
        },
    ]


def _patch_blueprint(scenario: dict[str, str], modules: list[str]) -> dict[str, Any]:
    if scenario["id"] == "query-null-guard":
        return {
            "id": "join-field-null-guard",
            "title": "Guard fields coming from joins",
            "mode": "manual_review",
            "targets": modules,
            "changes": [
                f"Wrap selected fields from LEFT JOIN with {ONEC_ISNULL} when missing right-side rows are valid.",
                "Replace LEFT JOIN with INNER JOIN only when business rules require the right-side row to exist.",
                "Add explicit IS NULL / IS NOT NULL filters when the query must branch on absence.",
            ],
            "risk": "Query semantics can change row counts; compare before/after on cases where the joined row is missing.",
            "test": "Create a fixture with missing right-side rows and assert totals, grouping and presentation fields.",
        }
    if scenario["id"] == "test-proof":
        return {
            "id": "focused-test-proof",
            "title": "Create executable proof before code changes",
            "mode": "manual_review",
            "targets": modules,
            "changes": [
                "Map the changed object to existing YAxUnit/Vanessa selectors.",
                "Generate skeletons only for missing behavior, then mark owner and acceptance.",
                "Attach run command and expected result to the proof packet.",
            ],
            "risk": "Generated tests can encode the wrong behavior without owner review.",
            "test": "Run exact tests first, then impact regression and smoke checks.",
        }
    return {
        "id": "safe-change-blueprint",
        "title": "Prepare safe diff blueprint",
        "mode": "manual_review",
        "targets": modules,
        "changes": [
            "Inspect impact and standards findings.",
            "Prepare a small patch with rollback notes.",
            "Run focused tests before requesting approval.",
        ],
        "risk": "No automatic write is safe until local evidence and owner approval exist.",
        "test": "Use the generated impact/test plan as the minimum acceptance set.",
    }


def _diff_lines(diff: str | None) -> list[str]:
    if not diff:
        return []
    lines: list[str] = []
    for raw_line in diff.splitlines():
        if raw_line.startswith(("+++", "---", "@@", "diff --git", "index ")):
            continue
        if raw_line.startswith("+"):
            line = raw_line[1:].strip()
        elif raw_line.startswith("-"):
            continue
        else:
            line = raw_line.strip()
        if line:
            lines.append(line)
    return lines[:120]


def _has_left_join(line: str) -> bool:
    upper = line.upper()
    return "LEFT JOIN" in upper or LEFT_JOIN_RU in upper


def _has_null_guard(line: str) -> bool:
    upper = line.upper()
    return ONEC_ISNULL_UPPER in upper or ONEC_IS_NULL in upper or "IS NULL" in upper


def _field_has_null_guard(line: str, field_ref: str) -> bool:
    upper = line.upper()
    field = field_ref.upper()
    isnull_call = re.compile(
        rf"{re.escape(ONEC_ISNULL_UPPER)}\s*\([^)]*{re.escape(field)}", re.IGNORECASE
    )
    null_test = re.compile(
        rf"{re.escape(field)}\s+(?:\u0415\u0421\u0422\u042c\s+(?:\u041d\u0415\s+)?NULL|IS\s+(?:NOT\s+)?NULL)",
        re.IGNORECASE,
    )
    return bool(isnull_call.search(upper) or null_test.search(upper))


def _join_alias(line: str) -> str | None:
    match = JOIN_ALIAS_RE.search(line)
    return match.group(1) if match else None


def _line_context(line: str) -> str:
    normalized = line.lstrip("| \t").upper()
    if normalized.startswith(
        (
            "\u041f\u041e ",
            "ON ",
            "\u0418 ",
            "\u0418\u041b\u0418 ",
            "\u0413\u0414\u0415 ",
            "WHERE ",
        )
    ):
        return "condition"
    if normalized.startswith(("ПО ", "ON ", "И ", "ИЛИ ", "ГДЕ ", "WHERE ")):
        return "condition"
    if " КАК " in normalized or " AS " in normalized:
        return "projection"
    return "expression"


def _field_line_for_alias(lines: list[str], alias: str) -> tuple[str, str] | None:
    alias_ref = re.compile(
        rf"(?<![\w\u0400-\u04ff.]){re.escape(alias)}\.[A-Za-z_\u0400-\u04ff][\w\u0400-\u04ff]*",
        re.IGNORECASE,
    )
    for line in lines:
        if _has_left_join(line):
            continue
        if _line_context(line) == "condition":
            continue
        for match in alias_ref.finditer(line):
            field_ref = match.group(0)
            if not _field_has_null_guard(line, field_ref):
                return line, field_ref
    return None


def _guarded_line(before: str, field_ref: str) -> str:
    guarded = f"{ONEC_ISNULL}({field_ref}, <BusinessDefault>)"
    if field_ref in before and not _has_left_join(before):
        return before.replace(field_ref, guarded, 1)
    return f"{guarded} AS <Field>"


def _query_null_guard_candidates(
    modules: list[str], diff: str | None
) -> list[dict[str, Any]]:
    lines = _diff_lines(diff)
    aliases: list[tuple[str, str]] = []
    for line in lines:
        if not _has_left_join(line):
            continue
        alias = _join_alias(line) or "<JoinAlias>"
        aliases.append((alias, line))

    if not aliases:
        aliases.append(
            ("<JoinAlias>", "LEFT JOIN <RightTable> AS <JoinAlias> ON <condition>")
        )

    candidates: list[dict[str, Any]] = []
    seen_fields: set[tuple[str, str]] = set()
    for alias, join_line in aliases:
        field_line = (
            None if alias == "<JoinAlias>" else _field_line_for_alias(lines, alias)
        )
        if field_line:
            before, field_ref = field_line
        elif not diff or not lines:
            before = join_line
            field_ref = f"{alias}.<Field>"
        else:
            continue
        field_key = (before, field_ref)
        if field_key in seen_fields:
            continue
        seen_fields.add(field_key)
        index = len(candidates) + 1
        after = _guarded_line(before, field_ref)
        target = (
            modules[min(index - 1, len(modules) - 1)] if modules else "provided diff"
        )
        candidates.append(
            {
                "id": f"join-field-null-guard-{index}",
                "target": target,
                "finding": "A field from a nullable join can leak NULL into selection, grouping, filters or presentation.",
                "confidence": "medium" if diff and lines else "low",
                "before": before,
                "after": after,
                "unified_diff": "\n".join(
                    ["@@ query-null-guard", f"- {before}", f"+ {after}"]
                ),
                "approval_required": True,
                "review_notes": [
                    f"Use {ONEC_ISNULL} only when a missing right-side row is valid for the business case.",
                    "Use INNER JOIN only when the related row is mandatory and row loss is accepted.",
                    "Use an explicit IS NULL / IS NOT NULL branch when absence has separate behavior.",
                ],
                "tests": [
                    "Fixture with a missing right-side row returns the expected totals and presentation values.",
                    "Fixture with an existing right-side row keeps previous values unchanged.",
                    "Compare row count, grouping and filters before/after on the target report/query.",
                ],
            }
        )
        if len(candidates) >= 3:
            break
    return candidates


def _diff_proposal(
    scenario: dict[str, str], modules: list[str], diff: str | None
) -> dict[str, Any]:
    if scenario["id"] != "query-null-guard":
        return {
            "status": "blueprint_only",
            "title": "No deterministic diff proposal for this scenario yet",
            "route": scenario["route"],
            "direct_apply": False,
            "candidates": [],
            "acceptance": [
                "Review impact and tests before preparing a manual diff.",
                "Attach the final diff to Evidence Bundle before approval.",
            ],
            "caveat": "Safe Autopilot does not apply code automatically.",
        }

    candidates = _query_null_guard_candidates(modules, diff)
    return {
        "status": "manual_review",
        "title": "Diff proposal: guard nullable join fields",
        "route": "/quality",
        "direct_apply": False,
        "candidates": candidates,
        "acceptance": [
            f"Every selected field from LEFT JOIN is wrapped with {ONEC_ISNULL}, has an explicit IS NULL branch, or the join is changed to INNER JOIN.",
            "The business owner confirms default values and allowed row-count changes.",
            "Focused tests cover missing and existing right-side rows.",
            "The approved diff, tests and rollback note are attached to Evidence Bundle.",
        ],
        "caveat": "This is a deterministic proposal for manual review; it is never applied automatically.",
    }


def _tests(plan: dict[str, Any], scenario: dict[str, str]) -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []
    for module in plan.get("modules", []):
        for item in module.get("covering_tests", [])[:4]:
            tests.append(
                {
                    "module_path": module["module_path"],
                    "selector": item.get("selector", ""),
                    "framework": item.get("framework", ""),
                    "priority": item.get("priority", "medium"),
                    "status": item.get("status", "recommended"),
                    "command": item.get("command", ""),
                    "reason": item.get("reason", ""),
                }
            )
    if tests:
        return tests[:12]
    fallback_selector = scenario["id"].replace("-", ":")
    return [
        {
            "module_path": module,
            "selector": fallback_selector,
            "framework": "YAxUnit/Vanessa/manual",
            "priority": "high" if scenario["id"] == "query-null-guard" else "medium",
            "status": "recommended",
            "command": f"Run focused scenario '{fallback_selector}' for {module}",
            "reason": "Fallback test because exact local test mapping is not available.",
        }
        for module in plan.get("changed_modules", [])
    ]


def _tests_from_diff_proposal(
    diff_proposal: dict[str, Any], scenario: dict[str, str]
) -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []
    for candidate in (diff_proposal.get("candidates") or [])[:6]:
        candidate_tests = candidate.get("tests") or []
        tests.append(
            {
                "module_path": candidate.get("target") or "provided diff",
                "selector": scenario["id"].replace("-", ":"),
                "framework": "YAxUnit/Vanessa/manual",
                "priority": "high",
                "status": "recommended",
                "command": f"Run manual query regression for {candidate.get('id')}",
                "reason": candidate_tests[0]
                if candidate_tests
                else "Fallback test generated from diff proposal.",
            }
        )
    return tests


def _approvals(gate: dict[str, Any], write_requested: bool) -> list[dict[str, str]]:
    approvals = [
        {
            "role": "developer",
            "required": "yes",
            "reason": "Owns exact code diff and rollback note.",
        },
        {
            "role": "QA / release",
            "required": "yes",
            "reason": "Owns test evidence and acceptance result.",
        },
    ]
    if gate.get("status") != "pass":
        approvals.append(
            {
                "role": "architect",
                "required": "yes",
                "reason": "Gate has warnings or risk; impact must be accepted explicitly.",
            }
        )
    if write_requested:
        approvals.append(
            {
                "role": "change owner",
                "required": "yes",
                "reason": "Write/apply actions need explicit scope, actor and audit trail.",
            }
        )
    return approvals


def _approval_handoff(
    modules: list[str],
    gate: dict[str, Any],
    write_requested: bool,
    diff_proposal: dict[str, Any],
    tests: list[dict[str, Any]],
    approvals: list[dict[str, str]],
) -> dict[str, Any]:
    gate_status = gate.get("status", "warn")
    candidates = diff_proposal.get("candidates") or []
    has_scope = bool(modules or candidates)
    status = "ready_for_owner_review" if has_scope and tests else "needs_scope"
    if write_requested or gate_status != "pass" or candidates:
        status = "approval_required" if has_scope and tests else "needs_scope"

    role_actions = {
        "developer": "Confirm the generated diff is minimal, reversible and matches the target module.",
        "QA / release": "Attach focused run result or manual evidence for every changed module.",
        "architect": "Accept impact warnings, unmeasured modules and allowed row-count changes.",
        "change owner": "Name actor, scope, branch, rollback point and approval timestamp before any write action.",
    }
    roles = [
        {
            "role": item["role"],
            "required": item["required"],
            "decision": role_actions.get(item["role"], item["reason"]),
            "route": "/safe-autopilot"
            if item["role"] == "developer"
            else "/evidence-bundle",
        }
        for item in approvals
    ]

    return {
        "status": status,
        "can_request_approval": bool(has_scope and tests),
        "request_endpoint": "/api/v1/safe-autopilot/approval-request",
        "approval_record_kind": "edt_mcp_call",
        "handoff_line": (
            "The team can review the packet now; code remains read-only until the named owner approves scope and rollback."
            if has_scope and tests
            else "Add a changed module or diff before requesting approval."
        ),
        "blocked_actions": [
            "Apply generated diff directly from Safe Autopilot.",
            "Run EDT-MCP write or execute tools without actor, reason, scope and approval.",
            "Mark release green while impact is unmeasured or focused tests are missing.",
        ],
        "roles": roles,
        "evidence_packet": [
            {
                "title": "Safe plan and diff proposal",
                "route": "/safe-autopilot",
                "artifact": "rentgen-safe-autopilot.md",
                "why": "Shows goal, scenario, direct-apply block, diff candidate and tests.",
            },
            {
                "title": "Impact gate",
                "route": "/change",
                "artifact": "change-plan.md",
                "why": "Shows blast radius, warnings and unmeasured modules.",
            },
            {
                "title": "Test proof",
                "route": "/testing",
                "artifact": "test-factory.md",
                "why": "Shows focused checks before release or write approval.",
            },
            {
                "title": "Evidence manifest",
                "route": "/evidence-bundle",
                "artifact": "evidence-bundle-manifest.json",
                "why": "Creates buyer-safe and audit-safe proof packet.",
            },
        ],
        "audit_requirements": [
            "actor",
            "scope",
            "branch",
            "rollback",
            "approval_timestamp",
            "evidence_bundle_id",
        ],
        "local_asset_line": "Approval is based on local graph, deterministic rules and evidence; external AI remains optional.",
    }


def _ai_independence(
    plan: dict[str, Any],
    gate: dict[str, Any],
    modules: list[str],
    diff_proposal: dict[str, Any],
) -> dict[str, Any]:
    unmeasured = plan.get("unmeasured_modules") or []
    candidates = diff_proposal.get("candidates") or []
    graph_state = (
        "measured"
        if modules and not unmeasured and gate.get("status") == "pass"
        else "unmeasured"
    )
    return {
        "mode": "deterministic-local-first",
        "external_ai_required": False,
        "buyer_line": "Safe Autopilot produces plan, diff proposal, tests, approvals and evidence without sending code to external AI.",
        "license_line": "This is a local engineering asset with optional AI acceleration, not mandatory token rent.",
        "local_sources": [
            {
                "title": "Changed modules or diff",
                "available": bool(modules or candidates),
                "evidence": f"{len(modules)} modules, {len(candidates)} diff candidates",
            },
            {
                "title": "Rentgen graph impact",
                "available": graph_state == "measured",
                "evidence": graph_state,
            },
            {
                "title": "Deterministic 1C standards",
                "available": True,
                "evidence": "join-field-null-guard, CI gate, approval policy",
            },
            {
                "title": "Evidence Bundle",
                "available": True,
                "evidence": "hashed JSON/Markdown packet route is available",
            },
        ],
        "deterministic_rules": [
            "Scenario classification from goal keywords and 1C risk patterns.",
            "LEFT JOIN nullable-field guard proposals use deterministic parsing and templates.",
            "Impact gate uses local Rentgen graph thresholds when the store is available.",
            "Direct apply remains false regardless of AI availability.",
        ],
        "optional_ai_controls": [
            "AI may explain local findings, but every claim must cite local evidence.",
            "External AI proxy must use redaction, budget limits and audit logging.",
            "Write/execute tools require approval even when an AI model suggests the change.",
        ],
    }


def _decision(
    modules: list[str], gate: dict[str, Any], write_requested: bool
) -> dict[str, Any]:
    score = 82
    if not modules:
        score -= 18
    if gate.get("status") == "fail":
        score -= 24
    elif gate.get("status") == "warn":
        score -= 12
    if write_requested:
        score -= 8
    score = max(0, min(100, score))
    if gate.get("status") == "fail":
        status = "risk"
    elif score >= 82 and modules and not write_requested:
        status = "ready"
    else:
        status = "watch"
    headline = (
        "Safe Autopilot can guide the change in read-only mode with tests and evidence."
        if status == "ready"
        else "Safe Autopilot needs more evidence or approval before any write action."
    )
    return {"status": status, "score": score, "headline": headline}


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1C Rentgen Safe Autopilot",
        "",
        f"Goal: **{report['goal']}**",
        f"Status: **{report['decision']['status'].upper()}** / score **{report['decision']['score']}**",
        f"Scenario: **{report['scenario']['title']}**",
        "",
        "## Flow",
        "",
    ]
    for step in report["steps"]:
        lines.append(f"- **{step['title']}** ({step['status']}): {step['action']}")
    lines.extend(["", "## Patch Blueprint", ""])
    blueprint = report["patch_blueprint"]
    lines.append(f"- **{blueprint['title']}** ({blueprint['mode']})")
    for item in blueprint["changes"]:
        lines.append(f"- {item}")
    proposal = report["diff_proposal"]
    lines.extend(["", "## Diff Proposal", ""])
    lines.append(f"- **{proposal['title']}** ({proposal['status']})")
    for candidate in proposal["candidates"]:
        lines.append(
            f"- `{candidate['target']}` {candidate['id']}: {candidate['finding']}"
        )
        lines.append(f"  - before: `{candidate['before']}`")
        lines.append(f"  - after: `{candidate['after']}`")
    for item in proposal["acceptance"]:
        lines.append(f"- Acceptance: {item}")
    handoff = report["approval_handoff"]
    lines.extend(["", "## Approval Handoff", ""])
    lines.append(f"- Status: **{handoff['status']}**")
    lines.append(f"- Can request approval: **{handoff['can_request_approval']}**")
    lines.append(f"- {handoff['handoff_line']}")
    for item in handoff["roles"]:
        lines.append(
            f"- **{item['role']}** required={item['required']}: {item['decision']}"
        )
    for item in handoff["evidence_packet"]:
        lines.append(
            f"- Evidence `{item['artifact']}` via `{item['route']}`: {item['why']}"
        )
    ai = report["ai_independence"]
    lines.extend(["", "## AI Independence", ""])
    lines.append(f"- Mode: **{ai['mode']}**")
    lines.append(f"- External AI required: **{ai['external_ai_required']}**")
    lines.append(f"- {ai['buyer_line']}")
    lines.append(f"- {ai['license_line']}")
    for item in ai["local_sources"]:
        lines.append(
            f"- Local source `{item['title']}` available={item['available']}: {item['evidence']}"
        )
    for item in ai["optional_ai_controls"]:
        lines.append(f"- AI control: {item}")
    lines.extend(["", "## Tests", ""])
    for item in report["tests"]:
        lines.append(f"- **{item['priority']}** `{item['selector']}`: {item['reason']}")
    lines.extend(["", "## Approvals", ""])
    for item in report["approvals"]:
        lines.append(
            f"- **{item['role']}** required={item['required']}: {item['reason']}"
        )
    if report["caveats"]:
        lines.extend(["", "## Caveats", ""])
        lines.extend(f"- {item}" for item in report["caveats"])
    return "\n".join(lines)


def build_safe_autopilot(
    store: Any = None,
    *,
    goal: str = "Plan a safe 1C change",
    changed_modules: list[str] | None = None,
    diff: str | None = None,
    allow_write: bool = False,
    risk_threshold: int = 70,
    impact_threshold: int = 300,
) -> dict[str, Any]:
    """Build a read-only Ask/Plan/Impact/Diff/Test/Evidence route."""

    modules = dedupe(list(changed_modules or []) + extract_diff_modules(diff))
    scenario = _scenario(goal)
    plan, gate, caveats = _impact(store, modules, risk_threshold, impact_threshold)
    write_requested = bool(allow_write)
    patch_blueprint = _patch_blueprint(scenario, modules)
    diff_proposal = _diff_proposal(scenario, modules, diff)
    tests = _tests(plan, scenario)
    if not tests and diff_proposal.get("candidates"):
        tests = _tests_from_diff_proposal(diff_proposal, scenario)
    approvals = _approvals(gate, write_requested)
    approval_handoff = _approval_handoff(
        modules=modules,
        gate=gate,
        write_requested=write_requested,
        diff_proposal=diff_proposal,
        tests=tests,
        approvals=approvals,
    )
    ai_independence = _ai_independence(
        plan=plan,
        gate=gate,
        modules=modules,
        diff_proposal=diff_proposal,
    )
    approval_required = (
        write_requested
        or gate.get("status") != "pass"
        or bool(diff_proposal["candidates"])
    )
    report: dict[str, Any] = {
        "generated_at": _now(),
        "goal": goal,
        "scenario": scenario,
        "decision": _decision(modules, gate, write_requested),
        "summary": {
            "changed_modules": len(modules),
            "impact_edges": gate.get("summary", {}).get("total_impact_edges", 0),
            "impacted_modules": gate.get("summary", {}).get(
                "total_impacted_modules", 0
            ),
            "violations": gate.get("summary", {}).get("violation_count", 0),
            "tests": 0,
            "diff_candidates": 0,
            "approval_roles": len(approval_handoff["roles"]),
            "evidence_items": len(approval_handoff["evidence_packet"]),
            "blocked_actions": len(approval_handoff["blocked_actions"]),
            "external_ai_required": ai_independence["external_ai_required"],
            "local_sources": len(ai_independence["local_sources"]),
            "write_allowed": False,
            "approval_required": approval_required,
        },
        "safety_policy": {
            "mode": "read-only-plan",
            "direct_apply": False,
            "writes_allowed": False,
            "requested_write": write_requested,
            "approval_required": approval_required,
            "audit_line": "Any write/apply/execute action must name actor, scope, branch, rollback and evidence bundle.",
        },
        "steps": _steps(scenario, modules, gate, write_requested),
        "impact": {
            "gate": gate,
            "modules": plan.get("modules", []),
            "unmeasured_modules": plan.get("unmeasured_modules", []),
        },
        "patch_blueprint": patch_blueprint,
        "diff_proposal": diff_proposal,
        "tests": tests,
        "approvals": approvals,
        "approval_handoff": approval_handoff,
        "ai_independence": ai_independence,
        "evidence": [
            {
                "title": "Change impact",
                "route": "/change",
                "artifact": "change-plan.md",
            },
            {
                "title": "Test Factory",
                "route": "/testing",
                "artifact": "test-factory.md",
            },
            {
                "title": "Evidence Bundle",
                "route": "/evidence-bundle",
                "artifact": "evidence-bundle-manifest.json",
            },
        ],
        "caveats": [
            *caveats,
            *list(plan.get("caveats") or [])[:4],
            "Safe Autopilot v1 creates a plan and blueprint only; it never applies code or executes 1C actions.",
        ],
        "download_name": "rentgen-safe-autopilot.md",
    }
    report["summary"]["tests"] = len(report["tests"])
    report["summary"]["diff_candidates"] = len(report["diff_proposal"]["candidates"])
    report["markdown"] = _markdown(report)
    return report
