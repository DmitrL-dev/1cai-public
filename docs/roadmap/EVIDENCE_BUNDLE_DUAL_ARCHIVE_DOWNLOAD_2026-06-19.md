# Evidence Bundle Dual Archive Download - 2026-06-19

## Why

The Evidence Bundle screen now explains the linked Killer Demo ZIP, but explanation alone is not enough.
Procurement should be able to download both archives from the same buying/proof surface:

- Evidence Bundle ZIP for source evidence and required files;
- linked Killer Demo ZIP for close-room overlays, meeting receipt, activation handoff and role packets.

## Implemented

1. Added `X-Killer-Demo-Archive-Sha256` response header to `POST /api/v1/killer-demo/archive`.
   - It mirrors the actual Killer Demo archive SHA-256.
   - Existing `X-Archive-Sha256` remains for compatibility.
   - `X-Evidence-Archive-Sha256` still carries the nested Evidence Archive hash.

2. Added a `Linked Killer Demo ZIP` button to `/evidence-bundle`.
   - It reuses the current buyer inputs.
   - It sends a clean Killer Demo archive request.
   - It downloads the ZIP and shows filename, Killer Demo archive hash, nested Evidence Archive hash and file count.
   - It is disabled when Killer Demo is turned off in bundle inputs.

3. Added test coverage for the specialized Killer Demo archive hash header.

## Buyer Impact

The procurement operator no longer needs to leave Evidence Bundle to collect the close-room archive.
The screen now supports the full receipt flow:

1. download Evidence Bundle ZIP;
2. download linked Killer Demo ZIP;
3. copy both hashes into the same ticket;
4. forward the right files from the right archive boundary.

## Verification

- `tests/unit/test_killer_demo_api.py` checks `X-Killer-Demo-Archive-Sha256`.
- `npm run build` validates the Evidence Bundle dual-download UI.
