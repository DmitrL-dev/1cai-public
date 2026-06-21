# Buyer Room Plan

Дата: 2026-06-20.

## Зачем

Первый экран уже содержал buyer brief, role cards, purchase path and evidence readiness, but a live demo operator still had to decide which path to open first. This could make the product feel broad before it feels inevitable.

## Что добавлено

- `buyer_room_plan` in `/api/v1/management/buyer-brief`.
- A compact Home `Room plan` block that names:
  - current room mode;
  - role to start with;
  - route to open;
  - proof file;
  - close question;
  - files to send after the demo.
- Evidence Bundle materialization:
  - `buyer-room-plan.json`;
  - `buyer-room-plan.md`;
  - SHA-256 manifest entries;
  - procurement required file;
  - recipient send-files;
  - ZIP, README, OPEN_FIRST and archive acceptance receipt visibility.
- Evidence Bundle UI highlights Buyer Room Plan above procurement handoff with route, proof file, close question, sequence, send files and direct `.md/.json` downloads.
- Killer Demo proof packet sync:
  - `proof_packet.room_map.plan_filename`;
  - prioritized proof file card;
  - role handoff after `buyer-brief.md`;
  - proof-forwarding objection points to `buyer-room-plan.md`.
- Deterministic route priority:
  - blocked evidence -> `/configurations`;
  - high hotspots -> developer path `/change`;
  - red architecture/platform areas -> architect path;
  - purchase ready -> director board pack;
  - review queue -> vendor portfolio;
  - otherwise guided proof route.

## Проверки

- `pytest tests/unit/test_executive_dashboard.py tests/unit/test_evidence_bundle.py tests/unit/test_launch_room.py -q`
- `npm run build` in `portal`
- `python -m py_compile src/services/rentgen/evidence_bundle.py src/services/rentgen/killer_demo_path.py`
- `pytest tests/unit/test_evidence_bundle.py tests/unit/test_killer_demo_path.py -q`

## Buyer Impact

The first screen now answers: "who is in the room, what do I open first, what proof do I show, what do I send, and what close question do I ask?" without forcing a buyer through the full workbench.
