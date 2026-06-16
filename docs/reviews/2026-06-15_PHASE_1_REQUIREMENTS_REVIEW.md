# Phase 1 Requirements Integration Review

Date: 2026-06-15

## Findings

### Fixed before close

1. `artifact_sync` was returned by `save_trace`, but was not persisted into the stored trace record.
   - Fix: sync metadata is now written into `requirements_traces.json` together with the trace.
   - Regression assertion: loaded trace contains `artifact_sync.artifact_id`.

### Open risks

1. Requirement transitions are intentionally simple and do not yet enforce role-based validators or quorum approvals.
   - Severity: medium.
   - Next action: Phase 2 Policy & Gates Engine should own transition validators.

2. Artifact projection creates BSL/module/metadata/test artifacts from trace candidates, but does not yet mark links suspect after upstream module or requirement changes.
   - Severity: medium.
   - Next action: add suspect-link invalidation when Change Sets and Baselines exist.

3. API exposes artifact trace for a requirement, but portal UI is not yet wired to show the graph inline.
   - Severity: low for backend readiness, medium for user workflow.
   - Next action: Phase 6 UX consolidation.

## Scope Reviewed

- `src/services/rentgen/requirements_traceability.py`
- `src/api/requirements_api.py`
- `tests/unit/test_requirements_traceability.py`
- Indirect integration with:
  - `src/services/rentgen/artifact_graph.py`
  - `src/api/artifacts_api.py`
  - `src/ai/mcp/server.py`

## Product Fit

The requirement workflow now produces controlled internal ALM artifacts:

- requirement trace records remain compatible with existing API/MCP callers;
- saved traces create/update a `requirement` artifact;
- candidate modules become `bsl_module` artifacts;
- candidate metadata objects become `metadata_object` artifacts;
- candidate tests become `test_case` artifacts;
- trace links are available through Artifact Graph;
- trace status can move through an internal lifecycle endpoint.

This moves BA from "external documents plus analysis result" toward an internal 1cAI system of record.

## Enterprise Readiness

- Offline: yes, local JSON stores.
- Audit: partial; `decision_log` records status transitions with actor/reason.
- Access control: not yet object-level; to be enforced by policy/IAM phases.
- Evidence: artifact sync data is persisted in trace records.
- Traceability: direct links are available immediately; transitive matrix is planned after Change Sets.

## Test Evidence

Command:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_requirements_traceability.py tests\unit\test_artifact_graph.py tests\unit\test_artifacts_api.py -q
```

Result:

- 10 passed.
- 1 existing pytest-asyncio deprecation warning from `tests/conftest.py` event loop fixture.

## Residual Risk

This is a backend/system-of-record slice. It does not yet solve release approvals, baselines or policy validation. Those are explicitly next in the P0 path.

## Next Actions

1. Implement Change Set core.
2. Link change sets to requirement artifacts and release readiness reports.
3. Add test-selection and release-readiness actions to change set lifecycle.
4. Extend Artifact Graph coverage matrix to include transitive change-set/test/release coverage.
