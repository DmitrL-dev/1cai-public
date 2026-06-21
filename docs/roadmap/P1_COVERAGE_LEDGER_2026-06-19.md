# P1 Coverage Ledger - 2026-06-19

## Why

Several surfaces already had local caveats, but the product still needed one shared buyer-facing contract:
missing or partial evidence must look the same in Home, Demo Story and Vendor Audit, not green in one place and cautious in another.

## Implemented

- Added `src/services/rentgen/coverage_ledger.py`.
- Executive Dashboard now includes `coverage_ledger` as the top-level management contract.
- Buyer Brief now includes `coverage_ledger` and `summary.coverage_caveats`.
- Demo Story now includes `coverage_ledger` and exports it in markdown.
- Vendor Portfolio now includes `coverage_ledger`, projects caveat count into portfolio summary, and carries the same ledger through `vendor_room_bridge`.
- Home screen shows an `Evidence coverage` block with measured/items, risk count and caveats.
- API client types now include `CoverageLedgerResponse`.

## Regression

```text
pytest tests/unit/test_coverage_ledger.py tests/unit/test_management_demo_intake.py tests/unit/test_executive_dashboard.py tests/unit/test_vendor_portfolio.py -q
15 passed

npm.cmd run build
passed
```

## Caveat

This closes the P1 shared-ledger contract for buyer/demo/vendor surfaces. Lower-level specialist pages can still add richer local rows, but they should reuse the same language: measured, unknown, risk, caveat.
