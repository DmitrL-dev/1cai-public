# Verification Packet Pre-Deal Role Controls - 2026-06-20

## What Changed

- Added the shared `VerificationPacketControls` ZIP download to Buyer Concierge, Scenario Hub, Demo Command Center, Guided Demo, Business Case, Value Packs, Vendor Portfolio, Commercial Offer Studio, Board Pack and Enterprise Trust Center.
- Each room now builds an Evidence Bundle verification-packet request with its own include flag plus Killer Demo, so role-first, value-first and trust-first buyers can attach the same pair-level procurement control ZIP without leaving the room.
- Value Packs uses a stable demo verification request because the page is catalog-driven rather than form-driven.

## Buyer Impact

Buyers who start from a role, package, vendor audit, commercial offer, board decision or trust review can now download both the open-first Buyer Room Packet and the archive Verification Packet from the same surface.

## Verification

- `npm run build` in `portal`
