# Procurement Verification Packet ZIP - 2026-06-20

## What Changed

- Added `POST /api/v1/evidence-bundle/archive/verification-packet`.
- The endpoint returns a small ZIP for procurement/security tickets.
- The ZIP does not replace the Evidence Bundle ZIP or Killer Demo ZIP; it records their verification result and receipts.
- The Evidence Bundle portal page now has `Verification Packet ZIP`.
- The portal download UX is shared through `VerificationPacketControls` across Home, Launch Room, Killer Demo, Pilot Launchpad, Outcome Ledger and Evidence Bundle.
- Buyer Pulse, Buyer Brief, Launch Room and Killer Demo now surface `archive-verification-packet.zip` as a purchase-path artifact, proof packet item and post-demo send file.
- Evidence Bundle procurement handoff now names the verification packet as a separate `control_attachments` item with a gate, verification step and recipient packet attachment.

## ZIP Contents

- `OPEN_FIRST_VERIFICATION_PACKET.md`
- `dual-archive-verification-packet.json`
- `dual-archive-verification-packet.md`
- `evidence-archive-verification-receipt.json`
- `evidence-archive-verification-receipt.md`
- `killer-demo-archive-verification-receipt.json`
- `killer-demo-archive-verification-receipt.md`
- `hash-table.json`

## Response Headers

- `X-Archive-Sha256`
- `X-Verification-Packet-Sha256`
- `X-Verification-Packet-Files`
- `X-Dual-Verification-Status`

## Buyer Impact

Security and procurement receive one compact control ZIP to attach next to the two full archives. The packet states whether both archives pass, whether the Killer Demo ZIP references the same Evidence archive hash, and which receipts/hashes should be recorded.

The buyer-facing path now points to the same artifact from the first screen through the close-room receipt and activation handoff, so a sponsor can forward one verification attachment while security records `X-Verification-Packet-Sha256`.

## Verification

- `python -m py_compile src/api/evidence_bundle_api.py src/api/killer_demo_api.py src/services/rentgen/evidence_bundle.py`
- `pytest tests/unit/test_evidence_bundle.py tests/unit/test_killer_demo_api.py -q`
- `npm run build` in `portal`
- Buyer path sync follow-up: `pytest tests/unit/test_executive_dashboard.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
