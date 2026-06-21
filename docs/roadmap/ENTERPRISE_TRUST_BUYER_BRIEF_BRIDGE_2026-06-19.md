# Enterprise Trust Buyer Brief Bridge

Date: 2026-06-19.

Enterprise Trust Center now carries the same Buyer Brief room map as Home, Buyer Concierge, Business Case, Vendor Portfolio and deal-route screens.

## Implemented

- New `trust_room_bridge` in `build_enterprise_trust_center`.
- `/api/v1/enterprise-trust-center/build` builds `buyer_brief` from the fast buyer-brief service and passes it through Value Packs, Vendor Portfolio, Business Case, Guided Demo, Scenario Hub, Pilot Launchpad, Demo Command Center and Enterprise Trust Center.
- `exports` starts with `buyer-brief.md` and `buyer-pulse.md`.
- Summary includes trust-room role, proof and meeting-step counts.
- `/enterprise-trust-center` UI shows Buyer Room Map before Security Questionnaire.
- `proof_routes` includes Buyer Brief meeting-flow routes, including `/killer-demo`.

## Buyer Effect

Security, architect and procurement roles now enter Trust Center with the same first-minute context as the commercial path. They see owner roles, proof readiness, required files and meeting flow before the longer questionnaire, making trust review a purchase enabler instead of a late blocker.

## Verification

- `python -m py_compile src/services/rentgen/enterprise_trust_center.py src/api/enterprise_trust_center_api.py tests/unit/test_enterprise_trust_center.py`
- `python -m pytest tests/unit/test_enterprise_trust_center.py -q`
- API build smoke confirms `management-buyer-brief`, five role cards, four proof items, four meeting steps, first files `buyer-brief.md`/`buyer-pulse.md`, `/killer-demo` route and `7 200 000 RUB` three-year AI rent in the room line when monthly AI cost is `200000`.
- `npm run build`
