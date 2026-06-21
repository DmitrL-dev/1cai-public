# Buyer Room Packet Shared Portal Controls - 2026-06-20

## What Changed

- `BuyerRoomPacketControls` is now the single portal component for Buyer Room Packet download and verification.
- Home, Launch Room, Killer Demo, Pilot Launchpad, Outcome Ledger and Evidence Bundle use the shared component.
- Board Pack, Commercial Offer Studio, Enterprise Trust Center, Buyer Concierge, Scenario Hub, Demo Command Center, Guided Demo, Business Case, Value Packs and Vendor Portfolio already use the same control.
- Evidence Bundle no longer keeps duplicated local `buyerRoomPacket*` state, mutations or result cards.

## Buyer Impact

Every buyer-facing path now exposes the same compact open-first packet with the same SHA-256 comparison and endpoint verification result. A director, architect, developer or procurement reviewer can start from any major screen and still attach the same verified room packet instead of hunting for the correct archive.

## Verification

- `npm run build` in `portal`
- targeted `rg` checks confirm the old local packet mutations are gone from Launch Room, Killer Demo, Pilot Launchpad, Outcome Ledger and Evidence Bundle.
