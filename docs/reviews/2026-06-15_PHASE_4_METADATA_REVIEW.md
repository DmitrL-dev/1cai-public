# Phase 4 Canonical Metadata Review

Date: 2026-06-15

## Scope Reviewed

- Service: `src/services/rentgen/canonical_metadata.py`
- Existing metadata graph compatibility: `src/services/rentgen/metadata_graph.py`
- API: `src/api/metadata_api.py`
- MCP: `src/ai/mcp/server.py`
- Tests: `tests/unit/test_canonical_metadata.py`, `tests/unit/test_metadata_graph.py`

## Findings

1. Medium: canonical import currently targets EDT/unpacked metadata. Live DB metadata export, `.cf/.dt` extraction and extension `.cfe` ingestion still need adapters.
2. Medium: query extraction is not yet canonicalized. Query artifacts are planned but not parsed from BSL/form XML in this slice.
3. Medium: snapshot objects are stored inline in JSON. This is fine for on-prem MVP and tests, but large enterprise configs will eventually need chunking or SQLite/Postgres storage.
4. Low: artifact sync uses `relates_to` for metadata->module/form links. A richer ownership/link taxonomy can improve trace semantics later.

No blocking bugs were found in the completed canonical metadata slice.

## Product Fit

The slice moves metadata analysis from read-only scanning to a canonical product model:

- EDT metadata can be imported into `data/canonical_metadata.json`.
- Objects get stable ids, fingerprints, groups and snapshot membership.
- Drift compares added/removed/changed objects between snapshots.
- Rights diff focuses on role-right changes and dangerous rights totals.
- Metadata objects, forms and BSL modules synchronize into Artifact Graph.
- API and MCP expose import, object list/detail, drift and rights diff.

This directly helps architects, developers, BAs and release managers without an LLM: they can inspect what changed in the 1C configuration and attach those changes to governance evidence.

## Enterprise Readiness

- Offline/on-prem: local JSON store, no network dependency.
- Traceability: canonical metadata links to Artifact Graph artifacts.
- Governance: rights diff can feed release/security review.
- Scalability risk: JSON is acceptable for current product hardening but must be revisited for very large configs.
- Audit: central audit trail is pending Phase 5.

## Test Evidence

Command executed:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_canonical_metadata.py tests\unit\test_metadata_graph.py -q
```

Result: 5 passed, 1 existing pytest-asyncio warning from `tests/conftest.py`.

## Residual Risk

The canonical model is usable for EDT snapshot/drift/rights workflows now. It is not yet a universal importer for every 1C metadata source format.

## Next Actions

1. Add adapters for v8unpack JSON/XML, live DB export and extensions.
2. Parse query text into `query` artifacts and link it to metadata/module owners.
3. Feed metadata drift and rights diff into release-readiness and policy context.
4. Add storage compaction/chunking for large enterprise configurations.
