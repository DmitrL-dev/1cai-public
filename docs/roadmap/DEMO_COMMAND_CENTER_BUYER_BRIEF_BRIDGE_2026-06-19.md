# Demo Command Center Buyer Brief Bridge

Date: 2026-06-19.

Demo Command Center now carries the same Buyer Brief room map as Home, Evidence Bundle, Killer Demo and the deal/activation/outcome screens.

## Implemented

- New `demo_room_bridge` in `build_demo_command_center`.
- `/api/v1/demo-command-center/build` builds `buyer_brief` from the fast buyer-brief service and passes it into Pilot Launchpad and Demo Command Center.
- `exports` starts with `buyer-brief.md` and `buyer-pulse.md`.
- Summary includes demo-room role, proof and meeting-step counts.
- `/demo-command-center` UI shows Demo Room Bridge before live stages.

## Buyer Effect

The live presenter screen now starts with the buyer room map, first files, presenter opening, role cards, proof readiness and close question. A new presenter can start from one buyer-safe route instead of showing the whole product map.

## Verification

- `python -m py_compile src/services/rentgen/demo_command_center.py src/api/demo_command_center_api.py tests/unit/test_demo_command_center.py`
- `python -m pytest tests/unit/test_demo_command_center.py -q`
- `python -m pytest tests/unit/test_demo_command_center.py tests/unit/test_outcome_ledger.py tests/unit/test_pilot_launchpad.py tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- API smoke for `POST /api/v1/demo-command-center/build` confirms `management-buyer-brief`, five role cards, four proof items, four meeting steps, first files `buyer-brief.md`/`buyer-pulse.md`, `/killer-demo` route and `7 200 000 RUB` three-year AI rent in the room line when monthly AI cost is `200000`.
