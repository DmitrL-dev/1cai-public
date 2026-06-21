# Open-First Path Backend Contract - 2026-06-20

## What Changed

- `build_buyer_brief` now emits `open_first_path`: four data-driven actions for orient, prove, close and verify.
- Home reads `buyerBrief.open_first_path` when available and keeps only a loading fallback.
- Buyer Room Packet ZIP now includes `open-first-path.json` and `open-first-path.md`.
- `buyer-brief.md` and `OPEN_FIRST_BUYER_ROOM.md` reference the open-first path directly.
- Buyer Room Packet verification now requires the open-first path files, increasing the packet contract to 14 files.
- Evidence Bundle buyer-brief artifact summary and Markdown now include open-first path evidence.

## Buyer Impact

The anti-confusion first path is now a product contract, not just screen layout. A sponsor, developer, architect or procurement reviewer can open the first packet and see the same orient/prove/close/verify route that the portal shows.

## Verification

- `python -m py_compile src/services/rentgen/buyer_brief.py src/api/management_api.py src/services/rentgen/evidence_bundle.py`
- `pytest tests/unit/test_executive_dashboard.py tests/unit/test_evidence_bundle.py -q` -> 14 passed.
- `npm run build` in `portal`
