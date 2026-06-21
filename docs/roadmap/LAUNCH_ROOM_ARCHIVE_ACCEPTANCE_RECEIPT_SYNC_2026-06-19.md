# Launch Room Archive Acceptance Receipt Sync - 2026-06-19

## Why

Launch Room is the first buyer cockpit. After Evidence Bundle gained a dual-archive acceptance receipt,
Launch Room also needed to point to that receipt; otherwise the buying room could still end at
`MEETING_CLOSE_RECEIPT.md` and `POST_DEMO_ACTIVATION_HANDOFF.md` without telling procurement how to record both ZIP hashes.

## Implemented

1. Added `archive-acceptance-receipt.md` to `purchase_spine.evidence_files`.
2. Added `archive-acceptance-receipt.md` and `archive-acceptance-receipt.json` to Launch Room proof packet.
3. Added `archive-acceptance-receipt.md` to `buyer_room_bridge.files`.
4. Launch Room markdown now includes the receipt through the Purchase Artifacts section.

## Buyer Impact

The first cockpit now carries the full close path:

1. open Killer Demo ZIP;
2. send meeting close receipt;
3. send post-demo activation handoff;
4. record Evidence Bundle ZIP and linked Killer Demo ZIP hashes through the archive acceptance receipt.

This keeps the buyer from falling out of the purchase flow when procurement asks for exact archive evidence.

## Verification

- `tests/unit/test_launch_room.py` checks purchase artifacts, proof packet, buyer room bridge and markdown.
