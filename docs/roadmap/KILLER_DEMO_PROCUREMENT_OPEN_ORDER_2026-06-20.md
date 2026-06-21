# Killer Demo Procurement Open Order - 2026-06-20

## What Changed

- Killer Demo `proof_packet.procurement_handoff` now carries `open_order`, `attachments`, `owner_line` and `acceptance`.
- The open order matches Home and Launch Room: Evidence Bundle ZIP, Killer Demo ZIP, Verification Packet ZIP, meeting close receipt and post-demo activation handoff.
- Killer Demo markdown prints the open order with archive hash headers.
- The portal Proof Packet procurement card renders the open order next to missing/blocker/recipient counters.

## Buyer Impact

At the end of the live demo, the presenter can close with one exact procurement sequence instead of a loose list of files. Security sees `X-Archive-Sha256`, `X-Killer-Demo-Archive-Sha256` and `X-Verification-Packet-Sha256` in the same close-room artifact.

## Verification

- `python -m py_compile src/services/rentgen/killer_demo_path.py`
- `pytest tests/unit/test_killer_demo_path.py -q`
- `npm run build` in `portal`
