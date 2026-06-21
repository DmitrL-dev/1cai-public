# Safe Autopilot v1

Date: 2026-06-19.

Safe Autopilot is the read-only developer cockpit for 1C changes. It turns a goal, changed modules and optional diff into an Ask / Plan / Impact / Diff / Tests / Evidence route without applying code or executing 1C actions.

## Implemented

- Backend service: `src/services/rentgen/safe_autopilot.py`
- API: `POST /api/v1/safe-autopilot/plan`
- Approval API: `POST /api/v1/safe-autopilot/approval-request`
- UI: `/safe-autopilot`
- Navigation: Engineering sidebar and home fast entry
- Evidence Bundle artifact: `safe-autopilot.json` and `safe-autopilot.md`
- Tests: `tests/unit/test_safe_autopilot.py`

## Report Shape

- `scenario`: classified change route, including query NULL guard, test proof, release gate or generic safe change.
- `safety_policy`: read-only mode, no direct apply, write request flag, approval requirement and audit line.
- `steps`: Ask, Plan, Impact, Diff, Tests and Evidence owners/actions.
- `impact`: CI gate, measured modules and unmeasured modules when graph/store coverage is missing.
- `patch_blueprint`: manual-review change plan, including 1C join-field NULL guard options.
- `diff_proposal`: deterministic manual-review candidates with before/after, unified diff, approval flag, review notes, tests and acceptance criteria. v1 generates concrete proposals for LEFT JOIN nullable-field guards with `ЕстьNULL`, explicit NULL branches or approved INNER JOIN semantics.
- `approval_handoff`: approval status, blocked dangerous actions, role decisions, evidence packet, audit requirements and local-asset line.
- `query_null_guard_refinement`: duplicate join aliases are deduplicated, join condition lines are not blindly wrapped, and `Справочник.<Имя>.ПустаяСсылка` is not treated as a joined-table alias.
- Query Surgeon NULL refinement now keeps mixed SELECT lines honest: a guarded field on the same line no longer hides another unguarded joined field, while `ON/ПО ... AND/И ...` join-condition continuations are not reported as business field usage.
- Query Surgeon field-specific NULL refinement checks `ЕстьNULL` / `ЕСТЬ NULL` against the concrete joined `Alias.Field`, so one guarded field no longer suppresses another unguarded field on the same projection line; real Unicode `ПО/И/ИЛИ/ГДЕ` condition prefixes are skipped.
- `approval-request`: authenticated handoff that creates a `write_module_source` approval record linked to the Safe Autopilot plan, with module constraints and audit event.
- `ai_independence`: deterministic-local-first mode, external-AI-required flag, local sources, deterministic rules and optional AI controls.
- `tests`: mapped or fallback YAxUnit/Vanessa/manual checks.
- `approvals`: role-specific acceptance before write/apply/execute actions.
- `evidence`: routes and artifacts to attach to the proof packet.

## Buyer Value

1. Developers get a concrete path from request to safe diff without trusting a generic chat answer.
2. Architects see impact and coverage caveats before approving the change.
3. QA sees the minimum test proof that must exist before release.
4. Security and directors can see that write actions are blocked by default and require actor, scope, rollback and evidence.
5. The LEFT JOIN / NULL pain is now a visible product moment: the tool proposes an exact reviewable diff while still blocking automatic application.
6. Real 1C query text now produces a cleaner candidate list: selected nullable fields become reviewable `ЕстьNULL` proposals, while join semantics stay an approval decision.
7. Mixed 1C projection lines from customer snippets are handled at field level, reducing both false safety and noisy join-condition findings.
7. Approval handoff turns the plan into a team decision: developer, QA/release, architect and change owner each get a named decision and evidence route.
8. AI Independence makes the commercial argument explicit: the value comes from local graph, rules and evidence; external AI is optional acceleration, not a required rent meter.
9. The product remains useful when AI is disabled because the plan is deterministic and evidence-first.
10. The handoff panel can create a real approval request instead of leaving a manual process gap after the demo.

## Caveats

- v1 creates a plan, blueprint and manual-review diff proposals; it never applies code.
- Exact patch application is blocked unless a future approved write tool is connected.
- If Rentgen store is not built, impact is explicitly unmeasured instead of reported as safe zero.

## Verification

- `python -m py_compile src/services/rentgen/safe_autopilot.py src/api/safe_autopilot_api.py src/app/routers.py`
- `python -m pytest tests/unit/test_safe_autopilot.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
