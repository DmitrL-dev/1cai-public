# Post-Purchase Open-First Path Continuity - 2026-06-20

## What Changed

- Pilot Launchpad `pilot_room_bridge` now carries `open_first_path` with a safe fallback when Buyer Brief is absent.
- Outcome Ledger `outcome_room_bridge` now carries `open_first_path` with a Day 30 verification-oriented fallback.
- Pilot and Outcome summaries expose `pilot_room_open_first` / `outcome_room_open_first`.
- Portal Pilot Launchpad and Outcome Ledger render the open-first path before role/proof/meeting blocks.
- Pilot and Outcome Markdown exports include the open-first path.
- Both bridges list `open-first-path.md` immediately after the Buyer Room Packet ZIP.

## Buyer Impact

The first route survives after the sale. Day 0 activation and Day 30 outcome claims still start from the same orient/prove/close/verify spine, so the customer does not lose the proof path once the demo turns into adoption.

## Verification

- `python -m py_compile src/services/rentgen/pilot_launchpad.py src/services/rentgen/outcome_ledger.py`
- `pytest tests/unit/test_pilot_launchpad.py tests/unit/test_outcome_ledger.py -q` -> 5 passed.
- `npm run build` in `portal`
