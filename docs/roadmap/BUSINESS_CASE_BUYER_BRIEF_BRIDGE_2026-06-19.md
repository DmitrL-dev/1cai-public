# Business Case Buyer Brief Bridge

Date: 2026-06-19.

Business Case now carries the same Buyer Brief room map as Home, Buyer Concierge, Evidence Bundle and deal-route screens.

## Implemented

- New `business_room_bridge` in `build_business_case`.
- `/api/v1/business-case/build` builds `buyer_brief` from the fast buyer-brief service and passes it into Business Case.
- Summary includes business-room role, proof and meeting-step counts.
- `/business-case` UI shows Buyer Room Map before the money levers and subscription escape.
- Evidence routes now include Buyer Brief meeting-flow routes, including `/killer-demo`.

## Buyer Effect

The director sees the same first-minute role/proof map before the economic argument. The value story starts with who is in the room, what proof is ready, what files can be forwarded and only then explains AI rent, local-license anchor and break-even.

## Verification

- `python -m py_compile src/services/rentgen/business_case.py src/api/business_case_api.py tests/unit/test_business_case.py`
- `python -m pytest tests/unit/test_business_case.py -q`
- API build smoke confirms `management-buyer-brief`, five role cards, four proof items, four meeting steps, first files `buyer-brief.md`/`buyer-pulse.md`, `/killer-demo` route and `7 200 000 RUB` three-year AI rent in the room line when monthly AI cost is `200000`.
- `npm run build`
