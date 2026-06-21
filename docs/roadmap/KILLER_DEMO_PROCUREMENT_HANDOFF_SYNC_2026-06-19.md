# Killer Demo Procurement Handoff Sync - 2026-06-19

## Why

Killer Demo already had a proof packet and Evidence Bundle already had a procurement handoff, but the demo close still treated `bundle_id + bundle_sha256` as enough to call the packet forwardable. That could let the presenter ask for purchase while procurement still had missing files, blockers or risk review items.

## Implemented

- `proof_packet.ready_to_forward` now depends on both archive readiness and effective procurement handoff readiness.
- `proof_packet.procurement_handoff` exposes status, missing/blocker/review counts, recipients, verification steps, archive endpoint, hash header and first handoff file.
- Killer Demo compensates the intentional build-order gap where Evidence Bundle is built before the current Killer Demo markdown exists: a missing `killer-demo.md` blocker is covered when `rentgen-killer-demo-path.md` is attached by the current demo export.
- Deal Readiness now adds a concrete packet blocker with missing/blocker/review counts instead of a generic bundle-hash action.
- Killer Demo markdown includes procurement handoff status, archive endpoint and current-demo coverage.
- Portal Killer Demo Proof Packet now shows a Procurement handoff card with status, counts, recipients, verification steps and covered files.
- TypeScript API contract includes `proof_packet.procurement_handoff`.

## Verification

```text
pytest tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q
9 passed

npm.cmd run build
passed
```

## Product Effect

The buyer-facing close is now stricter and clearer: the presenter can ask for the paid step only when the proof archive and procurement handoff are effectively forwardable. If procurement is blocked, the same screen tells the room exactly what is missing and what must be resolved before the ask.
