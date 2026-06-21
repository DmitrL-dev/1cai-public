# Outcome Ledger - 2026-06-19

## Why This Slice Exists

Board Pack helps the buyer approve a motion. Outcome Ledger answers the next board question: what changes after we buy, who adopts it, when do we measure it, and how does this become rollout or expansion instead of a one-off demo?

It turns the purchase into a 7/30/60/90-day proof loop with role outcomes, success metrics, risk burndown and expansion paths.

## Implemented

- Backend service: `src/services/rentgen/outcome_ledger.py`
- API: `POST /api/v1/outcome-ledger/build`
- Health: `GET /api/v1/outcome-ledger/health`
- Portal: `/outcome-ledger`
- Evidence Bundle artifact: `outcome-ledger.json` and `outcome-ledger.md`
- Navigation: sidebar, home fast entry, Evidence Bundle toggle, route tree.
- Commercial Offer Studio now links to Outcome Ledger in proposal sections, buy-now path and exports.
- Health is fast-pulse based; `POST /build` remains the proof-complete adoption/outcome artifact.
- Buyer Brief Bridge: `outcome_room_bridge` carries the first-minute room map into post-purchase outcome claims before value and adoption sections.

## Report Shape

The report contains:

- `value_realization`: first-year value, AI subscription baseline, manual review/release/risk exposure and proof standard.
- `outcome_tiles`: developer, release, trust, platform and vendor outcomes with owner, route and acceptance.
- `adoption_timeline`: Day 0, Day 1, Day 7, Day 30, Day 60 and Day 90 adoption gates.
- `success_metrics`: measurable business and trust metrics tied to implemented proof routes.
- `role_scorecards`: role-specific adoption triggers from Buyer Concierge and Board Pack.
- `risk_burndown`: Board Pack risks converted into Day 7 and Day 30 actions.
- `expansion_paths`: enterprise rollout, hardening, developer pack and vendor portfolio expansion.
- `acceptance_rollup`: Pilot Launchpad sign-off rows converted into outcome routes, proof files, next owner/window and claim readiness.
- `governance_refresh`: approval, audit, Evidence Bundle and trust gates for Day 7/30/60/90 proof refresh.
- `outcome_room_bridge`: Buyer Brief source/status, primary motion, outcome motion, role cards, proof readiness, meeting flow, first files and outcome question.
- `proof_packet`: Buyer Brief, Buyer Pulse, Outcome Ledger, Board Pack, Pilot Launchpad, Business Case, Trust Center, Governance Proof, Audit and Evidence Bundle artifacts.
- `exports`: starts with `buyer-brief.md` and `buyer-pulse.md`, then outcome/proof artifacts.

## Product Effect

Outcome Ledger makes the sale feel less like a demo and more like an owned program:

1. Director sees measurable value windows.
2. Developer sees real review-saving proof.
3. Security sees risks burned down before rollout claims.
4. Vendor sees expansion and repeatable packages.
5. Evidence Bundle carries the outcome plan with hashes.
6. Governance proof is refreshed before renewal, rollout or hardening claims.
7. Pilot acceptance is no longer stranded in the pilot artifact; each sign-off row becomes a measured outcome or blocker.
8. The post-purchase review reuses the same buyer-room map before claiming value.

## Verification

- `python -m py_compile src/services/rentgen/outcome_ledger.py src/api/outcome_ledger_api.py src/services/rentgen/evidence_bundle.py`
- `python -m pytest tests/unit/test_outcome_ledger.py tests/unit/test_commercial_offer_studio.py tests/unit/test_evidence_bundle.py -q`
- `python -m pytest tests/unit/test_outcome_ledger.py tests/unit/test_pilot_launchpad.py tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- Wide regression: 53 passed, 1 existing pytest-asyncio warning.
- `npm run build`
- Health regression ensures `/health` does not call the deep outcome build path.
- Live smoke:
  - unauth `POST /api/v1/outcome-ledger/build` returns 401
  - auth build returns 200 with `outcome_room_bridge`, governance gates/windows, `/killer-demo`, `/approvals`, `/audit` and `Outcome Room Bridge`/`Governance Refresh` markdown
  - Evidence Bundle returns `outcome-ledger` artifact and `outcome-ledger.md`
  - UI `/outcome-ledger` returns 200
