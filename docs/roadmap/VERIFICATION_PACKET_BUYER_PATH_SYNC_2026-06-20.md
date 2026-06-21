# Verification Packet Buyer Path Sync - 2026-06-20

## What Changed

- Buyer Pulse and Buyer Brief now expose `archive-verification-packet.zip` as a purchase-path artifact.
- Home renders the verification packet next to close receipt, activation handoff and archive acceptance receipt.
- Home now also renders a procurement handoff open order with Evidence ZIP, Killer Demo ZIP, Verification Packet ZIP and required hash headers.
- Launch Room includes the packet in purchase spine evidence files and proof packet exports.
- Killer Demo proof packet exposes `verification_packet` with endpoint, filename, hash header, open-first file and contents.
- Killer Demo page now downloads `Verification Packet ZIP` directly from the close-room sidebar using the same demo inputs.
- Meeting Close Receipt and Post-Demo Activation Handoff include the verification packet in send/proof files.
- Commercial close evidence requirements now list `Verification Packet ZIP` after Killer Demo ZIP, close receipt and activation handoff.
- Evidence Bundle procurement handoff now exposes `verification_packet`, `control_attachments`, a pair-level verification gate/step and recipient packet attachments without placing the control ZIP inside the Evidence Archive.
- Pilot Launchpad and Outcome Ledger now carry the same packet into Day 0 activation, acceptance register, post-purchase proof spine and Day 30 outcome measurement.

## Contract

- File: `archive-verification-packet.zip`
- Endpoint: `POST /api/v1/evidence-bundle/archive/verification-packet`
- Hash header: `X-Verification-Packet-Sha256`
- Open first: `OPEN_FIRST_VERIFICATION_PACKET.md`

## Buyer Impact

The first screen, live demo close room and procurement handoff now describe the same control artifact. A sponsor sees one attachment to forward; security sees exact hashes and receipts; architecture sees that the Evidence and Killer Demo archives are checked as a pair instead of trusted as screenshots.

The archive boundary stays explicit: Evidence Bundle ZIP carries source evidence and role packets; Killer Demo ZIP carries close-room overlays; Verification Packet ZIP carries the receipts and hash table proving both archives as a pair.

## Verification

- `python -m py_compile src/services/rentgen/buyer_pulse.py src/services/rentgen/buyer_brief.py src/services/rentgen/launch_room.py src/services/rentgen/killer_demo_path.py`
- `pytest tests/unit/test_executive_dashboard.py tests/unit/test_launch_room.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q`
- `npm run build` in `portal`
