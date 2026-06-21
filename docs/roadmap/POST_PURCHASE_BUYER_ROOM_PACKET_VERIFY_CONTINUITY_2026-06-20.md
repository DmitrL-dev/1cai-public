# Post-Purchase Buyer Room Packet Verify Continuity - 2026-06-20

## What Changed

- Portal `/pilot-launchpad` now exposes direct `Buyer Room Packet ZIP` and `Verify Buyer Room Packet` controls.
- Portal `/outcome-ledger` now exposes the same packet download and verification controls for Day 30/90 proof review.
- Both screens compute the downloaded packet SHA-256 locally and compare it with `X-Buyer-Room-Packet-Sha256`.
- Verification cards show endpoint status, hash-table status, open-first status, archive SHA-256, checked file count and finding count.

## Buyer Impact

The post-purchase path no longer relies on the buyer remembering which earlier screen had the packet download. Day 0 activation and later outcome claims can attach the same verified open-first packet directly from the workflow they are using.

## Verification

- `npm run build` in `portal`
