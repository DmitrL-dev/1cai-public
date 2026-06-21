# Killer Demo Path v1

Date: 2026-06-19.

Killer Demo Path is the buyer-facing presentation route over Launch Room, Test Factory, Trust Center, Board Pack, Outcome Ledger and Evidence Bundle. It answers the product question: "what do we show first so a developer, architect, security owner and director all understand why this is worth buying?"

## Implemented

- Backend service: `src/services/rentgen/killer_demo_path.py`
- API: `POST /api/v1/killer-demo/build`
- UI: `/killer-demo`
- Evidence Bundle artifact: `killer-demo.json` and `killer-demo.md`
- Request assumptions: `monthly_ai_subscription_cost` and related Business Case assumptions flow into the generated Evidence Bundle and back into Killer Demo close artifacts.
- Navigation: sidebar, home fast entry, route tree and Evidence Bundle toggle
- Health is fast-pulse based; `POST /build` remains the proof-complete demo path over Evidence Bundle.
- Tests: `tests/unit/test_killer_demo_path.py`, plus Evidence Bundle artifact coverage

## Report Shape

- `primary_route`: the first route to open; switches to Trust Center if enterprise trust is risky.
- `opening_brief`: first click, first-30-second talk track, role entries, anti-confusion responses and success signal.
- `killer_stages`: six-stage path from single-door orientation to artifact close.
- `demo_modes`: 3-minute, 5-minute, 8-minute board and security-first variants.
- `role_sparks`: role-specific first click, proof and close line.
- `proof_moments`: developer, security, director, sponsor and evidence moments.
- `close_scripts`: audience-specific closing prompts.
- `exports`: buyer-safe artifact list.
- `proof_packet`: bundle id/hash when available, ZIP proof archive route, key artifact files, SHA-256 values and role-specific handoff instructions.
- `safe-autopilot` route in proof packet: developer/QA handoff includes safe diff blueprint, tests and approval policy.
- `governance-proof` in proof packet: approval/audit evidence travels with the buyer handoff through `/approvals` and `/audit`.
- `commercial_close_packet`: Close Packet projection from Commercial Offer Studio with primary ask, one-page order, checkout gates, mutual action plan, buyer commitments and evidence requirements.
- Commercial close and Local Asset Case now show three-year AI rent, local-license anchor and break-even so the demo speaks the same anti-subscription story as Business Case and Offer Studio.
- `deal_readiness`: blockers, next paid step, role acceptance and close checklist for the actual buyer conversation.
- `committee_close_board`: accepted/blocked roles, final procurement question, role-specific send files and blocker-to-scope guidance for the buying committee.
- `objection_router`: presenter-safe responses for size/confusion, AI subscription, security, developer proof, proof forwarding, price-before-proof and after-purchase objections with route, proof file, owner, status and close question.
- Security objection and architect/security handoff now use `rentgen-security-questionnaire.md` from Evidence Bundle when available.
- Proof packet files are priority-ordered so the visible first files include the demo path, security questionnaire, Trust Center, tests, Safe Autopilot and governance proof instead of arbitrary manifest order.
- Buyer Brief sync: `proof_packet.room_map` highlights `buyer-brief.md`, `buyer-room-plan.md` and `buyer-pulse.md`; role handoff starts with Buyer Brief plus Buyer Room Plan, and the proof-forwarding objection points to `buyer-room-plan.md`.
- Role-specific reports from Demo Story are included in the proof packet and recipient handoff: developer/QA, architect/security and director/sponsor each receive their own short report file.
- Evidence Bundle forwarding kit is surfaced in `proof_packet.forwarding_kit`, Meeting Close Receipt and Post-Demo Activation Handoff, and the portal shows the same role notes in Proof Packet, Close Receipt and Activation cards.
- Killer Demo ZIP exposes `X-Killer-Demo-Manifest`, `X-Killer-Demo-Manifest-Sha256` and `X-Killer-Demo-Manifest-Files`; Killer Demo and Evidence Bundle UIs show those values after archive download.
- Killer Demo ZIP includes `VERIFY_ARCHIVE.md` and covers it with `killer-demo-manifest.json`, so the close-room archive carries its own verification checklist.
- `local_asset_case`: finance/security proof that Rentgen is a local 1C evidence asset with optional AI, not endless AI rent.
- `commercial-offer-studio` proof route in `local_asset_case`: opens the procurement dossier and license-model story.
- `customer_can_repeat` and `role_acceptance`: demo-close signals that prove the buyer understood the product in role language.
- `proof_routes`: route allow-list for the UI and evidence packet.

## Buyer Value

1. The client sees one guided demo path instead of a menu of technical reports.
2. Developers get an immediate Test Factory proof instead of a generic sales pitch.
3. Architects and security see trust blockers and caveats early, not hidden until procurement.
4. Directors see the transition from proof to buying motion and post-purchase outcomes.
5. The meeting ends with exportable Markdown/JSON evidence, a SHA-256 bundle manifest and a ZIP proof archive route.
6. Sales or delivery can forward one role-aware proof packet instead of manually explaining which files matter to whom.
7. The presenter sees whether to ask for purchase now, sell a proof sprint, or convert trust/test blockers into paid hardening scope.
8. Finance and security get a concise asset-vs-subscription argument backed by Business Case, Trust Center, Productization and Evidence Bundle routes.
9. The presenter can verify repeat-back and role acceptance before ending the meeting.
10. The first visible block tells a new buyer where to click, what to say in 30 seconds and how each role should enter the product.
11. The close is explicit: buyer sees whether the ask is enterprise purchase, paid pilot, proof sprint or hardening, plus approval/audit/evidence checkout gates.
12. The final screen can show the buying committee state: who accepted proof, who is blocked, which files each role receives and what question turns the meeting into a paid next step.
13. The presenter answers common objections from one panel instead of hunting across Board Pack, Demo Command Center, Trust Center and Evidence Bundle.
14. Security receives a concrete questionnaire file in the proof packet, not only a route name.
15. The presenter sees the highest-value proof files first, with file cards linked back to their product routes.
16. Role buyers can leave with their own file, not a generic archive they must interpret later.
17. Customer-specific AI-rent assumptions stay consistent with Business Case, Board Pack and Evidence Bundle instead of reverting to demo defaults.
18. The first proof-packet files are a buyer-readable room map and room plan, so the handoff does not start as a raw technical archive.
19. The close-room handoff can point to Evidence Bundle forwarding notes, so sending role packets after the demo does not become manual copywriting.
20. The presenter sees forwarding notes while closing the meeting and while opening activation, not only inside exported JSON.
21. Procurement can record the close-room ZIP hash and the exact `killer-demo-manifest.json` hash from response headers.
22. The close-room ZIP explains its own verification order before role packets or activation files are forwarded.

## Caveats

- Killer Demo Path orchestrates implemented proof surfaces; deep reports remain the source of truth.
- Customer-specific acceptance data is still required before generated tests become final release gates.
- If Trust Center or Test Factory is risky, the path intentionally leads with that risk instead of hiding it.

## Verification

- `python -m py_compile src/services/rentgen/killer_demo_path.py src/api/killer_demo_api.py src/services/rentgen/evidence_bundle.py src/api/evidence_bundle_api.py src/app/routers.py`
- `python -m pytest tests/unit/test_killer_demo_path.py tests/unit/test_commercial_offer_studio.py tests/unit/test_evidence_bundle.py -q`
- Health regression ensures `/health` does not call the deep Killer Demo/Evidence Bundle build path.
- API smoke with `monthly_ai_subscription_cost=200000` returns `7 200 000 RUB` in Killer Demo commercial close and local asset case.
