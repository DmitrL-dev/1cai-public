# Post-Purchase Verification Packet Continuity - 2026-06-20

## What Changed

- Pilot Launchpad now treats `archive-verification-packet.zip` as a Day 0 activation artifact.
- Activation Contract adds a gate for recording `X-Verification-Packet-Sha256`.
- Acceptance Register adds `day0-verification-packet` for security/procurement.
- Pilot Room Bridge and exports include the verification packet next to close receipt and archive acceptance receipt.
- Outcome Ledger carries the same file into outcome room, proof packet, exports and post-purchase proof spine.
- Outcome acceptance fallback creates a Day 0 verification row even when the incoming Pilot Launchpad report is old.
- Pilot Launchpad and Outcome Ledger now expose one-click `Verification Packet ZIP` downloads with local SHA-256 comparison against `X-Verification-Packet-Sha256`.
- The two post-purchase screens now share the same `VerificationPacketControls` portal component used by Home, Launch Room, Killer Demo and Evidence Bundle.
- Outcome Ledger Day 0 proof spine now renders `Verification Packet ZIP` as a separate hash-control with filename, hash header and Day 30 check.

## Contract

- File: `archive-verification-packet.zip`
- Endpoint: `POST /api/v1/evidence-bundle/archive/verification-packet`
- Hash header: `X-Verification-Packet-Sha256`

## Buyer Impact

The proof story no longer ends at the demo. The same verification packet that procurement accepts after the close room becomes the Day 0 baseline for pilot activation and the Day 30 evidence needed before claiming rollout value.

## Verification

- `python -m py_compile src/services/rentgen/pilot_launchpad.py src/services/rentgen/outcome_ledger.py`
- `pytest tests/unit/test_pilot_launchpad.py tests/unit/test_outcome_ledger.py -q`
- `npm run build` in `portal`
