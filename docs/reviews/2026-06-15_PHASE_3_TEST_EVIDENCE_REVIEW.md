# Phase 3 Test Evidence Review

Date: 2026-06-15

## Scope Reviewed

- Service: `src/services/rentgen/test_evidence.py`
- API: `src/api/testing_api.py`
- Router mount: `src/app/routers.py`
- MCP: `src/ai/mcp/server.py`
- Tests: `tests/unit/test_test_evidence.py`

## Findings

1. Medium: runner adapters are not implemented yet. The layer can record/import evidence, but YAxUnit, Vanessa, 1C:Tester and Allure command adapters still need dedicated wrappers with dry-run defaults and external command policy gates.
2. Medium: evidence attachments are stored as metadata only. There is no artifact bundle copy, checksum verification or retention policy for attached logs/reports yet.
3. Low: duplicate test cases are intentionally stable by selector hash, but historical case renames still need a merge/alias model.
4. Low: API does not yet expose aggregate trend views by change set, framework, owner or flaky marker.

No blocking implementation bugs were found in the completed slice.

## Product Fit

The slice turns test execution from an advisory matrix into stored delivery evidence:

- QA can record manual, YAxUnit, Vanessa or imported JUnit results.
- CI can persist dry-run or real-run evidence without depending on external ALM tools.
- Change sets can be linked to test runs in the internal artifact graph.
- Agents can import/list evidence through MCP without direct file access.

This is valuable without an LLM: the product now has local, auditable test evidence as part of its system of record.

## Enterprise Readiness

- Offline/on-prem: JSON store under `data/test_runs.json`, no network dependency.
- Traceability: test runs and test cases are projected into `artifact_graph.json`.
- Governance: test runs can be connected to change sets and later policy gates.
- API/MCP: both human workflows and agent/IDE workflows are covered.
- Audit: not yet integrated with a central audit log; this belongs to Phase 5.

## Test Evidence

Commands executed:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_test_evidence.py tests\unit\test_policy_engine.py tests\unit\test_baselines_review_packs.py tests\unit\test_change_sets.py tests\unit\test_requirements_traceability.py tests\unit\test_artifact_graph.py tests\unit\test_artifacts_api.py -q
```

Result: 24 passed, 1 existing pytest-asyncio warning from `tests/conftest.py`.

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_test_evidence.py -q
```

Result: 4 passed, 1 existing pytest-asyncio warning from `tests/conftest.py`.

## Residual Risk

The layer is ready as an evidence store/import surface, but not yet as a complete test execution subsystem. Runner adapters and attachment checksums are the next work items before claiming full QA automation.

## Next Actions

1. Add runner adapter abstractions for YAxUnit, Vanessa, 1C:Tester, JUnit JSON/Allure import.
2. Add evidence attachment checksum and optional local copy into an evidence bundle directory.
3. Feed latest test-run status into change-set policy context before approval/release.
4. Add aggregate API for flaky tests, failed tests by module/change set and framework trends.
