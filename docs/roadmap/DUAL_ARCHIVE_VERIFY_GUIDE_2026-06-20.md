# Dual Archive Verify Guide

Date: 2026-06-20.

## Why

Evidence Bundle and Killer Demo ZIP now expose hashes and manifests, but a buyer still needs a plain first-party checklist inside the archives. Procurement should not infer verification order from README prose or API headers.

## Added

- `VERIFY_ARCHIVE.md` inside Evidence Bundle ZIP.
- `VERIFY_ARCHIVE.md` inside Killer Demo ZIP, replacing the Evidence copy when the close-room archive is assembled.
- Evidence `archive-manifest.json` hashes the Evidence `VERIFY_ARCHIVE.md`.
- `killer-demo-manifest.json` hashes the Killer Demo `VERIFY_ARCHIVE.md`.
- `OPEN_FIRST.md`, `README.md`, `OPEN_FIRST_KILLER_DEMO.md` and `README-KILLER-DEMO.md` point to the verification guide.
- `POST /api/v1/evidence-bundle/archive/verify` verifies the generated Evidence ZIP server-side and returns pass/warn/fail findings.
- `POST /api/v1/killer-demo/archive/verify` verifies the generated Killer Demo ZIP server-side, including the embedded Evidence `archive-manifest.json` when present.
- Portal buttons `Verify Evidence ZIP` and `Verify Killer ZIP` show the archive SHA-256, checked files and findings next to the download controls.
- Verify responses include `verification_receipt` and `verification_receipt_markdown`; the portal exposes `Receipt JSON` and `Receipt MD` downloads for procurement tickets.
- `POST /api/v1/evidence-bundle/archive/verify-dual` and the portal `Verify Both ZIPs` button produce one combined packet for the Evidence ZIP + linked Killer Demo ZIP pair.
- `POST /api/v1/evidence-bundle/archive/verification-packet` and the portal `Verification Packet ZIP` button package the combined packet, both receipts and hash table into one small ticket attachment.
- Buyer Pulse, Buyer Brief, Launch Room and Killer Demo now surface `archive-verification-packet.zip` in purchase path, proof packet, meeting receipt and activation handoff contracts.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py src/api/killer_demo_api.py`
- `pytest tests/unit/test_evidence_bundle.py tests/unit/test_killer_demo_api.py -q`
- `npm run build` in `portal`

## Buyer Impact

The buyer receives two archives that each explain exactly which hash headers, manifest files and boundary files to record before forwarding role packets or accepting the close-room handoff.
