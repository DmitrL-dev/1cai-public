# Dual Archive Verification Packet - 2026-06-20

## What Changed

- Added `POST /api/v1/evidence-bundle/archive/verify-dual`.
- The endpoint verifies the Evidence Bundle ZIP and the linked Killer Demo ZIP as one procurement packet.
- The Killer Demo ZIP is built from the same Evidence archive payload used by the Evidence verification, so `X-Evidence-Archive-Sha256` must match the Evidence ZIP hash in the pair.
- The portal Evidence Bundle page now has `Verify Both ZIPs`.
- The UI exposes `Packet JSON` and `Packet MD` downloads for the combined procurement ticket.
- `POST /api/v1/evidence-bundle/archive/verification-packet` returns a small ZIP with the dual packet, both receipts, `OPEN_FIRST_VERIFICATION_PACKET.md` and `hash-table.json`.

## Packet Contract

The response uses `rentgen.dual_archive_verification_packet.v1` and contains:

- overall `pass` / `warn` / `fail` status;
- pair hashes for Evidence ZIP, Killer Demo ZIP and Killer embedded Evidence source hash;
- `same_evidence_archive_hash`, proving whether the two ZIPs belong to the same generated evidence source;
- full Evidence archive verification result and receipt;
- full Killer Demo archive verification result and receipt;
- `dual-archive-verification-packet.md`, a buyer-forwardable Markdown summary.

## Buyer Impact

Procurement no longer needs to reconcile two separate verification cards by hand. One button proves the archive pair, gives security the findings and gives the director/architect a single receipt trail for the close-room handoff.

When the buyer needs a file for the ticket, `Verification Packet ZIP` packages that receipt trail without bundling the two larger archives again.

## Verification

- `python -m py_compile src/api/evidence_bundle_api.py src/api/killer_demo_api.py src/services/rentgen/evidence_bundle.py`
- `pytest tests/unit/test_evidence_bundle.py tests/unit/test_killer_demo_api.py -q`
- `npm run build` in `portal`
