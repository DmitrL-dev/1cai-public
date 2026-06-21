# Evidence Bundle Archive Acceptance Receipt - 2026-06-19

## Why

After a strong demo, procurement still needs a boring, exact answer:

- which ZIP is the evidence archive;
- which ZIP is the close-room archive;
- which HTTP hash header to record;
- which files belong to each archive boundary;
- where `MEETING_CLOSE_RECEIPT.md` and `POST_DEMO_ACTIVATION_HANDOFF.md` come from.

Without that receipt, the product can feel impressive but operationally fuzzy at the moment of purchase.

## Implemented

1. Added `archive_acceptance_receipt` to Evidence Bundle:
   - Evidence Bundle ZIP endpoint, filename, hash header and open-first file;
   - linked Killer Demo ZIP endpoint, filename, hash header and open-first file;
   - explicit contains/excludes boundaries;
   - role overlays from the linked Killer Demo ZIP;
   - three acceptance steps for the procurement ticket.

2. Added generated files to the Evidence Archive:
   - `archive-acceptance-receipt.json`;
   - `archive-acceptance-receipt.md`.

3. Added portal visibility:
   - download button for `archive-acceptance-receipt.md`;
   - Archive Acceptance Receipt panel with both archive boundaries and acceptance steps.

4. Kept archive truth intact:
   - Evidence Archive contains the receipt and source evidence;
   - close-room overlays remain in the linked Killer Demo ZIP;
   - tests assert `MEETING_CLOSE_RECEIPT.md/.json` and `POST_DEMO_ACTIVATION_HANDOFF.md/.json` are not standalone files in the ordinary Evidence Archive.

## Buyer Impact

The buyer can now close the loop in one procurement ticket:

1. Record Evidence Bundle ZIP filename and `X-Archive-Sha256`.
2. Record linked Killer Demo ZIP filename and `X-Killer-Demo-Archive-Sha256`.
3. Forward source evidence and close-room overlays from the correct archive boundary.

This turns "cool demo" into "auditable purchase motion".

## Verification

- `tests/unit/test_evidence_bundle.py` covers report fields, markdown, ZIP contents and archive boundary exclusions.
- `npm run build` validates the typed portal panel.
