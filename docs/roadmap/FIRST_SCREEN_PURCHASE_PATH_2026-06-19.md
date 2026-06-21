# First Screen Purchase Path - 2026-06-19

## Why

Killer Demo now produces a buyer ZIP, Meeting Close Receipt and Post-Demo Activation Handoff. The Home screen and fast Buyer Brief still needed to point at that same buying path before the user enters the deep workbench. Otherwise the first minute says "many tools", while the post-demo archive says "one purchasing chain".

## Implemented

- Added `purchase_path` to fast Buyer Pulse.
- Added `purchase_path` to Buyer Brief with:
  - `Launch Room`
  - `Killer Demo ZIP`
  - `MEETING_CLOSE_RECEIPT.md`
  - `POST_DEMO_ACTIVATION_HANDOFF.md`
  - `Outcome Ledger`
- Added `summary.purchase_path_steps` and `summary.purchase_path_files` to Buyer Brief.
- Evidence Bundle Buyer Pulse/Buyer Brief markdown and artifact summaries now include the same purchase path.
- Home Buyer Start now shows a compact `Purchase path` block with clickable route chain and real artifact filenames.
- Portal API client types now expose the new Buyer Pulse/Brief purchase path contract.

## Verification

```text
pytest tests/unit/test_executive_dashboard.py -q
6 passed

pytest tests/unit/test_evidence_bundle.py -q
5 passed

npm.cmd run build
passed
```

## Product Effect

The first screen now promises the same chain the archive later proves: start in Launch Room, prove in Killer Demo, close with receipt, activate with paid handoff and realize value in Outcome Ledger. That reduces "what is this product?" friction and makes the buyer path visible before the specialist surfaces appear.
