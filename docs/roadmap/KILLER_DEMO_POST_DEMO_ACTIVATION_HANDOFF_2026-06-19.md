# Killer Demo Post-Demo Activation Handoff - 2026-06-19

## Why

Meeting Close Receipt captures what happened in the room, but the buyer also needs to know what happens next. Without a post-demo activation handoff, the proof ZIP can still become "nice archive, unclear next step". The close must flow into paid start, Day 7 proof and Day 30 acceptance.

## Implemented

- Added `post_demo_activation_handoff` to Killer Demo.
- Added `proof_packet.activation_handoff` and `summary.activation_handoff_ready`.
- Added buyer-forwardable activation files to the Killer Demo ZIP:
  - `POST_DEMO_ACTIVATION_HANDOFF.md`
  - `post-demo-activation-handoff.json`
- Added activation handoff metadata and SHA-256 file entries to `killer-demo-manifest.json`.
- `MEETING_CLOSE_RECEIPT.md/.json` now references the activation handoff and includes its files in `send_files`.
- Commercial Close Packet evidence requirements now include `Post-Demo Activation Handoff` after `Killer Demo ZIP` and `Meeting Close Receipt`.
- Portal Killer Demo now has an `Activation` JSON download button and a Proof Packet card showing activation status, files, route chain, start route and next outcome window.

## Verification

```text
pytest tests/unit/test_killer_demo_path.py tests/unit/test_killer_demo_api.py -q
9 passed

npm.cmd run build
passed
```

## Product Effect

The buyer no longer receives only proof of the demo. They receive the bridge from proof to paid start: next paid step, owner, invoice trigger, route chain, gates, Day 7 proof and Day 30 outcome path. That keeps the emotional peak of the demo connected to an operational buying motion.
