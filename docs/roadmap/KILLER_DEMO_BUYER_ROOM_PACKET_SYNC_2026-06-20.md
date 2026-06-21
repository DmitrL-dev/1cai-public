# Killer Demo Buyer Room Packet Sync - 2026-06-20

## What Changed

- Killer Demo `proof_packet.procurement_handoff.open_order` now starts with Buyer Room Packet ZIP and `X-Buyer-Room-Packet-Sha256`.
- `room_map` exposes the packet filename, endpoint and hash header.
- Meeting Close Receipt and Post-Demo Activation Handoff include `rentgen-buyer-room-packet.zip` in their send/proof files.
- Commercial Close Packet evidence requirements now start with Buyer Room Packet ZIP before Killer Demo ZIP, receipt, activation and Verification Packet ZIP.
- Portal `/killer-demo` renders the packet filename/hash in Buyer room map, shows all 6 procurement handoff steps and exposes direct download/verify actions for the packet.

## Buyer Impact

The close-room presenter now ends the live demo with the same open-first packet used by Home and Launch Room. The buyer can leave the meeting with one compact room packet, a visible packet verification result, two full archives, one verification packet and the receipt/activation chain.

## Verification

- `python -m py_compile src/services/rentgen/killer_demo_path.py`
- `pytest tests/unit/test_killer_demo_path.py -q`
- `npm run build` in `portal`
