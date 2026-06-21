# Buyer Room Packet Purchase Path Sync - 2026-06-20

## What Changed

- Buyer Pulse and Buyer Brief now expose `purchase_path.buyer_room_packet_artifact`.
- `rentgen-buyer-room-packet.zip` is included in `purchase_path.send_files`.
- Procurement Handoff now starts with Buyer Room Packet ZIP and its `X-Buyer-Room-Packet-Sha256` hash header before Evidence, Killer Demo and Verification Packet ZIPs.
- Home shows the Buyer Room Packet as a purchase artifact and renders all 6 procurement handoff steps.
- Evidence Bundle downstream tests lock the new file through Buyer Pulse/Brief materialization.

## Buyer Impact

The first-screen packet is no longer just a portal convenience. It is part of the product's sale contract: the room opens one compact ZIP first, then proceeds to the deeper archives and post-demo activation evidence.

## Verification

- `python -m py_compile src/services/rentgen/buyer_pulse.py src/services/rentgen/buyer_brief.py src/api/management_api.py`
- `pytest tests/unit/test_executive_dashboard.py tests/unit/test_evidence_bundle.py -q`
- `npm run build` in `portal`
