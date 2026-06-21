# Killer Demo Buyer Room Packet Verify Sync - 2026-06-20

## What Changed

- Portal `/killer-demo` now has direct `Buyer Room Packet ZIP` and `Verify Buyer Room Packet` actions in the close-room sidebar.
- The downloaded ZIP is checked locally against `X-Buyer-Room-Packet-Sha256` before the presenter forwards it.
- Verification results show archive status, hash-table status, open-first status, archive SHA-256, checked file count and finding count.
- `readinessTone` now treats `pass` as green and `fail` as danger, matching the verification endpoint contract.

## Buyer Impact

Killer Demo can now end in one screen with the room packet downloaded, verified and ready to send to the committee. The presenter does not need to jump back to Home or Launch Room to prove the procurement packet is clean.

## Verification

- `npm run build` in `portal`
