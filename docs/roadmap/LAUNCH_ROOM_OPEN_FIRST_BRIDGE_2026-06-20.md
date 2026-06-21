# Launch Room Open-First Bridge - 2026-06-20

## What Changed

- Launch Room `buyer_room_bridge` now carries `open_first_path`.
- If Buyer Brief already provides the path, Launch Room preserves it; otherwise it builds a safe fallback from meeting/proof/purchase signals.
- Launch Room Markdown now includes an `Open-First Path` section.
- Portal `/launch-room` renders the path before role cards, meeting flow and proof readiness.
- The bridge file list includes `open-first-path.md`.

## Buyer Impact

The main cockpit now repeats the same orient/prove/close/verify sequence seen on Home and inside the Buyer Room Packet. A buyer who starts from Launch Room does not need to infer the first path from separate role cards and proof blocks.

## Verification

- `python -m py_compile src/services/rentgen/launch_room.py`
- `pytest tests/unit/test_launch_room.py -q` -> 2 passed.
- `npm run build` in `portal`
