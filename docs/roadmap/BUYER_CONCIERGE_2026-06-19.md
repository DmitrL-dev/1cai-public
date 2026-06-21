# Buyer Concierge - 2026-06-19

## Why This Slice Exists

The product now has proof, trust, pilot and commercial routes. That creates power, but also first-screen risk: a buyer can open the product, see many strong modules and still ask "where do I start?"

Buyer Concierge is the first-click layer. It routes the room by role or pain, then points to the shortest proof path and buy-now path.

## Implemented

- Backend service: `src/services/rentgen/buyer_concierge.py`
- API: `POST /api/v1/buyer-concierge/build`
- Health: `GET /api/v1/buyer-concierge/health`
- Portal: `/buyer-concierge`
- Evidence Bundle artifact: `buyer-concierge.json` and `buyer-concierge.md`
- Navigation: sidebar, home fast entry, Evidence Bundle toggle, route allow-lists in demo/pilot/scenario/guided/business/vendor/trust/commercial pages.
- Purchase Router: AI/month, three-year AI rent, local-license anchor, break-even, Launch Room primary CTA, recommended purchase, close sequence and role-specific purchase asks.
- Buyer Brief Bridge: `concierge_room_bridge` carries the first-minute room map into the role/pain screen before Purchase Router.

## Report Shape

The report contains:

- `orientation`: what the product is and is not.
- `default_next_action`: the safest next click for the current evidence state.
- `persona_cards`: Developer, Architect, Director, Security/CIO, Vendor, QA/Release and Operations.
- `purchase_router`: local-license buying motion with money anchors, quick actions, role prompts, close sequence, guardrails and proof files.
- `concierge_room_bridge`: Buyer Brief role cards, proof readiness, meeting flow, first files and close question.
- `pain_picker`: concrete pain cards such as LEFT JOIN/NULL, release go/no-go, platform update, enterprise trust and vendor audit.
- `shortest_paths`: 5-minute buyer route, developer spark, architect/security trust and vendor buy-now route.
- `confusion_guardrails`: presenter recovery when the buyer freezes, jumps to security, asks price early or loses meeting time.
- `exports`: buyer-safe markdown and links to Scenario Hub, Trust Center, Offer Studio and Evidence Bundle.

## Product Effect

This makes the product feel smaller at first contact without reducing its depth:

1. Pick role or pain.
2. Follow one short route.
3. Convert the role proof into a purchase ask.
4. Show trust if needed.
5. Select a commercial package.
6. Export hashed proof.

The product no longer depends on the buyer understanding the whole sidebar before seeing value.

## Purchase Router Effect

The first role/pain screen now repeats the commercial spine instead of hiding it in Business Case or Offer Studio:

- Director sees Launch Room as the primary action, plus the recommended paid step.
- Developer sees a defect proof as a route into a paid sprint, not an isolated lint finding.
- Architect sees platform/update evidence as hardening or pilot scope.
- Security sees locality, SBOM/offline posture, Rights/RLS and evidence retention as approval gates.
- Vendor sees the first audit as a packaged paid rollout path.

This keeps the product small at first contact while still making the buying motion explicit.

## Verification

- `python -m py_compile` for service/API/evidence integration.
- `python -m pytest tests/unit/test_buyer_concierge.py -q`
- `_build_report` smoke confirms `management-buyer-brief`, first files `buyer-brief.md`/`buyer-pulse.md` and `/killer-demo` in proof routes.
- API smoke should confirm `purchase_router.status`, `three_year_ai_rent`, `local_license_anchor` and `/launch-room` proof route.
- Health uses the shared fast buyer pulse and must not call the deep Concierge build path.
- Evidence Bundle regression requires `buyer-concierge` artifact and markdown manifest entry.
- Frontend build validates `/buyer-concierge` route generation and TypeScript contracts.
