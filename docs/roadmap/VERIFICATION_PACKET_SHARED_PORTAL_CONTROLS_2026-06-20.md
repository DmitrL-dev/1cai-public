# Verification Packet Shared Portal Controls - 2026-06-20

## What Changed

- Added `VerificationPacketControls` as the single portal component for `Verification Packet ZIP`.
- Home, Launch Room, Killer Demo, Pilot Launchpad, Outcome Ledger and Evidence Bundle now use the shared component.
- Launch Room, Pilot Launchpad and Outcome Ledger no longer keep duplicated verification-packet download helpers, state or mutations.
- Killer Demo and Evidence Bundle still keep their archive-specific helpers, but their verification-packet action is now shared.
- The shared control compares the downloaded file hash with `X-Verification-Packet-Sha256` and shows file count plus dual-verification status.

## Buyer Impact

The procurement control ZIP now behaves the same from the first screen, close room, activation room, outcome room and evidence workbench. A sponsor or security reviewer can start anywhere and still get the same hash-visible verification attachment.

## Verification

- `npm run build` in `portal`
- targeted `rg` checks confirm old `verificationPacketMutation` and `verificationPacketInfo` route-local blocks are gone.
