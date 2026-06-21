# First Screen Archive Receipt Sync - 2026-06-19

## Why

The Home purchase path already showed the high-conversion chain:

Launch Room -> Killer Demo ZIP -> Meeting Close Receipt -> Post-Demo Activation Handoff -> Outcome Ledger.

After dual-archive procurement receipt was added, the first screen also needed to name that receipt.
Otherwise the buyer could understand the demo path but still miss the exact file procurement needs for recording both ZIP hashes.

## Implemented

1. Buyer Pulse `purchase_path.send_files` now includes:
   - `archive-acceptance-receipt.md`;
   - `archive-acceptance-receipt.json`.

2. Buyer Brief `purchase_path` now includes:
   - `archive_receipt_artifact`;
   - deduplicated purchase send files with receipt markdown/json.

3. Buyer Pulse and Buyer Brief markdown exports include purchase path files and the archive receipt.

4. Home purchase path shows the archive receipt as a third mini artifact next to:
   - `MEETING_CLOSE_RECEIPT.md`;
   - `POST_DEMO_ACTIVATION_HANDOFF.md`.

## Buyer Impact

The first screen now tells the buyer not only what happens after the demo, but which procurement receipt records:

- Evidence Bundle ZIP hash;
- linked Killer Demo ZIP hash;
- correct file boundaries between evidence archive and close-room archive.

## Verification

- `tests/unit/test_executive_dashboard.py` checks Buyer Pulse/Brief purchase path fields.
- `tests/unit/test_evidence_bundle.py` checks materialized markdown/JSON artifacts.
- `npm run build` validates the Home UI.
