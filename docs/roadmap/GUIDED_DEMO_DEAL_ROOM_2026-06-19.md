# Guided Demo / Deal Room v1

Date: 2026-06-19.

## Purpose

Guided Demo is the anti-confusion layer for 1C Rentgen. It turns the product from a set of powerful surfaces into one buyer route:

- start from a clear cockpit, not a menu maze;
- prove developer value with a concrete 1C defect path;
- prove architect value with topology, blast radius and platform risk;
- prove director value with Business Case and objections;
- prove enterprise trust with Productization, SBOM/offline readiness and Evidence Bundle artifacts.

## Live Surface

- UI: `/guided-demo`
- API: `POST /api/v1/guided-demo/build`
- Health: `GET /api/v1/guided-demo/health`
- Evidence Bundle flag: `include_guided_demo` enabled by default
- Markdown export: `rentgen-guided-demo.md`
- Health is fast-pulse based; `POST /build` remains the proof-complete guided demo artifact.
- Buyer Brief Bridge: `guided_room_bridge` carries the first-minute room map into the guided walkthrough before opening proof and buyer route.

## Buyer Route

1. Orientation: score, roles, top risks and first actions.
2. Developer proof: change impact plus Query Surgeon LEFT JOIN/NULL guard story.
3. Architect proof: architecture, metadata, blast radius and update risk.
4. Platform proof: Platform Doctor and productization readiness.
5. Director proof: Business Case money map and objections.
6. Vendor proof: audit/work-package route for partners.
7. Evidence close: hashed JSON/Markdown artifacts.
8. Productization close: SBOM, offline manifest, archive and verification path.
9. Buyer Brief bridge: primary motion, guided path, role cards, proof readiness, meeting flow and first files.

## Product Contract

Guided Demo does not invent value. It composes existing implemented reports:

- Executive Dashboard and Demo Story
- Business Case
- Value Packs
- Vendor Portfolio
- Productization Readiness
- Evidence Bundle

The report includes decision/status, total minutes, role paths, objection cards, 24h/7d/30d close plan, `guided_room_bridge`, export list, caveats and markdown.

Exports now start with `buyer-brief.md` and `buyer-pulse.md` so the guided route can be forwarded with the same buyer-room context as the rest of the product.

## Why It Matters

This is the layer that prevents the buyer from saying "I do not understand what this product is." The product now has a single first demo route that can make a developer care about a concrete defect, an architect care about system risk, a director care about money and a security/CIO owner care about local artifacts.

## Verification

- `python -m py_compile src/services/rentgen/guided_demo.py src/api/guided_demo_api.py`
- `python -m pytest tests/unit/test_guided_demo.py -q`
- `python -m pytest tests/unit/test_guided_demo.py tests/unit/test_demo_command_center.py tests/unit/test_outcome_ledger.py tests/unit/test_pilot_launchpad.py tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- Health regression ensures `/health` does not call the deep guided demo build path.
