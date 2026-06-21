# Outcome Ledger Post-Purchase Proof Spine - 2026-06-19

## Why

Outcome Ledger already showed Day 7/30/60/90 adoption, governance refresh and value claims.
It still needed an explicit Day 0 proof spine, otherwise a buyer could see measured outcomes without seeing
which accepted demo close, activation handoff and dual-archive receipt those outcomes inherit from.

## Implemented

1. Backend:
   - adds `MEETING_CLOSE_RECEIPT.md`, `POST_DEMO_ACTIVATION_HANDOFF.md`, `archive-acceptance-receipt.md/.json` and `killer-demo-manifest.json` to Outcome Ledger proof/export surfaces;
   - adds fallback `day0-activation-baseline` to `acceptance_rollup` when older Pilot Launchpad input does not yet include the close-packet row;
   - adds `post_purchase_proof_spine` with status, ready-to-measure/claim flags, buyer line, measurement rule, required routes, archive receipt and activation gate.

2. Portal:
   - adds Outcome Ledger TypeScript contract fields for `post_purchase_proof_spine`;
   - adds a first-class `Day 0 proof spine` panel before the value/adoption sections;
   - shows receipt, activation gate, required routes and send-ready files for buyer/procurement/audit roles.

3. Tests:
   - locks the presence of meeting receipt, activation handoff, archive receipt and Killer Demo manifest in proof/export lists;
   - verifies Day 0 fallback acceptance row and markdown output;
   - verifies blocked pilot acceptance keeps post-purchase measurement from becoming claimable.

## Buyer Impact

The post-purchase story is now continuous:

- the demo ends with `MEETING_CLOSE_RECEIPT.md`;
- paid activation starts from `POST_DEMO_ACTIVATION_HANDOFF.md`;
- procurement records both ZIP boundaries through `archive-acceptance-receipt.md/.json`;
- Outcome Ledger measures Day 30 value against that accepted Day 0 packet.

That makes the product feel less like a dashboard maze and more like a closed commercial operating loop.

## Verification

- `python -m py_compile src/services/rentgen/outcome_ledger.py`
- `pytest tests/unit/test_outcome_ledger.py -q`
- `npm.cmd run build`
