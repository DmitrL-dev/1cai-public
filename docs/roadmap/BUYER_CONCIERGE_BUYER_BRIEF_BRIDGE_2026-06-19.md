# Buyer Concierge Buyer Brief Bridge

Date: 2026-06-19.

Buyer Concierge now carries the same Buyer Brief room map as Home, Evidence Bundle, Killer Demo, Scenario Hub, Guided Demo and deal-route screens.

## Implemented

- New `concierge_room_bridge` in `build_buyer_concierge`.
- `/api/v1/buyer-concierge/build` builds `buyer_brief` from the fast buyer-brief service and passes it into Guided Demo, Scenario Hub, Pilot Launchpad, Demo Command Center, Commercial Offer Studio and Buyer Concierge.
- `exports` starts with `buyer-brief.md` and `buyer-pulse.md`.
- Summary includes concierge-room role, proof and meeting-step counts.
- `/buyer-concierge` UI shows Buyer Room Map before Purchase Router.
- `proof_routes` now includes Buyer Brief meeting-flow routes, including `/killer-demo`.

## Buyer Effect

The first role/pain screen now starts with the same room map that travels through the rest of the buying chain. A new customer can pick a role, see first files, understand proof readiness and move to Launch Room or Killer Demo without interpreting the whole product surface.

## Verification

- `python -m py_compile src/services/rentgen/buyer_concierge.py src/api/buyer_concierge_api.py tests/unit/test_buyer_concierge.py`
- `python -m pytest tests/unit/test_buyer_concierge.py -q`
- `_build_report` smoke for Buyer Concierge confirms `management-buyer-brief`, five role cards, four proof items, four meeting steps, first files `buyer-brief.md`/`buyer-pulse.md`, `/killer-demo` route and `7 200 000 RUB` three-year AI rent in the room line when monthly AI cost is `200000`.
- `npm run build`
