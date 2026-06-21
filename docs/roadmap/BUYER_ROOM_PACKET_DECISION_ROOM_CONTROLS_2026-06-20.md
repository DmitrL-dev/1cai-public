# Buyer Room Packet Decision Room Controls - 2026-06-20

## What Changed

- Added shared portal `BuyerRoomPacketControls` for packet download, local SHA-256 comparison and endpoint verification.
- Board Pack now exposes `Buyer Room Packet ZIP` and `Verify Buyer Room Packet` from the director decision room.
- Commercial Offer Studio now exposes the same controls beside the one-page order and proposal export.
- Enterprise Trust Center now exposes the same controls for security and procurement review.

## Buyer Impact

Director, procurement and security rooms can attach the compact open-first buyer packet without jumping back to Home, Launch Room or Evidence Bundle. This keeps the buying decision tied to the same verified hash trail that opens the demo room.

## Verification

- `npm run build` in `portal`
