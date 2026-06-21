# Evidence Bundle Buyer Brief

Date: 2026-06-19.

Home Buyer Brief made the first minute clearer in the live product. This slice makes that first-minute room map portable and hash-verifiable inside Evidence Bundle.

## Implemented

- New `buyer-brief` artifact in `build_evidence_bundle`.
- ZIP/manifest files: `buyer-brief.json` and `buyer-brief.md`.
- `buyer-brief.md` is a required procurement file.
- Director, architect/security, security/procurement and developer/QA recipient packets include `buyer-brief.md`.
- OPEN_FIRST and archive contents surface Buyer Brief through the required-file and role-packet flow.
- `/evidence-bundle` UI prioritizes and highlights `buyer-brief.md` before Buyer Pulse in send-ready role packets.
- Buyer Concierge now consumes Buyer Brief as `concierge_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md`, and shows the room map before Purchase Router.
- Business Case now consumes Buyer Brief as `business_room_bridge` and shows the role/proof/meeting map before money levers and subscription escape.
- Value Packs now consumes Buyer Brief as `value_room_bridge` and shows the role/proof/meeting map before package cards.
- Vendor Portfolio now consumes Buyer Brief as `vendor_room_bridge` and shows the role/proof/meeting map before Deal Board.
- Enterprise Trust Center now consumes Buyer Brief as `trust_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md`, and shows the role/proof/meeting map before Security Questionnaire.
- Killer Demo proof packet now consumes the same Buyer Brief as `room_map`, places `buyer-brief.md` and `buyer-pulse.md` first, and starts role handoff with `buyer-brief.md`.
- Launch Room now consumes Buyer Brief as `buyer_room_bridge`, starts its proof packet with `buyer-brief.md`/`buyer-pulse.md`, and shows the room map before cockpit phases.
- Board Pack now consumes Buyer Brief as `board_room_bridge`, starts its proof packet with `buyer-brief.md`/`buyer-pulse.md`, and shows the board-room map before board snapshot and close packet.
- Commercial Offer Studio now consumes Buyer Brief as `offer_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md`, and shows the role/proof/meeting map before procurement dossier and pricing.
- Pilot Launchpad now consumes Buyer Brief as `pilot_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md`, and shows the role/proof/meeting map before paid activation.
- Outcome Ledger now consumes Buyer Brief as `outcome_room_bridge`, starts proof packet/exports with `buyer-brief.md`/`buyer-pulse.md`, and shows the role/proof/meeting map before value claims.
- Demo Command Center now consumes Buyer Brief as `demo_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md`, and shows the role/proof/meeting map before live stages.
- Guided Demo now consumes Buyer Brief as `guided_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md`, and shows the role/proof/meeting map before the guided buyer route.
- Scenario Hub now consumes Buyer Brief as `scenario_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md`, and shows the role/proof/meeting map before the pain gallery and recommended path.

## Buyer Effect

- The forwarded ZIP now starts with a readable room map: primary motion, role cards, proof readiness and meeting flow.
- Procurement can verify that the same first-minute guidance shown on Home was generated into JSON/Markdown and covered by SHA-256 manifest entries.
- Security sees Audit/SIEM and Trust Center proof readiness before opening deep artifacts.
- The first role/pain screen now uses the same room map before purchase routing.
- Director value review now starts from the same room map before AI-rent and local-license math.
- Role/package selection now starts from the same room map before the customer sees the catalog.
- Partner audit review now starts from the same room map before work packages and commercial motion.
- Security/procurement review now starts from the same room map before the questionnaire and controls.
- The live demo and the downloaded ZIP now speak the same first-minute room-map language.
- The first launch cockpit, board packet, live demo and downloaded ZIP now speak the same first-minute room-map language.
- Commercial proposal review now starts with role-specific proof and forwardable files before price discussion.
- Paid pilot activation now reuses the same room map before owner/date/gates are agreed.
- Post-purchase value review now reuses the same room map before measured outcome claims.
- Live presenters now start from the same room map before timed demo stages.
- Guided walkthroughs now start from the same room map before the buyer route.
- Pain-led scenario discovery now starts from the same room map before the customer sees the larger catalog.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py tests/unit/test_evidence_bundle.py`
- `python -m pytest tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- API/archive smoke with `monthly_ai_subscription_cost=200000` should include `buyer-brief.json`, `buyer-brief.md`, five role cards, four proof readiness items and `7 200 000 RUB`.
