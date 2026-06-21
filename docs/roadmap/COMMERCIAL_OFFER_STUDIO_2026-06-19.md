# Commercial Offer Studio - 2026-06-19

## Why This Slice Exists

The product now has role demos, pilot planning, enterprise trust and evidence exports. The next buyer question is commercial: what exactly do we buy, how is the price anchored, and how do we avoid another endless AI subscription?

Commercial Offer Studio turns proof into a buyable package set:

- 24-hour proof sprint;
- 30-day local license pilot;
- enterprise local license;
- platform and trust hardening pack;
- vendor portfolio rollout.

## Implemented

- Backend service: `src/services/rentgen/commercial_offer_studio.py`
- API: `POST /api/v1/commercial-offer-studio/build`
- Health: `GET /api/v1/commercial-offer-studio/health`
- Portal: `/commercial-offer-studio`
- Evidence Bundle artifact: `commercial-offer-studio.json` and `commercial-offer-studio.md`
- Navigation: sidebar, home fast entry, Evidence Bundle toggle, route allow-lists in demo/pilot/scenario/guided/business/vendor/trust pages.
- Health is fast-pulse based; `POST /build` remains the proof-complete offer/procurement artifact.
- Buyer Brief Bridge: `offer_room_bridge` carries the first-minute room map into the commercial screen before pricing and dossier sections.

## Report Shape

The report contains:

- `offer_room_bridge`: Buyer Brief source/status, primary motion, recommended purchase, role cards, proof readiness, meeting flow, first files and close question.
- `offers`: proof sprint, local pilot, enterprise license, hardening pack, vendor rollout.
- `pricing_ladder`: value-based anchors derived from Business Case visible value and AI subscription displacement.
- `procurement_dossier`: recommended purchase, full subscription escape plan, local-vs-AI-rent line, license models, procurement artifacts, approval matrix and red lines.
- `close_packet.one_page_order`: carries three-year AI rent, local-license anchor and break-even line from Business Case.
- `close_packet`: primary paid ask, one-page order, mutual action plan, buyer commitments, evidence requirements, approval/audit/evidence checkout gates and close script.
- `stakeholder_closers`: developer, architect, director, security and vendor close lines.
- `deal_risks`: procurement, finance, pilot and productization risks with mitigation routes.
- `proposal_sections`: executive offer, technical proof, enterprise trust, pilot route and proof bundle.
- `buy_now_path`: pick offer, confirm trust, attach proof, book pilot.
- `exports`: starts with `buyer-brief.md` and `buyer-pulse.md`, then the commercial and downstream proof artifacts.

## Product Effect

This gives the seller and buyer a concrete answer after the demo:

1. Pick the paid package.
2. Confirm trust artifacts.
3. Attach hashed proof.
4. Book the pilot or license rollout.
5. Check approval records, audit-chain validity and proof archive before asking for purchase.
6. Send finance/security/procurement one local-product dossier instead of a generic AI subscription story.
7. Keep the role map, proof files and meeting flow visible before anyone sees the price sheet.

The commercial story stays grounded in implemented evidence instead of becoming an abstract price sheet.

## Verification

- `python -m py_compile` for service/API/evidence integration.
- `python -m pytest tests/unit/test_commercial_offer_studio.py -q`
- `python -m pytest tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- Health regression ensures `/health` does not call the deep offer build path.
- Live smoke: `POST /api/v1/commercial-offer-studio/build` returns `offer_room_bridge`, `close_packet`, checkout gates, `/killer-demo`, `/approvals` and `/audit` proof routes.
- Evidence Bundle regression was extended to require `commercial-offer-studio` artifact and markdown manifest entry.

Full regression should include the commercial, trust, evidence, demo, pilot, scenario, guided and business tests plus `npm run build`.
