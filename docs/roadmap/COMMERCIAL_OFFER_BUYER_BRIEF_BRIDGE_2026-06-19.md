# Commercial Offer Buyer Brief Bridge

Date: 2026-06-19.

Commercial Offer Studio now starts from the same Buyer Brief room map as Home, Evidence Bundle, Killer Demo, Launch Room and Board Pack.

## Implemented

- New `offer_room_bridge` in `build_commercial_offer_studio`.
- `/api/v1/commercial-offer-studio/build` builds `buyer_brief` from the fast buyer-brief service and passes it into the commercial offer report.
- `exports` starts with `buyer-brief.md` and `buyer-pulse.md`.
- Summary includes offer-room role, proof and meeting-step counts.
- `/commercial-offer-studio` UI shows Offer Room Bridge before procurement dossier and close packet.
- `proof_routes` now includes Buyer Brief meeting-flow routes, including `/killer-demo`.

## Buyer Effect

The commercial screen no longer opens as a price sheet. It starts with who is in the room, which proof each role needs, which files should be forwarded first, what paid motion is being asked for, and which recommended purchase backs that motion.

## Verification

- `python -m py_compile src/services/rentgen/commercial_offer_studio.py src/api/commercial_offer_studio_api.py tests/unit/test_commercial_offer_studio.py`
- `python -m pytest tests/unit/test_commercial_offer_studio.py -q`
- `python -m pytest tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- API smoke for `POST /api/v1/commercial-offer-studio/build` confirms `management-buyer-brief`, five role cards, four proof items, four meeting steps, first files `buyer-brief.md`/`buyer-pulse.md`, `/killer-demo` routes and `7 200 000 RUB` three-year AI rent when monthly AI cost is `200000`.
