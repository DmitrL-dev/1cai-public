# Phase 7 Agentic Workflow Review

Date: 2026-06-15

## Scope Reviewed

- Service: `src/services/rentgen/agentic_workflows.py`
- API: `src/api/agentic_api.py`
- Router mount: `src/app/routers.py`
- MCP: `src/ai/mcp/server.py`
- Tests: `tests/unit/test_agentic_workflows.py`

## Findings

1. Medium: the layer is deterministic guardrails and workflow state, not a full LLM planning/execution orchestrator yet.
2. Medium: approvals are represented as gate requirements but not yet integrated with the approval workflow service for automatic approval-id validation.
3. Medium: action gates are not yet enforced inside every risky endpoint; services can call them, but boundary enforcement still needs broad integration.
4. Low: no UI route exists for agentic plans yet.

No blocking defects were found in the completed agentic workflow slice.

## Product Fit

The slice makes AI acceleration safer by putting deterministic workflow rules underneath it:

- Agentic plans have modes: ask, plan, act, review.
- Act mode is rejected in review unless the plan is approved.
- Risky actions are blocked without confirmation and an approved/running plan.
- Reviews cite artifact trace summaries, policy evaluation and test evidence.
- API and MCP expose plan creation, review and action gate checks.

This preserves product value without an LLM: teams can use the same plan/review/gate mechanism manually or from CI/IDE integrations.

## Enterprise Readiness

- Offline/on-prem: local JSON store.
- Governance: risky action taxonomy is explicit.
- Traceability: plans sync into Artifact Graph as work items.
- Audit: plan create/review/action gate events are logged.
- Remaining: approval workflow integration and endpoint-wide enforcement.

## Test Evidence

Command executed:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_agentic_workflows.py tests\unit\test_policy_engine.py tests\unit\test_artifact_graph.py tests\unit\test_test_evidence.py -q
```

Result: 15 passed, 1 existing pytest-asyncio warning from `tests/conftest.py`.

## Residual Risk

The layer is ready as a deterministic safety and workflow substrate. It is not yet a full autonomous coding agent runtime.

## Next Actions

1. Validate approval ids through `approval_workflow`.
2. Call `action_gate` inside EDT-MCP write/run paths, metadata import, runner execution and release actions.
3. Add workbench/UI view for agentic plans and blocked actions.
4. Add LLM planner adapters that must emit this plan schema before Act mode.
