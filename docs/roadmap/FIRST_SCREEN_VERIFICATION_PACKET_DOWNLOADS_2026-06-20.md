# First Screen Verification Packet Downloads - 2026-06-20

## What Changed

- Home procurement handoff now has a manual `Verification Packet ZIP` download action.
- Launch Room now has the same `Verification Packet ZIP` action in its input sidebar.
- Both screens now use the shared `VerificationPacketControls` component rather than local packet mutations.
- Both actions compare the downloaded ZIP SHA-256 with `X-Verification-Packet-Sha256` locally in the browser.
- The actions are click-only and do not make the first buyer screen heavier on initial load.

## Buyer Impact

The first-screen path is no longer just instructional. A sponsor, architect or security reviewer can immediately create the small procurement control ZIP and see whether the local file hash matches the server header.

## Verification

- `npm run build` in `portal`
- Live smoke against `POST /api/v1/evidence-bundle/archive/verification-packet`
