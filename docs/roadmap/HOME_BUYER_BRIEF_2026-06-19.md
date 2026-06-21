# Home Buyer Brief

Date: 2026-06-19.

The Home first screen now has a fast first-minute buyer brief instead of assembling role and proof guidance only inside the frontend.

## Implemented

- Service: `src/services/rentgen/buyer_brief.py`.
- API: `GET /api/v1/management/buyer-brief`.
- Portal Home consumes `managementApi.buyerBrief()` and uses its embedded `pulse`.
- The brief returns:
  - `primary_motion` for the next buyer ask;
  - `room_line` for the first-minute commercial story;
  - five role cards: developer, architect, director, security, vendor;
  - four proof readiness items: Evidence Bundle, approvals, audit/SIEM, Trust Center;
  - `meeting_flow` for Orient -> Prove -> Ask -> Forward;
  - embedded fast `pulse` with AI-rent and purchase status.

## Product Effect

This tightens the anti-monster experience. The first screen no longer has to invent role guidance locally: backend and UI agree on the same buyer path, proof files and routes.

The buyer sees a concrete room map before deep reports: who is in the meeting, what proof to open, what file can be forwarded and how the local license compares with recurring AI rent.

## Verification

- `python -m py_compile src/services/rentgen/buyer_brief.py src/api/management_api.py tests/unit/test_executive_dashboard.py`
- `python -m pytest tests/unit/test_executive_dashboard.py -q`
- `npm run build`
- Authenticated smoke: `GET /api/v1/management/buyer-brief?monthly_ai_subscription_cost=200000` returns `source: management-buyer-brief`, 5 role cards, 4 proof readiness items and `7 200 000 RUB`.
