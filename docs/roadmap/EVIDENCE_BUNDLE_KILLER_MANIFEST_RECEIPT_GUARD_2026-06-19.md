# Evidence Bundle Killer Manifest Receipt Guard - 2026-06-19

## Why

Outcome Ledger now uses `killer-demo-manifest.json` as part of the Day 0 post-purchase proof spine.
Evidence Bundle already carried the linked Killer Demo archive boundary, but the archive README needed to name
the linked manifest explicitly so procurement has one obvious hash-verification file to record.

## Implemented

- Evidence Archive `README.md` now prints the linked Killer Demo ZIP manifest filename.
- Evidence Bundle tests assert:
  - `procurement_handoff.killer_demo_handoff.manifest_file == "killer-demo-manifest.json"`;
  - the linked archive boundary contains `killer-demo-manifest.json`;
  - `archive-acceptance-receipt` keeps the manifest file for the linked archive;
  - the generated Evidence ZIP README names `killer-demo-manifest.json`.

## Buyer Impact

Procurement can record three things without guessing:

- Evidence Bundle ZIP hash;
- linked Killer Demo ZIP hash;
- `killer-demo-manifest.json` as the close-room archive manifest.

That keeps the Day 0 close packet, activation handoff and Day 30 Outcome Ledger claims on the same evidence trail.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py`
- `pytest tests/unit/test_evidence_bundle.py -q`
