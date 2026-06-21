# Killer Demo Buyer Brief Sync

Date: 2026-06-19.

Buyer Brief is now part of the Killer Demo proof packet, not only Home and Evidence Bundle.

## Implemented

- `proof_packet.room_map` in `build_killer_demo_path`.
- `buyer-brief.md` and `buyer-pulse.md` are selected and priority-ordered before technical proof files.
- Developer/QA, architect/security and director/sponsor handoff packets start with `buyer-brief.md`.
- Committee close board role send-files include `buyer-brief.md`.
- Proof-forwarding objection now points to `buyer-brief.md`.
- `/killer-demo` UI shows a dedicated Buyer room map card before the ZIP archive and file list.

## Buyer Effect

The demo handoff starts with a readable role map, proof readiness and meeting flow before the buyer sees deeper artifacts. A director, architect, security owner or developer can forward the same first-minute map without explaining the whole product tree.

## Verification

- `python -m py_compile src/services/rentgen/killer_demo_path.py tests/unit/test_killer_demo_path.py`
- `python -m pytest tests/unit/test_killer_demo_path.py -q`
- `npm run build`
