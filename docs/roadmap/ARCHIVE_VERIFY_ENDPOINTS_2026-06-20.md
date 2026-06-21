# Archive Verify Endpoints - 2026-06-20

## What Changed

- Evidence Bundle now has `POST /api/v1/evidence-bundle/archive/verify`.
- Killer Demo now has `POST /api/v1/killer-demo/archive/verify`.
- Both endpoints build the same ZIP as the download route and verify it server-side without extracting files.
- Portal pages `/evidence-bundle` and `/killer-demo` now expose buyer-visible verify buttons and compact pass/warn/fail cards.
- Portal archive downloads also compute browser-side SHA-256 for the downloaded Blob and show whether it matches the archive hash header.
- Verify responses now include `verification_receipt` and `verification_receipt_markdown`, a buyer-forwardable receipt that security/procurement can attach to an intake ticket.
- Evidence Bundle now also has `POST /api/v1/evidence-bundle/archive/verify-dual`, which verifies Evidence ZIP and linked Killer Demo ZIP as one pair.
- Evidence Bundle now has `POST /api/v1/evidence-bundle/archive/verification-packet`, a compact ZIP with the dual packet, both receipts and a hash table.

## Evidence Bundle Verification

The verifier checks:

- required buyer proof files such as `OPEN_FIRST.md`, `VERIFY_ARCHIVE.md`, `bundle.json`, `README.md`, `procurement-handoff.*` and `archive-acceptance-receipt.*`;
- `archive-manifest.json` schema and source manifest digest link;
- every `archive-manifest.json.files[*]` entry exists, with matching SHA-256 and byte size;
- `archive-acceptance-receipt.json` does not claim missing Evidence Archive files.

The response includes `archive_sha256`, checked file count, severity summary, findings, expected download headers and a verification receipt.

## Killer Demo Verification

The verifier checks:

- required close-room files such as `OPEN_FIRST_KILLER_DEMO.md`, `VERIFY_ARCHIVE.md`, `killer-demo.json`, `proof-packet.json`, `MEETING_CLOSE_RECEIPT.*` and `POST_DEMO_ACTIVATION_HANDOFF.*`;
- every `killer-demo-manifest.json.files[*]` overlay entry exists, with matching SHA-256 and byte count;
- role packet filenames listed in `killer-demo-manifest.json`;
- embedded Evidence Bundle verification through the same Evidence verifier when `archive-manifest.json` is present.

The Killer ZIP assembly also syncs the embedded Evidence `archive-manifest.json` when the Killer version of `VERIFY_ARCHIVE.md` replaces the Evidence guide.

## Buyer Impact

The buyer can now press "Verify Evidence ZIP" or "Verify Killer ZIP" in the portal and see the integrity result before forwarding files. This turns the archive from a raw download into a first-party proof artifact that security, architecture, procurement and a director can all record in one ticket.

After a ZIP download, the portal also shows a local Blob hash match/mismatch line, so the presenter can prove the bytes received by the browser match the backend response header.

After verification, the portal exposes `Receipt JSON` and `Receipt MD` downloads. The receipt names the archive hash, decision, expected headers, finding summary, embedded Evidence status and acceptance steps.

The Evidence Bundle page also exposes `Verify Both ZIPs`, returning a `rentgen.dual_archive_verification_packet.v1` response with a combined Markdown/JSON packet and a `same_evidence_archive_hash` check.

The `Verification Packet ZIP` button downloads a small control archive for procurement tickets. It includes `OPEN_FIRST_VERIFICATION_PACKET.md`, dual packet JSON/Markdown, both archive receipts and `hash-table.json`.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py src/api/evidence_bundle_api.py src/api/killer_demo_api.py`
- `pytest tests/unit/test_evidence_bundle.py tests/unit/test_killer_demo_api.py -q`
- `npm run build` in `portal`
