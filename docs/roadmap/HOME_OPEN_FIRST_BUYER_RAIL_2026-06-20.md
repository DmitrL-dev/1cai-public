# Home Open-First Buyer Rail - 2026-06-20

## What Changed

- Home now shows an `Open-first path` rail directly under the primary buyer motion.
- The rail compresses the first buyer sequence into four visible actions: orient, prove, close and verify.
- When Buyer Brief data is available, the rail is data-driven from `buyer_room_plan`, first `proof_readiness` item, close artifact and Verification Packet artifact.
- The rail now reads the backend `buyerBrief.open_first_path` contract directly, keeping local reconstruction only as a loading fallback.
- When Buyer Brief data is still loading, the rail falls back to Launch Room, Killer Demo, Evidence Bundle and Pilot Launchpad so the first screen remains understandable.
- Each rail item links to its route and shows the file that should travel with the meeting or procurement handoff.

## Buyer Impact

The first screen no longer asks a new client to understand every module at once. It gives a compact "open this first, prove this, close here, verify this" path before exposing the deeper workbench. Developers still get proof files, architects get verification, and directors see a purchase sequence.

## Verification

- `npm run build` in `portal`
- `pytest tests/unit/test_executive_dashboard.py tests/unit/test_evidence_bundle.py -q` after materializing `open_first_path`
