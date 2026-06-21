# Launch Room Procurement Handoff Sync - 2026-06-20

## What Changed

- Launch Room `purchase_spine` now carries the same procurement-ready handoff shape as the first screen.
- The handoff names the open order: Evidence Bundle ZIP, Killer Demo ZIP, Verification Packet ZIP, close receipt and activation handoff.
- Launch Room markdown now includes `## Procurement Handoff` with file names and required hash headers.
- The portal Purchase Spine panel renders the handoff next to purchase artifacts.
- The Launch Room sidebar now downloads `Verification Packet ZIP` directly and compares the local ZIP hash with `X-Verification-Packet-Sha256`.

## Buyer Impact

A buyer can start from Home or jump directly into Launch Room and still see the same archive boundary and acceptance order. Procurement/security no longer has to infer whether `MEETING_CLOSE_RECEIPT.md` comes from the Evidence ZIP or the linked Killer Demo ZIP.

## Verification

- `python -m py_compile src/services/rentgen/launch_room.py`
- `pytest tests/unit/test_launch_room.py -q`
- `npm run build` in `portal`
