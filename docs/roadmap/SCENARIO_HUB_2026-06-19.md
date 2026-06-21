# Scenario Hub v1

Date: 2026-06-19.

Scenario Hub is the pain-led buyer gallery for 1C Rentgen. It exists so a first-time customer does not see a large product surface as a monster: they start from a recognizable 1C pain, then follow a proof route.

## Implemented

- Backend service: `src/services/rentgen/scenario_hub.py`
- API: `POST /api/v1/scenario-hub/build`
- Health: `GET /api/v1/scenario-hub/health`
- UI: `/scenario-hub`
- Navigation: sidebar and executive cockpit fast entry
- Evidence Bundle flag: `include_scenario_hub` enabled by default
- Bundle artifact: `scenario-hub.json` and `scenario-hub.md`
- Health is fast-pulse based; `POST /build` remains the proof-complete scenario gallery artifact.
- Buyer Brief Bridge: `scenario_room_bridge` carries the first-minute room map into the pain gallery before recommended path and scenario cards.

## Scenario Set

- Release go/no-go
- LEFT JOIN field without `ЕстьNULL` / `ЕСТЬ NULL` guard
- Change blast radius
- Architecture map
- Platform or typical update risk
- Extension/update risk
- Rights/RLS trust
- Lock/deadlock after release
- Vendor pre-sale audit
- Local enterprise proof instead of endless AI subscription rent

## Buyer Value

- Developer gets a concrete 1C defect and test path.
- Architect gets platform, extension, architecture and rights proof.
- Director gets money map, go/no-go and local product positioning.
- Vendor gets a pre-sale audit story and work packages.
- Security gets local evidence, productization and hashed export routes.

## Product Links

- Guided Demo exports Scenario Hub markdown.
- Business Case links Scenario Hub in evidence routes.
- Value Packs route each pack through Scenario Hub.
- Vendor Portfolio uses Scenario Hub as the first buyer action.
- Evidence Bundle includes Scenario Hub by default.
- Buyer Brief Bridge keeps Scenario Hub aligned with Home, Guided Demo, Demo Command Center, Launch Room, Board Pack, Offer Studio, Pilot Launchpad and Outcome Ledger.

## Verification

- `python -m py_compile src/services/rentgen/scenario_hub.py src/api/scenario_hub_api.py`
- Health regression ensures `/health` does not call the deep scenario build path.
- `python -m pytest tests/unit/test_scenario_hub.py -q`
- `npm run build`
