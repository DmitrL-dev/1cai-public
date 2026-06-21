# Launch Room Buyer Room Packet Verify Sync - 2026-06-20

## What Changed

- Portal `/launch-room` now has `Verify Buyer Room Packet` next to the ZIP download.
- The verify action calls `GET /api/v1/management/buyer-room-packet/verify`.
- Launch Room shows packet status, hash-table status, open-first status, archive SHA-256, checked file count and finding count.

## Buyer Impact

If the buyer starts from Launch Room instead of Home, the same open-first room packet can be downloaded and verified from the cockpit before the meeting moves into deeper archives.

## Verification

- `npm run build` in `portal`
