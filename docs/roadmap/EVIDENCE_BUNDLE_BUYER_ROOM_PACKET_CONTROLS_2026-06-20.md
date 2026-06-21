# Evidence Bundle Buyer Room Packet Controls - 2026-06-20

## What Changed

- Portal `/evidence-bundle` now uses the shared `BuyerRoomPacketControls` component next to Evidence/Killer/dual verification actions.
- The duplicated local packet state, management API calls and verification cards were removed from the route.
- The same `Buyer Room Packet ZIP` and `Verify Buyer Room Packet` behavior now matches Home, Launch Room, Killer Demo, Pilot Launchpad, Outcome Ledger and pre-deal rooms.
- The downloaded packet is locally compared against `X-Buyer-Room-Packet-Sha256`.
- The verification card shows status, hash-table status, open-first status, archive SHA-256, checked file count and finding count.

## Buyer Impact

Security and procurement can stay inside the Evidence Bundle screen and still attach the compact open-first buyer packet before or alongside the larger archives and verification packet.

## Verification

- `npm run build` in `portal`
