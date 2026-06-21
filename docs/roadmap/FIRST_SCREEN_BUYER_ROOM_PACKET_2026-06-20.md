# First Screen Buyer Room Packet - 2026-06-20

## What Changed

- Added `GET /api/v1/management/buyer-room-packet`.
- The endpoint builds from the fast Buyer Brief path and does not run deep deal/evidence generation.
- The ZIP includes `OPEN_FIRST_BUYER_ROOM.md`, Buyer Brief, Buyer Pulse, Buyer Room Plan, Purchase Path, Procurement Handoff and `hash-table.json`.
- Response headers expose `X-Buyer-Room-Packet-Sha256`, `X-Buyer-Room-Packet-Files` and `X-Buyer-Room-Packet-Open-First`.
- Home now uses the shared `BuyerRoomPacketControls` block with ZIP download, local SHA-256 comparison and endpoint verification status.
- Buyer Pulse/Brief purchase path now names `rentgen-buyer-room-packet.zip`, and Procurement Handoff starts with its `X-Buyer-Room-Packet-Sha256` control.
- `GET /api/v1/management/buyer-room-packet/verify` verifies required files, open-first guidance and `hash-table.json` SHA-256 coverage.

## Buyer Impact

The first screen can hand a compact, ordered packet to a director, architect, developer or procurement owner before anyone opens the full workbench. It gives the room a single starting file, a role route, the close question, purchase path and exact procurement handoff.

## Verification

- `python -m py_compile src/api/management_api.py`
- `pytest tests/unit/test_executive_dashboard.py -q`
- `npm run build` in `portal`
