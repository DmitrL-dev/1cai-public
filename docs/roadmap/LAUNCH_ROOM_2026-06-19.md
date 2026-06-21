# Launch Room v1

Date: 2026-06-19.

## Purpose

Launch Room is the first buyer-facing cockpit over the growing Rentgen surface.
It reduces the "monster product" effect by turning many powerful modules into one path:
orient, prove, trust, approve, adopt, export.

## Implemented

- Backend service: `src/services/rentgen/launch_room.py`
- API: `POST /api/v1/launch-room/build`, `GET /api/v1/launch-room/health`
- UI: `/launch-room`
- Evidence Bundle artifact: `launch-room.json` and `launch-room.md`
- Navigation: top sidebar entry and dashboard fast entry
- Tests: `tests/unit/test_launch_room.py`, Evidence Bundle artifact coverage
- Buyer Journey: Close -> Activate -> Govern -> Realize, with checkout, activation and governance gates.
- Buyer Journey surfaces Outcome acceptance and claim signals: acceptance rows, watch/blocked counts and claim readiness.
- Purchase Spine: first cockpit shows AI/month, three-year AI rent, local-license anchor, break-even, invoice trigger and proof routes.
- Buyer Brief Bridge: first cockpit now carries the same primary motion, role cards, meeting flow, proof readiness and forwardable files as Home/Killer Demo/Evidence Bundle.
- Proof packet starts with `buyer-brief.md` and `buyer-pulse.md`.
- Proof routes now include `/approvals` and `/audit` so the cockpit can answer procurement and security questions without sending the buyer into a maze.

## Product Value

- Next best action keeps the buyer from choosing among too many modules.
- Six-phase path explains what happens in a meeting without hiding deep reports.
- Buyer Journey makes the paid motion visible: board approval, paid activation, governance proof and measurable outcomes are one path.
- Purchase Spine turns the local-license vs AI-rent argument into a first-screen decision aid instead of hiding it in Business Case.
- Buyer Room Bridge turns the first cockpit into a room map: each role sees why they care, which route to open and which file can be forwarded.
- Acceptance/claim badges bring Pilot Launchpad and Outcome Ledger sign-off readiness back to the first cockpit.
- Role switchboard gives developer, director, security and architecture users their first and second click.
- Meeting modes support short rescue, board, security-first and post-purchase conversations.
- Route health keeps risks visible instead of pretending the product is ready when Trust or Outcomes are risky.
- The UI surfaces gate counts directly, so a buyer can see what is ready before asking for price, security or rollout proof.
- Health now includes `purchase_spine_status` and `three_year_ai_rent` so launch checks can assert commercial readiness.
- Health is fast-pulse based: it does not build Trust, Offer, Board, Outcome and Evidence artifacts on liveness checks.

## Caveats

- Launch Room is a cockpit over existing proof surfaces; it is not a replacement for deep reports.
- The current local demo can honestly return `risk` when Trust/Productization caveats are present.
- Signed/offline bundle packaging remains a productization hardening step.
