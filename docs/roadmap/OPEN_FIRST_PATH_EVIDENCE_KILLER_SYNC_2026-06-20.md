# Open-First Path Evidence/Killer Sync - 2026-06-20

## What Changed

- Evidence Bundle now materializes `open-first-path.json` and `open-first-path.md` as first-class artifacts.
- Evidence `OPEN_FIRST.md`, README, archive receipt boundaries, procurement required artifacts and role recipient packets now name `open-first-path.md`.
- Killer Demo proof packet selects `open-first-path.md` and ranks it directly after Buyer Brief/Pulse.
- Killer Demo room map now exposes `open_first_path_ready`, filename, route and SHA-256.
- Role handoff packets now start with `open-first-path.md`, then Buyer Brief and Buyer Room Plan.
- Portal Killer Demo shows the open-first path file in the Buyer Room Map proof card.

## Buyer Impact

The first route no longer disappears after the first screen. It travels as a hashable artifact through Evidence Bundle, Killer Demo, role handoffs and the close-room UI, so every stakeholder receives the same "what to open first" sequence.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py src/services/rentgen/killer_demo_path.py`
- `pytest tests/unit/test_evidence_bundle.py tests/unit/test_killer_demo_path.py -q` -> 11 passed.
- `npm run build` in `portal`
