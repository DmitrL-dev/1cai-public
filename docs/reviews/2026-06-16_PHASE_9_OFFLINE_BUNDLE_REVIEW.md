# Phase 9 Offline Bundle Manifest Review

Date: 2026-06-16

## Scope Reviewed

- Service: `src/services/offline_bundle.py`.
- API additions: `src/api/productization_api.py`.
- MCP additions: `offline_bundle_manifest`, `offline_bundle_verify` in `src/ai/mcp/server.py`.
- Productization docs: `docs/productization/OFFLINE_BUNDLE_MANIFEST.md`.
- Readiness map: `src/services/productization_readiness.py`.
- Tests: `tests/unit/test_offline_bundle.py`, `tests/unit/test_productization_readiness.py`.

## Findings

### Medium

- The layer creates and verifies an integrity manifest, but it does not yet build a binary installer or archive payload. The next packaging step is a real offline artifact bundle/installer that consumes this manifest.
- HMAC signing is suitable for closed-contour pilot delivery, but production should support customer KMS or certificate-backed signing.

### Low

- Verification checks the current filesystem against manifest paths. Remote artifact registry verification is not implemented yet.
- The manifest includes a product readiness snapshot but does not yet attach test run bundles or SBOM files as first-class artifact categories.

## Product Fit

This step closes the first concrete packaging gap from the mega review. It gives release managers and implementation teams a reproducible list of product files, hashes, manifest digest and optional signature. It works without AI and can be used by CI, a future installer, customer release boards and air-gapped deployment procedures.

## Enterprise Readiness

- Paths are constrained to the repository root to avoid arbitrary file inclusion or writes.
- API signing does not accept secrets in request bodies; it uses local environment variables.
- Production and airgap profiles explicitly require signed manifests in the installer profile.
- Verification detects missing files, hash mismatch, manifest digest mismatch and signature mismatch.

## Test Evidence

Command:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_offline_bundle.py tests\unit\test_productization_readiness.py -q
```

Result:

- 9 passed.
- 1 existing pytest-asyncio fixture deprecation warning.
- Existing RequestsDependencyWarning about urllib3/chardet mismatch.

## Residual Risk

This is not the final installer. It is the integrity substrate for that installer. The next step must create an actual bundle/installer artifact, attach SBOM/dependency metadata and run install/verify smoke tests.

## Next Actions

1. Add archive/bundle writer that consumes this manifest.
2. Add SBOM/dependency manifest as a first-class bundle artifact.
3. Add install/upgrade smoke test command for Windows/offline pilot.
4. Add customer KMS/certificate signing profile.
