# Pilot Launchpad v1

Date: 2026-06-19.

Pilot Launchpad is the sales-to-adoption close layer for 1C Rentgen. Scenario Hub answers "what pain do I recognize?" and Guided Demo answers "how do I see proof?". Pilot Launchpad answers "what do we buy or pilot tomorrow, who accepts it, and what artifacts go to procurement?".

## Implemented

- Backend service: `src/services/rentgen/pilot_launchpad.py`
- API: `POST /api/v1/pilot-launchpad/build`
- Health: `GET /api/v1/pilot-launchpad/health`
- UI: `/pilot-launchpad`
- Navigation: sidebar and executive cockpit fast entry
- Evidence Bundle flag: `include_pilot_launchpad` enabled by default
- Bundle artifact: `pilot-launchpad.json` and `pilot-launchpad.md`
- Health is fast-pulse based; `POST /build` remains the proof-complete pilot artifact.
- Buyer Brief Bridge: `pilot_room_bridge` carries the first-minute room map into paid activation before pilot offers and acceptance sections.

## Buyer Outputs

- `pilot_room_bridge`: Buyer Brief source/status, primary motion, activation motion, role cards, proof readiness, meeting flow, first files and activation question
- 24-hour buyer proof
- 7-day release pilot
- 30-day local license pilot
- Vendor portfolio rollout
- Day plan for 0-24 hours, days 2-7 and days 8-30
- Acceptance matrix for developer, architect, director, security, operations and vendor roles
- `acceptance_register`: Day 0/1/7/30 sign-off rows with owner, decision, evidence route/file, status, blocker and next action
- Procurement pack for finance, security, governance, audit, architecture board, release board and vendor owner
- `activation_contract`: selected paid offer, primary ask, invoice trigger, Day 0/7/30 milestones, buyer commitments and approval/audit/evidence activation gates
- `proof_routes`: includes `/approvals`, `/audit`, `/evidence-bundle`, Trust Center and the selected pilot proof route
- `exports`: starts with `buyer-brief.md` and `buyer-pulse.md`, then pilot/deal/trust proof files

## Product Links

- Scenario Hub and Guided Demo export Pilot Launchpad markdown.
- Business Case links Pilot Launchpad in evidence routes.
- Vendor Portfolio uses Scenario Hub first, then Pilot Launchpad as the conversion action.
- Evidence Bundle includes Pilot Launchpad by default.

## Verification

- `python -m py_compile src/services/rentgen/pilot_launchpad.py src/api/pilot_launchpad_api.py`
- `python -m pytest tests/unit/test_pilot_launchpad.py -q`
- `python -m pytest tests/unit/test_pilot_launchpad.py tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- Health regression ensures `/health` does not call the deep pilot build path.
- Live smoke: authenticated `POST /api/v1/pilot-launchpad/build` returns `pilot_room_bridge`, activation readiness, 5 activation gates, acceptance register rows, `/killer-demo`, `/approvals`, `/audit` and `Pilot Room Bridge`/`Activation Contract`/`Acceptance Register` markdown; UI `/pilot-launchpad` returns 200.
