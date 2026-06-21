# Demo Command Center v1

Date: 2026-06-19.

Demo Command Center is the live presenter cockpit for 1C Rentgen. It turns the buyer-facing surfaces into a timed meeting route: what to open, what to say, how to pivot by role, how to recover when the buyer changes direction, and how to close with artifacts.

## Implemented

- Backend service: `src/services/rentgen/demo_command_center.py`
- API: `POST /api/v1/demo-command-center/build`
- Health: `GET /api/v1/demo-command-center/health`
- UI: `/demo-command-center`
- Navigation: first sidebar item and executive cockpit fast entry
- Evidence Bundle flag: `include_demo_command_center` enabled by default
- Bundle artifact: `demo-command-center.json` and `demo-command-center.md`
- Health is fast-pulse based; `POST /build` remains the proof-complete live meeting artifact.
- Buyer Brief Bridge: `demo_room_bridge` carries the first-minute room map into the live presenter screen before timed stages.

## Buyer Meeting Outputs

- Live stages under 8 minutes
- Role pivots for developer, architect, director, security and vendor
- Before/during/close checklist
- Objection responses with proof routes
- Proof asset list
- Recovery cards for missing data, security jumps, developer skepticism and shortened meetings
- `demo_room_bridge`: Buyer Brief source/status, primary motion, presenter opening, role cards, proof readiness, meeting flow, first files and close question
- `exports`: starts with `buyer-brief.md` and `buyer-pulse.md`, then demo/proof artifacts

## Product Links

- Guided Demo, Scenario Hub and Pilot Launchpad export Demo Command Center markdown.
- Business Case links Demo Command Center in evidence routes.
- Vendor Portfolio starts with Demo Command Center, then Scenario Hub and Pilot Launchpad.
- Evidence Bundle includes Demo Command Center by default.

## Verification

- `python -m py_compile src/services/rentgen/demo_command_center.py src/api/demo_command_center_api.py`
- `python -m pytest tests/unit/test_demo_command_center.py -q`
- `python -m pytest tests/unit/test_demo_command_center.py tests/unit/test_outcome_ledger.py tests/unit/test_pilot_launchpad.py tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- Health regression ensures `/health` does not call the deep demo command build path.
