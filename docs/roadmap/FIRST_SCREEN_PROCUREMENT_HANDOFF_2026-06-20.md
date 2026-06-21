# First Screen Procurement Handoff - 2026-06-20

## What Changed

- Buyer Pulse `purchase_path` now includes `procurement_handoff`.
- Buyer Brief preserves that handoff and reports `summary.procurement_handoff_steps`.
- Home renders a compact procurement-ready checklist inside Purchase Path.
- Home now exposes a click-only `Verification Packet ZIP` action with local SHA-256 comparison.
- Home also exposes `Buyer Room Packet ZIP`, a lightweight open-first archive with Buyer Brief, Buyer Pulse, Buyer Room Plan, Purchase Path, Procurement Handoff and a packet hash table.
- The checklist names the open order: Evidence Bundle ZIP, Killer Demo ZIP, Verification Packet ZIP, close receipt and activation handoff.
- The same block exposes the hash headers buyers must record: `X-Archive-Sha256`, `X-Killer-Demo-Archive-Sha256` and `X-Verification-Packet-Sha256`.

## Buyer Impact

The first screen no longer leaves security/procurement to infer which files matter. A director sees the purchase path; an architect sees the archive boundary; procurement sees the exact order and headers needed to accept the handoff.

## Verification

- `python -m py_compile src/services/rentgen/buyer_pulse.py src/services/rentgen/buyer_brief.py`
- `python -m py_compile src/api/management_api.py`
- `pytest tests/unit/test_executive_dashboard.py -q`
- `npm run build` in `portal`
