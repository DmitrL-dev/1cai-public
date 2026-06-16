# Phase 1 Change Sets Review

Date: 2026-06-15

## Findings

### Fixed before close

1. Initial Change Set artifact sync only linked requirements and modules. That would have left tests and release decisions outside the internal graph.
   - Fix: sync now also projects selected test cases and attached release-readiness reports into Artifact Graph.
   - Regression assertion: requirement trace reaches `change_set`, `bsl_module`, `test_case` and `release` nodes.

### Open risks

1. Change Set transitions do not yet enforce policy validators or approval requirements.
   - Severity: high for regulated enterprise usage.
   - Next action: Phase 2 Policy & Gates Engine must own transition guards.

2. Release readiness attachment stores a full report inside the change-set JSON. This is useful for evidence, but can make the JSON heavy on very large diffs.
   - Severity: medium.
   - Next action: introduce evidence artifact references or chunked storage when test/release evidence grows.

3. Change Set UI route is not implemented yet.
   - Severity: medium for workflow adoption.
   - Next action: Phase 6 UX consolidation should add `/change-sets` and connect it to existing `/change`, `/requirements`, `/testing`, `/release-readiness`.

4. External PR/MR provider integration is not included.
   - Severity: low for core, medium for CI adoption.
   - Next action: Phase 2 CI pack.

## Scope Reviewed

- `src/services/rentgen/change_sets.py`
- `src/api/change_sets_api.py`
- `src/app/routers.py`
- `src/ai/mcp/server.py`
- `tests/unit/test_change_sets.py`
- Regression path with:
  - `src/services/rentgen/artifact_graph.py`
  - `src/services/rentgen/requirements_traceability.py`
  - `src/services/rentgen/test_coverage_matrix.py`
  - `src/services/rentgen/release_readiness.py`

## Product Fit

The slice introduces the core object needed for enterprise delivery governance:

- change set as a first-class record;
- links to source requirements;
- changed module extraction from explicit modules or diff;
- impact analysis attachment;
- risk-driven test matrix attachment;
- release-readiness decision attachment;
- lifecycle transitions and decision log;
- Artifact Graph projection for requirements, modules, tests and releases;
- API and MCP access.

This is the central workflow bridge from BA/architecture into developer/QA/release execution.

## Enterprise Readiness

- Offline: yes, local JSON store.
- Audit: partial; decision log records actor/status/reason.
- Evidence: impact/test/release reports stored inside the change set.
- Policy: not yet enforced; explicit Phase 2 dependency.
- Approvals: not yet connected to `approval_workflow`; explicit Phase 2 dependency.
- Scalability: JSON bootstrap is acceptable now; heavy evidence should later move to referenced artifacts.

## Test Evidence

Command:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_change_sets.py tests\unit\test_requirements_traceability.py tests\unit\test_artifact_graph.py tests\unit\test_artifacts_api.py -q
```

Result:

- 13 passed.
- 1 existing pytest-asyncio deprecation warning from `tests/conftest.py` event loop fixture.

## Residual Risk

Change Sets are now usable as an internal system-of-record object, but they are not yet a safe enterprise gate by themselves. The next blocking layer is policy-as-code plus baselines/review packs.

## Next Actions

1. Implement baselines and review packs.
2. Connect approvals/policy gates to Change Set transitions.
3. Add CI report artifact references.
4. Add UI consolidation for the full change workflow.
