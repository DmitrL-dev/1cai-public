# Evidence Bundle Archive Manifest

Date: 2026-06-20.

## Why

`manifest.json` verifies source evidence artifacts, but the downloaded ZIP also contains generated files: `OPEN_FIRST.md`, procurement handoff, archive receipt, role packets and forwarding notes. Security and procurement need a manifest for those generated ZIP entries too.

## Added

- `archive-manifest.json` inside the Evidence Bundle ZIP.
- `VERIFY_ARCHIVE.md` inside the Evidence Bundle ZIP, covered by `archive-manifest.json`.
- SHA-256, byte size and media type for every ZIP entry except `archive-manifest.json` itself.
- `archive_manifest_file` in the Evidence Archive acceptance receipt.
- `archive-manifest.json` in `OPEN_FIRST.md`, `procurement-handoff.md`, `README.md`, `archive_contents` and archive receipt boundaries.
- Evidence Bundle UI shows `archive-manifest.json` in the procurement handoff header and archive acceptance receipt cards.
- `/api/v1/evidence-bundle/archive` exposes `X-Archive-Manifest`, `X-Archive-Manifest-Sha256` and `X-Archive-Manifest-Files` headers, and the UI shows those values after ZIP download.
- Verification step updated to check both `manifest.json` and `archive-manifest.json`.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py`
- `pytest tests/unit/test_evidence_bundle.py -q`
- `npm run build` in `portal`

## Buyer Impact

The archive is now auditable as a delivery packet, not only as a set of source artifacts. A security owner can prove that the exact role packet and forwarding note they received match the generated ZIP.
