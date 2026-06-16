# Phase 2 Policy Engine Review

Date: 2026-06-15

## Findings

### Fixed before close

1. Policy engine initially existed as a standalone evaluator. That would not be enough for enterprise gates.
   - Fix: `transition_change_set` now evaluates policy before `approved`, `merged` and `released`.
   - Failed policy blocks transition unless `allow_policy_failure=true`.
   - Policy evaluation evidence is stored on the change set.

### Open risks

1. `allow_policy_failure=true` is an explicit override but is not yet tied to a formal approval record or review-pack approval.
   - Severity: high.
   - Next action: connect override to `approval_workflow` and/or approved review packs.

2. Policy rules are JSON and intentionally simple. They do not replace OPA/Rego for Kubernetes/Terraform policy.
   - Severity: medium.
   - Rationale: this engine is for product workflow gates; infra Rego policies remain under `policy/`.

3. Waiver matching is rule/scope based. It does not yet enforce owner group, SoD or quorum.
   - Severity: medium-high.
   - Next action: enterprise IAM/audit phase and approval integration.

## Scope Reviewed

- `policy/1cai-default-policy.json`
- `src/services/rentgen/policy_engine.py`
- `src/api/policies_api.py`
- `src/services/rentgen/change_sets.py`
- `src/api/change_sets_api.py`
- `src/app/routers.py`
- `src/ai/mcp/server.py`
- `tests/unit/test_policy_engine.py`
- `tests/unit/test_change_sets.py`

## Product Fit

This slice moves 1cAI from analysis reports into enforceable governance:

- JSON policy rules for impact, tests, release, security and standards;
- deterministic pass/warn/fail evaluation;
- persisted policy evaluation evidence;
- temporary waivers with owner, reason, expiration and approval decision;
- waiver projection into Artifact Graph;
- Change Set transition enforcement for high-risk statuses;
- API and MCP access.

The product now has a real gate layer: a risky change cannot silently become approved unless the caller explicitly records an override.

## Enterprise Readiness

- Offline: yes.
- Evidence: yes, evaluations are persisted.
- Waivers: yes, with expiration and decision status.
- Enforcement: yes for Change Set approval/merge/release transitions.
- Audit: partial; no append-only audit stream yet.
- IAM/SoD: not yet implemented.

## Test Evidence

Command:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_policy_engine.py tests\unit\test_baselines_review_packs.py tests\unit\test_change_sets.py tests\unit\test_requirements_traceability.py tests\unit\test_artifact_graph.py tests\unit\test_artifacts_api.py -q
```

Result:

- 20 passed.
- 1 existing pytest-asyncio deprecation warning from `tests/conftest.py` event loop fixture.

## Residual Risk

The engine is good enough to enforce internal gates, but regulated enterprise readiness still needs audit log, role-aware approvals, and waiver governance with SoD.

## Next Actions

1. Connect policy override to approval records.
2. Add CI report output with policy evaluation id.
3. Add test evidence store and runner import.
4. Add append-only audit log.
