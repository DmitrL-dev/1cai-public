# Guided Demo Buyer Brief Bridge

Date: 2026-06-19.

Guided Demo now carries the same Buyer Brief room map as Home, Evidence Bundle, Demo Command Center, Killer Demo and deal-route screens.

## Implemented

- New `guided_room_bridge` in `build_guided_demo`.
- `/api/v1/guided-demo/build` builds `buyer_brief` from the fast buyer-brief service and passes it into Guided Demo.
- `exports` starts with `buyer-brief.md` and `buyer-pulse.md`.
- Summary includes guided-room role, proof and meeting-step counts.
- `/guided-demo` UI shows Guided Room Bridge before opening proof and buyer route.
- `proof_routes` now includes Buyer Brief meeting-flow routes, including `/killer-demo`.

## Buyer Effect

The guided walkthrough now starts with the same role map, first files and proof readiness used by the rest of the buyer path. The presenter can pick one role path, prove one pain and forward artifacts without showing the whole product menu.

## Verification

- `python -m py_compile src/services/rentgen/guided_demo.py src/api/guided_demo_api.py tests/unit/test_guided_demo.py`
- `python -m pytest tests/unit/test_guided_demo.py -q`
- `python -m pytest tests/unit/test_guided_demo.py tests/unit/test_demo_command_center.py tests/unit/test_outcome_ledger.py tests/unit/test_pilot_launchpad.py tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- API smoke for `POST /api/v1/guided-demo/build` confirms `management-buyer-brief`, five role cards, four proof items, four meeting steps, first files `buyer-brief.md`/`buyer-pulse.md`, `/killer-demo` route and `7 200 000 RUB` three-year AI rent in the room line when monthly AI cost is `200000`.
