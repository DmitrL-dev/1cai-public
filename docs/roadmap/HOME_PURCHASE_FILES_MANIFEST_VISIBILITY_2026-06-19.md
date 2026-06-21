# Home Purchase Files Manifest Visibility - 2026-06-19

## Why

The first screen already explained the purchase path, but it only highlighted three artifacts visually.
After adding the Day 0 proof spine, `killer-demo-manifest.json` also became part of the buyer/procurement handoff.
Home needed to show the send-ready file list so the manifest is not introduced late in Evidence Bundle or Outcome Ledger.

## Implemented

- Home `BuyerPurchasePath` now renders compact `Files to forward` chips from `purchase_path.send_files`.
- Management API tests assert `killer-demo-manifest.json` is present in both Buyer Pulse and Buyer Brief purchase-path send files.
- The visible first screen now puts `MEETING_CLOSE_RECEIPT.md`, `POST_DEMO_ACTIVATION_HANDOFF.md`, `archive-acceptance-receipt.md/.json` and `killer-demo-manifest.json` in the same buyer path.

## Buyer Impact

The buyer sees the close/activation/procurement file set before opening deep workbench pages.
That reduces the "what are all these archives?" moment and makes the product feel like one guided commercial path.

## Verification

- `pytest tests/unit/test_executive_dashboard.py -q`
- `npm.cmd run build`
