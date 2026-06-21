# Offline Bundle Manifest

1cAI offline bundle manifests make product delivery reproducible inside closed enterprise contours.

## Purpose

The manifest records:

- product profile: `pilot`, `production` or `airgap`;
- every packaged file path;
- file size;
- file `sha256`;
- manifest digest;
- optional HMAC-SHA256 signature;
- product readiness snapshot at build time;
- verification command.

This is not a binary installer by itself. It is the integrity contract that an installer, CI job or customer release process can use before deploying 1cAI into an offline environment.

## Build

Unsigned pilot manifest:

```powershell
C:\Python311\python.exe -m src.services.offline_bundle --profile pilot --output data/offline_bundles/latest_manifest.json
```

Signed production manifest:

```powershell
$env:ONECAI_BUNDLE_SIGNING_KEY="replace-with-customer-secret"
C:\Python311\python.exe -m src.services.offline_bundle --profile production --sign --output data/offline_bundles/latest_manifest.json
```

## Verify

```powershell
C:\Python311\python.exe -m src.services.offline_bundle --verify data/offline_bundles/latest_manifest.json
```

For signed manifests, the verifier requires the same `ONECAI_BUNDLE_SIGNING_KEY` value.

## Build ZIP Bundle

```powershell
C:\Python311\python.exe -m src.services.offline_bundle --archive --profile pilot --output data/offline_bundles/1cai-pilot.zip
```

Signed production ZIP:

```powershell
$env:ONECAI_BUNDLE_SIGNING_KEY="replace-with-customer-secret"
C:\Python311\python.exe -m src.services.offline_bundle --archive --profile production --sign --output data/offline_bundles/1cai-production.zip
```

The archive contains:

- `manifest.json`;
- `DELIVERY_PASSPORT.json`;
- `DELIVERY_PASSPORT.md`;
- `VERIFY.txt`;
- `payload/<repo-relative-path>` files.

The delivery passport is the buyer handoff layer. It summarizes the profile,
signature policy, manifest SHA-256, verification commands, acceptance gates and
role-specific instructions for developer/QA, architect/security and director.

## Verify ZIP Bundle

```powershell
C:\Python311\python.exe -m src.services.offline_bundle --verify-archive data/offline_bundles/1cai-production.zip
```

## API

- `POST /api/v1/productization/offline-bundle/manifest`
- `GET /api/v1/productization/offline-bundle/manifest`
- `POST /api/v1/productization/offline-bundle/verify`
- `POST /api/v1/productization/offline-bundle/archive`
- `POST /api/v1/productization/offline-bundle/archive/verify`

The API never accepts signing secrets in request bodies. Signing uses the local environment variable.

## MCP

- `offline_bundle_manifest`
- `offline_bundle_verify`
- `offline_bundle_archive`
- `offline_bundle_archive_verify`

## Release Rule

For pilots, an unsigned manifest is acceptable as engineering evidence.

For production and air-gapped delivery, the manifest must be signed, stored with the release artifacts, and verified before installation.

For buyer handoff, attach `DELIVERY_PASSPORT.md` together with the Evidence
Bundle ZIP so security and the sponsor can verify what is being installed and
which gates remain open.
