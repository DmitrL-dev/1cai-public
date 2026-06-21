# Killer Demo Open-First Path Panel - 2026-06-20

## What Changed

- Killer Demo proof packets now expose `open_first_path` as the same four-step orient/prove/close/verify contract used by Home, Buyer Room Packet, Evidence Bundle and role rooms.
- The backend reads the path from the Evidence Bundle `open-first-path` JSON artifact when present, then normalizes it through the shared open-first helper; older bundles fall back to a stable Killer Demo route.
- Killer Demo Markdown now prints the four open-first steps inside the Proof Packet section instead of only naming `open-first-path.md`.
- The portal Killer Demo page renders the path with the shared `OpenFirstPathList` component before role-packet coverage, so the close-room proof starts with a visible action path rather than a file list.
- Unit coverage asserts the stages, files, summary counter and Markdown export.

## Verification

- `python -m py_compile src/services/rentgen/killer_demo_path.py tests/unit/test_killer_demo_path.py`
- `pytest tests/unit/test_killer_demo_path.py -q`
- `npm run build` in `portal`
