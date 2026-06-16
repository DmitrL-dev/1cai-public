# Phase 3 Runner Adapters Review

Date: 2026-06-15

## Scope Reviewed

- Service: `src/services/rentgen/test_runners.py`
- Evidence summary: `src/services/rentgen/test_evidence.py`
- Change-set policy context: `src/services/rentgen/change_sets.py`
- Policy rules: `policy/1cai-default-policy.json`
- API: `src/api/testing_api.py`
- MCP: `src/ai/mcp/server.py`
- Tests: `tests/unit/test_test_runners.py`, `tests/unit/test_test_evidence.py`

## Findings

1. Medium: actual Vanessa and 1C:Tester command lines are generic placeholders. Customer/project-specific runner profiles are still needed before real execution in paid deployments.
2. Medium: real external execution is implemented but not exercised in tests. This is intentional because it requires local 1C/Vanessa/YAxUnit installations; add Windows runner integration tests later.
3. Low: evidence bundle manifests store checksums and optional copies, but there is no retention/cleanup policy yet.
4. Low: API exposes file-path import for local on-prem use. Tenant/project path boundaries must be enforced in Phase 5 IAM/audit.

No blocking defects were found in the completed runner-adapter slice.

## Product Fit

The slice closes the QA execution loop without requiring an LLM:

- Teams can list supported runner adapters.
- CI/UI/agents can build deterministic dry-run plans.
- External commands are blocked unless `execute=true` and `allow_external=true`.
- JUnit XML, generic JSON and Allure-style files can be imported into the evidence store.
- Evidence bundles record sha256/size/presence for logs and reports.
- Change-set approval policy now sees failed stored test evidence.

## Enterprise Readiness

- Offline/on-prem: all runner planning, imports and bundle manifests are local.
- Safety: execution defaults to dry-run and requires an explicit external-execution flag.
- Governance: failed test evidence blocks change-set approval via `tests.evidence.failed_run`.
- Traceability: imported/recorded runs still project into Artifact Graph.
- Audit: central audit events are pending Phase 5.

## Test Evidence

Command executed:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_test_runners.py tests\unit\test_test_evidence.py tests\unit\test_change_sets.py tests\unit\test_policy_engine.py -q
```

Result: 15 passed, 1 existing pytest-asyncio warning from `tests/conftest.py`.

## Residual Risk

The runner layer is product-usable for dry-run planning and evidence import now. Full live execution readiness depends on environment-specific runner profiles, installer checks and path/tenant restrictions.

## Next Actions

1. Add named runner profiles stored under local config for YAxUnit, Vanessa and 1C:Tester.
2. Add Windows self-hosted CI examples that call `/api/v1/testing/runners/run`.
3. Add audit events for runner plan/run/import/bundle actions.
4. Add retention and cleanup rules for evidence bundles.
