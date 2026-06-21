# Scenario Hub Buyer Brief Bridge

Date: 2026-06-19.

Scenario Hub now carries the same Buyer Brief room map as Home, Evidence Bundle, Guided Demo, Demo Command Center, Killer Demo and deal-route screens.

## Implemented

- New `scenario_room_bridge` in `build_scenario_hub`.
- `/api/v1/scenario-hub/build` builds `buyer_brief` from the fast buyer-brief service and passes it into Scenario Hub.
- `exports` starts with `buyer-brief.md` and `buyer-pulse.md`.
- Summary includes scenario-room role, proof and meeting-step counts.
- `/scenario-hub` UI shows Scenario Room Bridge before recommended path and scenario cards.
- `proof_routes` now includes Buyer Brief meeting-flow routes, including `/killer-demo`.

## Buyer Effect

The pain gallery now starts with one buyer room map before it opens the larger scenario catalog. A new customer can pick a recognizable 1C pain, see which role owns it, verify the first proof files and move to the right demo/close route without parsing the whole product.

## Verification

- `python -m py_compile src/services/rentgen/scenario_hub.py src/api/scenario_hub_api.py tests/unit/test_scenario_hub.py`
- `python -m pytest tests/unit/test_scenario_hub.py -q`
- `python -m pytest tests/unit/test_scenario_hub.py tests/unit/test_guided_demo.py tests/unit/test_demo_command_center.py tests/unit/test_outcome_ledger.py tests/unit/test_pilot_launchpad.py tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- API smoke for `POST /api/v1/scenario-hub/build` confirms `management-buyer-brief`, five role cards, four proof items, four meeting steps, first files `buyer-brief.md`/`buyer-pulse.md`, `/killer-demo` route and `7 200 000 RUB` three-year AI rent in the room line when monthly AI cost is `200000`.
