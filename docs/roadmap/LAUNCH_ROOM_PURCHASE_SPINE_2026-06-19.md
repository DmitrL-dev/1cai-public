# Launch Room Purchase Spine

Date: 2026-06-19.

Launch Room now shows the buying spine on the first buyer cockpit: local product value, AI-rent baseline, local-license anchor, break-even, invoice trigger and proof routes. This keeps the first screen from feeling like a navigation dashboard detached from the commercial reason to buy.

## Implemented

- Backend `purchase_spine` in `src/services/rentgen/launch_room.py`.
- Launch Room markdown includes a `Purchase Spine` section.
- `/launch-room` UI shows a dedicated Purchase Spine panel with AI/month, three-year AI rent, local-license anchor, break-even, invoice trigger and proof routes.
- `LaunchRoomResponse` TypeScript contract includes `purchase_spine`.
- `/api/v1/launch-room/health` exposes `purchase_spine_status` and `three_year_ai_rent`.
- Unit regression verifies route, local-license anchor, break-even and markdown visibility.

## Buyer Value

1. The first cockpit answers why this is a purchase instead of another recurring AI subscription.
2. Directors see the local-license motion before diving into Board Pack or Offer Studio.
3. Procurement can jump from the first cockpit to Business Case, Offer Studio, Board Pack and Evidence Bundle without losing the commercial thread.
4. Developers and architects still keep their role paths, but the meeting has a visible paid next step.

## Verification

- `python -m py_compile src/services/rentgen/launch_room.py src/api/launch_room_api.py`
- `python -m pytest tests/unit/test_launch_room.py -q`
