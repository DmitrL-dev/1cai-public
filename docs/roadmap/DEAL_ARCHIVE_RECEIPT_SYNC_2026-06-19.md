# Deal Archive Receipt Sync - 2026-06-19

## Why

Evidence Bundle, Killer Demo, Launch Room and Home now know about the dual-archive acceptance receipt.
The paid ask also needed the same requirement, otherwise the commercial close packet could ask for purchase
without naming the procurement file that records both ZIP hashes.

## Implemented

1. Commercial Offer Studio:
   - adds `Archive Acceptance Receipt` to `procurement_dossier.procurement_pack`;
   - adds `Archive Acceptance Receipt` to `close_packet.evidence_requirements`;
   - exports close evidence requirements in markdown.

2. Board Pack:
   - preserves the offer-provided receipt requirement;
   - adds it as a fallback when an older commercial close packet does not include it;
   - exports evidence requirements in board markdown.

## Buyer Impact

The commercial and board-level close now say exactly what procurement needs before signature:

- Evidence Bundle ZIP;
- linked Killer Demo ZIP;
- `archive-acceptance-receipt.md` recording both archive hashes and file boundaries.

## Verification

- `tests/unit/test_commercial_offer_studio.py`;
- `tests/unit/test_board_pack.py`.
