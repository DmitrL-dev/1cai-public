# Launch Room Purchase Artifact Sync - 2026-06-19

## Why

Home and Killer Demo now share a clear purchase path, but Launch Room still surfaced an older proof packet that did not name the actual post-demo buyer artifacts. The cockpit must show the same handoff files the buyer receives after the demo.

## Implemented

- Launch Room `purchase_spine.proof_routes` now includes:
  - `/killer-demo`
  - `/pilot-launchpad`
  - `/outcome-ledger`
- Launch Room `purchase_spine.evidence_files` now always starts with:
  - `OPEN_FIRST_KILLER_DEMO.md`
  - `MEETING_CLOSE_RECEIPT.md`
  - `POST_DEMO_ACTIVATION_HANDOFF.md`
- Existing Business Case evidence files are appended without duplicates.
- Launch Room `proof_packet` now includes Killer Demo open-first, Meeting Close Receipt, Post-Demo Activation Handoff and Killer Demo manifest before lower-level launch/board/outcome files.
- `buyer_room_bridge.files` now carries the same post-demo handoff files.
- Launch Room markdown now has a `Purchase Artifacts` section.
- Portal Launch Room Purchase Spine now shows a `Purchase artifacts` grid with the buyer-forwardable filenames and routes.

## Verification

```text
pytest tests/unit/test_launch_room.py -q
2 passed

npm.cmd run build
passed
```

## Product Effect

Launch Room now reinforces the same buying chain as Home and Killer Demo: start in the cockpit, prove in Killer Demo, forward the ZIP, close with receipt, activate with paid handoff and track outcomes. The buyer sees real artifact names before procurement asks for them.
