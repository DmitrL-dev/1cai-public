# Launch Room Buyer Brief Bridge

Date: 2026-06-19.

Launch Room now consumes the same Buyer Brief language as Home, Killer Demo and Evidence Bundle.

## Implemented

- New `buyer_room_bridge` in `build_launch_room`.
- `/api/v1/launch-room/build` builds `buyer_brief` from the fast buyer-brief service and passes it into the deep cockpit.
- Launch Room proof packet starts with `buyer-brief.md` and `buyer-pulse.md`.
- Summary includes buyer-room role, proof and meeting-step counts.
- `/launch-room` UI shows a Buyer room bridge panel with primary motion, role cards, meeting flow, proof readiness and send files.
- `proof_routes` now includes the Buyer Brief meeting flow routes, including `/killer-demo`.

## Buyer Effect

The first launch cockpit no longer asks the buyer to infer the room map from phases. It shows who is in the meeting, which proof each role should see, which files are forwardable and which paid ask should happen next.

## Verification

- `python -m py_compile src/services/rentgen/launch_room.py src/api/launch_room_api.py tests/unit/test_launch_room.py`
- `python -m pytest tests/unit/test_launch_room.py -q`
- `npm run build`
