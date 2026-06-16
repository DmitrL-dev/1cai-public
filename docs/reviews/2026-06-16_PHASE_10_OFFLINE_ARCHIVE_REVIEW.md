# Phase 10 Offline Archive Bundle Review

Date: 2026-06-16

## Scope Reviewed

- Archive writer/verifier in `src/services/offline_bundle.py`.
- API endpoints in `src/api/productization_api.py`:
  - `POST /api/v1/productization/offline-bundle/archive`
  - `POST /api/v1/productization/offline-bundle/archive/verify`
- MCP tools:
  - `offline_bundle_archive`
  - `offline_bundle_archive_verify`
- Documentation: `docs/productization/OFFLINE_BUNDLE_MANIFEST.md`.
- Tests: `tests/unit/test_offline_bundle.py`.

## Findings

### Medium

- ZIP archive is now implemented, but it is not yet a full Windows installer. It is a portable delivery artifact with manifest and payload.
- Production signing still uses HMAC over a local secret. Customer KMS/certificate signing remains a later enterprise hardening item.

### Low

- Archive verification is local-only and does not pull from an artifact registry.
- SBOM and dependency inventory are not first-class archive members yet.

## Product Fit

This step moves packaging from "manifest only" to an actual transferable artifact. The bundle contains `manifest.json`, `VERIFY.txt` and `payload/...` files, so it can be copied into an offline contour and verified before installation.

## Enterprise Readiness

- Archive output paths are constrained to the repository root.
- Verification checks archive payload hashes without extracting files.
- Verification detects missing payload, payload tampering, manifest digest mismatch and signature mismatch.
- Signed production/airgap manifests can be verified with `ONECAI_BUNDLE_SIGNING_KEY`.

## Test Evidence

Command:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_offline_bundle.py -q
```

Result:

- 6 passed.
- 1 existing pytest-asyncio fixture deprecation warning.
- Existing RequestsDependencyWarning about urllib3/chardet mismatch.

## Residual Risk

The bundle is ready as an offline transfer artifact for pilots and controlled demos. It still needs installer orchestration, SBOM, dependency inventory, restore/install smoke checks and customer-grade signing for production certification.

## Next Actions

1. Add SBOM/dependency manifest generation.
2. Add install/upgrade smoke command profile.
3. Add signed release record linking bundle sha256 to baseline/change set.
4. Add customer KMS/certificate signing provider abstraction.
