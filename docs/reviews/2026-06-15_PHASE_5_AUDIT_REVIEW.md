# Phase 5 Audit Log Review

Date: 2026-06-15

## Scope Reviewed

- Service: `src/services/audit_log.py`
- API: `src/api/audit_api.py`
- Router mount: `src/app/routers.py`
- Integrations:
  - `src/services/rentgen/artifact_graph.py`
  - `src/services/rentgen/policy_engine.py`
  - `src/services/rentgen/test_evidence.py`
  - `src/services/rentgen/test_runners.py`
  - `src/services/rentgen/canonical_metadata.py`
- Tests: `tests/unit/test_product_audit_log.py`

## Findings

1. Medium: audit log is append-only NDJSON but not yet tamper-evident. Hash chaining/signatures are needed for stricter regulated environments.
2. Medium: API currently has an explicit `POST /api/v1/audit/events` integration endpoint without auth-bound actor enforcement in unit scope. Production auth/IAM must bind actor from token/session.
3. Medium: not every governance service is wired yet. Baselines, review packs, approvals, release readiness and EDT-MCP bridge should also emit product audit events.
4. Low: retention/export policy is not implemented yet.

No blocking defects were found in the completed audit slice.

## Product Fit

The slice adds a local product audit trail independent of the older DB-backed admin/security audit:

- Product events are stored in `data/audit_log.ndjson`.
- Events can be listed and exported through `/api/v1/audit/events` and `/api/v1/audit/export`.
- Artifact, policy, test evidence, runner and canonical metadata writes now emit audit records.
- Unit tests verify both direct audit service behavior and write-service integration.

This improves non-AI value immediately: teams can inspect what changed, which gate ran, which test evidence was stored and which metadata snapshot was imported.

## Enterprise Readiness

- Offline/on-prem: local NDJSON file, no DB/network dependency.
- API: list/export available for admins and integrations.
- Failure mode: audit calls are best-effort inside governance services so business flows are not broken by local log write failures.
- Gaps: auth-bound actors, tamper evidence and retention are still pending.

## Test Evidence

Command executed:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_product_audit_log.py tests\unit\test_artifact_graph.py tests\unit\test_policy_engine.py tests\unit\test_test_evidence.py tests\unit\test_canonical_metadata.py -q
```

Result: 19 passed, 1 existing pytest-asyncio warning from `tests/conftest.py`.

## Residual Risk

The audit layer is useful and wired into core governance flows, but it is not yet a full compliance-grade audit subsystem.

## Next Actions

1. Add hash-chain tamper evidence and export manifest hashes.
2. Bind API actor to authenticated user once Phase 5 IAM is complete.
3. Wire baselines, review packs, approvals, release readiness and EDT-MCP bridge.
4. Add retention/rotation policy and backup/restore documentation.
