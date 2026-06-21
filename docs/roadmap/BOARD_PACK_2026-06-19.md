# Board Pack - 2026-06-19

## Why This Slice Exists

Buyer Concierge reduces first-click confusion, Enterprise Trust Center answers security, and Commercial Offer Studio gives packages. Board Pack compresses those routes into one board-level decision artifact: what to approve, why now, what it costs, what can block it, and which proof files go into the packet.

This closes a product gap for directors, CIOs, architects, vendors and procurement: they do not need to understand every module before seeing a buying motion.

## Implemented

- Backend service: `src/services/rentgen/board_pack.py`
- API: `POST /api/v1/board-pack/build`
- Health: `GET /api/v1/board-pack/health`
- Portal: `/board-pack`
- Evidence Bundle artifact: `board-pack.json` and `board-pack.md`
- Navigation: sidebar, home fast entry, Evidence Bundle toggle, route tree.
- Commercial Offer Studio now links to Board Pack in proposal sections, buy-now path and exports.
- Health is fast-pulse based; `POST /build` remains the proof-complete board artifact.
- Buyer Brief Bridge: board packet now carries primary motion, committee role cards, proof readiness, meeting flow and buyer-forwardable files.
- Proof packet starts with `buyer-brief.md` and `buyer-pulse.md`.

## Report Shape

The report contains:

- `board_snapshot`: one-line buying story, value anchor, AI-rent baseline, trust position and recommended motion.
- `board_room_bridge`: board-room map over Buyer Brief with primary motion, role cards, proof readiness, meeting flow, files and final board question.
- `board_snapshot` and `board_close_packet.one_page_order` now carry three-year AI rent, local-license anchor and break-even from Commercial Offer/Business Case.
- `decision_brief`: six board questions with owner and proof route.
- `procurement question`: Board Pack now surfaces the Offer Studio procurement dossier as a board-level approval item.
- `signature checkout question`: Board Pack surfaces approval, audit, evidence archive and trust gates before signature.
- `committee_map`: role-specific concerns, proof routes and close lines.
- `recommended_offer`: proof sprint, local pilot, enterprise license or hardening pack depending on trust and pilot readiness.
- `risk_to_decision`: Trust Center and deal risks converted into board decisions.
- `proof_packet`: Board Pack, Concierge, Offer Studio, Trust Center, Business Case, Governance Proof, Audit and Evidence Bundle artifacts.
- `board_close_packet`: board-facing paid ask, one-page order, checkout gates, buyer commitments, evidence requirements and close script.
- `next_72_hours`: owner, route and output for the immediate paid next step.
- `objection_answers`: standard board objections routed to implemented proof.
- `board_room_script`: eight-minute meeting flow.

## Product Effect

Board Pack makes the product easier to buy:

1. The director sees a motion instead of a menu.
2. Security sees caveats before rollout pressure.
3. Finance sees local product value separate from AI credits.
4. Architects and developers see their proof routes represented.
5. The seller can export one board packet with hashes.
6. Procurement sees approval/audit/evidence checkout gates before signing, not after the quote.
7. The board starts from the same first-minute room map as Home, Launch Room, Killer Demo and Evidence Bundle.

## Verification

- `python -m py_compile src/services/rentgen/board_pack.py src/api/board_pack_api.py src/services/rentgen/evidence_bundle.py`
- `python -m pytest tests/unit/test_board_pack.py tests/unit/test_commercial_offer_studio.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- Health regression ensures `/health` does not call the deep board build path.
- Live smoke:
  - unauth `POST /api/v1/board-pack/build` returns 401
  - auth build returns 200 with close readiness, 4 checkout gates, `/approvals`, `/audit` and `Board Close Packet` markdown
  - Evidence Bundle returns `board-pack` artifact and `board-pack.md`
  - UI `/board-pack` returns 200
