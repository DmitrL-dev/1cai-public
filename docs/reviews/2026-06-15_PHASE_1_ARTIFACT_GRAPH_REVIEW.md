# Phase 1 Artifact Graph Review

Date: 2026-06-15

## Findings

### Fixed before close

1. `create_artifact` initially behaved like create-only for explicit ids while claiming upsert semantics. That could have reset `created_at` and `version` for stable ids such as `REQ-1`.
   - Fix: explicit-id upsert now loads the existing artifact and preserves history while incrementing version.
   - Regression test: `test_artifact_create_upserts_explicit_id_without_losing_history`.

### Open risks

1. Coverage matrix currently uses direct outgoing links from `need` / `requirement` / `capability`. It does not yet compute transitive coverage such as `requirement -> change_set -> test_run`.
   - Severity: medium.
   - Next action: extend matrix after Change Set core lands.

2. No dedicated portal page for `/artifacts` yet.
   - Severity: medium.
   - Rationale: API and MCP are enough for the first system-of-record slice; UI consolidation is planned in Phase 6.

3. Artifact store is JSON-backed and suitable for local/on-prem bootstrap, but it is not a concurrent multi-user database.
   - Severity: medium for enterprise scale.
   - Next action: keep atomic writes now; later add repository abstraction for SQLite/Postgres.

## Scope Reviewed

- `docs/status/dora_history.md`
- `docs/IMPLEMENTATION_MEGA_PLAN_2026-06-15.md`
- `src/services/rentgen/artifact_graph.py`
- `src/api/artifacts_api.py`
- `src/app/routers.py`
- `src/ai/mcp/server.py`
- `tests/unit/test_artifact_graph.py`
- `tests/unit/test_artifacts_api.py`

## Product Fit

The slice establishes the internal ALM system-of-record skeleton:

- artifacts for requirements, capabilities, change sets, metadata, BSL modules, tests, releases, incidents, approvals and waivers;
- directed links for traceability;
- trace traversal around one artifact;
- requirements-oriented coverage matrix;
- API and MCP access for portal/IDE/agents.

This directly supports the product thesis: 1cAI must be useful without AI by storing controlled engineering facts, not only generating text.

## Enterprise Readiness

- Offline: yes, local JSON store.
- Audit: partial; artifact version and timestamps exist, append-only audit log is Phase 5.
- Access control: inherited from surrounding API deployment; object-level RBAC not implemented yet.
- Evidence: matrix and trace output are deterministic and serializable.
- Policy: not connected yet; Phase 2 will attach policy evaluations and waivers.

## Test Evidence

Command:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_artifact_graph.py tests\unit\test_artifacts_api.py -q
```

Result:

- 7 passed.
- 1 existing pytest-asyncio deprecation warning from `tests/conftest.py` event loop fixture.

Conflict-marker hygiene:

```powershell
rg -n "^(<<<<<<< .+|=======$|>>>>>>> .+)" docs src tests
```

Result:

- No matches.

## Residual Risk

The graph is intentionally minimal and should not be presented as complete ALM yet. It is the foundation for the next slices: Requirements upgrade, Change Sets, Baselines/Review Packs, Policy Gates, Test Evidence.

## Next Actions

1. Connect requirement trace creation to artifact graph.
2. Add requirement transition/baseline API.
3. Implement Change Set core and link it to release readiness/test matrix.
4. Extend coverage matrix to transitive coverage after Change Sets exist.
