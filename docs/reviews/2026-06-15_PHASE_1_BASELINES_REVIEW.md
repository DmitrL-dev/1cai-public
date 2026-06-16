# Phase 1 Baselines And Review Packs Review

Date: 2026-06-15

## Findings

### Fixed before close

1. Baselines were described as immutable but could be recreated with the same explicit id, replacing the stored snapshot.
   - Fix: `create_baseline` now rejects an existing baseline id.
   - Regression test: `test_baseline_id_is_immutable`.

2. Initial trace assertion assumed only direct baseline links. Artifact Graph traversal correctly returned neighboring requirement/change/review-pack links as well.
   - Fix: test now asserts minimum direct coverage and required node types instead of exact link count.

### Open risks

1. Baseline snapshots embed full artifact copies. This is useful now, but large baselines may need chunked artifact evidence later.
   - Severity: medium.
   - Next action: evidence artifact store in Phase 3/5.

2. Review pack approvals are local decisions and are not yet connected to enterprise policy, quorum, role or segregation-of-duty rules.
   - Severity: high for regulated rollout.
   - Next action: Phase 2 Policy & Gates Engine.

3. No UI route yet for baselines/review packs.
   - Severity: medium for adoption.
   - Next action: Phase 6 UX consolidation.

## Scope Reviewed

- `src/services/rentgen/baselines.py`
- `src/api/baselines_api.py`
- `src/app/routers.py`
- `src/ai/mcp/server.py`
- `src/services/rentgen/artifact_graph.py`
- `tests/unit/test_baselines_review_packs.py`

## Product Fit

This slice closes the final P0 system-of-record piece:

- immutable baseline snapshots with SHA-256 evidence hash;
- baseline projection into Artifact Graph;
- review packs with fixed artifact snapshots;
- comments, approve/reject decisions and decision evidence;
- API and MCP access.

Together with Artifact Graph, Requirements integration and Change Sets, 1cAI now has an internal ALM/governance backbone rather than isolated analysis reports.

## Enterprise Readiness

- Offline: yes, local JSON stores.
- Evidence: yes, baseline/review-pack evidence hash and snapshots.
- Audit: partial, decisions/comments include actor/timestamps.
- Access control: not enforced at object level yet.
- Immutability: baseline id cannot be overwritten.
- Policy: not yet connected.

## Test Evidence

Command:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_baselines_review_packs.py tests\unit\test_change_sets.py tests\unit\test_requirements_traceability.py tests\unit\test_artifact_graph.py tests\unit\test_artifacts_api.py -q
```

Result:

- 17 passed.
- 1 existing pytest-asyncio deprecation warning from `tests/conftest.py` event loop fixture.

## Residual Risk

The core ALM/governance backbone exists, but it still permits transitions/approvals without a centralized policy engine. That is the next blocker for enterprise-grade readiness.

## Next Actions

1. Implement Policy & Gates Engine.
2. Connect policy evaluations to Change Set transitions and review-pack approvals.
3. Add waivers with owner approval and expiration.
4. Add CI evidence outputs using policy evaluation ids.
