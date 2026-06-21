# Buyer Room Packet Verify - 2026-06-20

## What Changed

- Added `GET /api/v1/management/buyer-room-packet/verify`.
- The verifier rebuilds the Buyer Room Packet ZIP and checks required files, `OPEN_FIRST_BUYER_ROOM.md`, `hash-table.json` coverage and SHA-256 consistency.
- The verify result returns expected packet headers: `X-Buyer-Room-Packet-Sha256`, `X-Buyer-Room-Packet-Files` and `X-Buyer-Room-Packet-Open-First`.
- Home now has `Verify Buyer Room Packet` next to the ZIP download.
- CORS exposes Buyer Room Packet, Verification Packet, Killer Demo archive and manifest headers so browser UI can read the same hashes that curl/tests see.

## Buyer Impact

The first packet is now a verifiable procurement control, not just a downloadable convenience. A buyer can open the room packet, record the SHA-256 and verify the packet structure before forwarding it to director, architect, developer and procurement roles.

## Verification

- `python -m py_compile src/api/management_api.py src/app/middleware.py`
- `pytest tests/unit/test_executive_dashboard.py -q`
- `npm run build` in `portal`
