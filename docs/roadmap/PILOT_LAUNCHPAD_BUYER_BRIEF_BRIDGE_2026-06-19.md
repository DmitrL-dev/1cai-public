# Pilot Launchpad Buyer Brief Bridge

Date: 2026-06-19.

Pilot Launchpad now carries the same Buyer Brief room map as Home, Evidence Bundle, Killer Demo, Launch Room, Board Pack and Commercial Offer Studio.

## Implemented

- New `pilot_room_bridge` in `build_pilot_launchpad`.
- `/api/v1/pilot-launchpad/build` builds `buyer_brief` from the fast buyer-brief service and passes it into the pilot activation report.
- `exports` starts with `buyer-brief.md` and `buyer-pulse.md`.
- Summary includes pilot-room role, proof and meeting-step counts.
- `/pilot-launchpad` UI shows Pilot Room Bridge before pilot offers and activation contract.
- `proof_routes` now includes Buyer Brief meeting-flow routes, including `/killer-demo`.

## Buyer Effect

Pilot activation no longer starts as an operational checklist. It starts with the same role map, proof readiness, first files and meeting flow that the buyer saw before purchase, then converts that motion into a selected paid pilot, invoice trigger, gates and Day 0/7/30 acceptance.

## Verification

- `python -m py_compile src/services/rentgen/pilot_launchpad.py src/api/pilot_launchpad_api.py tests/unit/test_pilot_launchpad.py`
- `python -m pytest tests/unit/test_pilot_launchpad.py -q`
- `python -m pytest tests/unit/test_pilot_launchpad.py tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- API smoke for `POST /api/v1/pilot-launchpad/build` confirms `management-buyer-brief`, five role cards, four proof items, four meeting steps, first files `buyer-brief.md`/`buyer-pulse.md`, `/killer-demo` routes and `7 200 000 RUB` three-year AI rent when monthly AI cost is `200000`.
