# Launch Room Buyer Room Packet Sync - 2026-06-20

## What Changed

- Launch Room `purchase_spine.evidence_files` now starts with `rentgen-buyer-room-packet.zip`.
- Launch Room `procurement_handoff.open_order` now has 6 steps and starts with Buyer Room Packet ZIP plus `X-Buyer-Room-Packet-Sha256`.
- Launch Room `proof_packet` and `buyer_room_bridge.files` include the same packet.
- Launch Room markdown prints the new file and hash header in Purchase Artifacts / Procurement Handoff.
- Portal `/launch-room` now has a `Buyer Room Packet ZIP` button with local SHA-256 comparison.
- Portal `/launch-room` now also has `Verify Buyer Room Packet`, showing verify status, hash-table status, open-first status, archive SHA-256 and finding count.

## Buyer Impact

If the buyer starts from Launch Room instead of Home, the room still gets the same compact open-first packet before deep archives. The cockpit, markdown and downloadable controls now tell the same procurement story.

## Verification

- `python -m py_compile src/services/rentgen/launch_room.py`
- `pytest tests/unit/test_launch_room.py -q`
- `npm run build` in `portal`
