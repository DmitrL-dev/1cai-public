# Phase 11 SBOM Inventory Review

Date: 2026-06-16

## Scope Reviewed

- Service: `src/services/sbom_inventory.py`.
- API endpoints in `src/api/productization_api.py`:
  - `POST /api/v1/productization/sbom`
  - `GET /api/v1/productization/sbom/report`
- MCP tool: `sbom_generate`.
- Documentation: `docs/productization/SBOM_INVENTORY.md`.
- Readiness map: `src/services/productization_readiness.py`.
- Tests: `tests/unit/test_sbom_inventory.py`.

## Findings

### Medium

- Built-in SBOM generation is an offline inventory, not a vulnerability scanner. It does not query CVE databases or license registries.
- Parsing is intentionally conservative and covers common local manifests: Python requirements, npm package manifests/locks and Dockerfile base images.

### Low

- Package URL, license and supplier fields are not fully normalized yet.
- The generated SBOM is not automatically embedded into the ZIP bundle as a first-class artifact yet.

## Product Fit

This adds a security/compliance foundation for offline product delivery. Enterprise customers can see the dependency surface without sending manifests to external tools. It also gives a future installer/bundle flow a local SBOM artifact to attach to release records.

## Enterprise Readiness

- Works without network access.
- Rejects paths outside the repository root.
- API can generate JSON or Markdown summaries without writing.
- MCP exposes SBOM generation for release-agent workflows.

## Test Evidence

Command:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_sbom_inventory.py -q
```

Result:

- 5 passed.
- 1 existing pytest-asyncio fixture deprecation warning.
- Existing RequestsDependencyWarning about urllib3/chardet mismatch.

## Residual Risk

For production certification, this SBOM should be enriched by customer-approved SCA tooling where available and attached to signed release bundles. The current layer is the offline baseline inventory.

## Next Actions

1. Attach generated SBOM to offline ZIP bundles.
2. Add license normalization and package URL fields.
3. Add vulnerability-enrichment adapter interface for customer-approved scanners.
4. Link SBOM hash to baselines/change sets/release records.
