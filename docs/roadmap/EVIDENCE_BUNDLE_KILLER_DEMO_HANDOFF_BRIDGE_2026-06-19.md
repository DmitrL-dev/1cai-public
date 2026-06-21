# Evidence Bundle Killer Demo Handoff Bridge - 2026-06-19

## Why

Evidence Bundle is the procurement source-of-truth archive. Killer Demo ZIP is the live close-room archive.

Before this pass, post-demo artifacts such as `MEETING_CLOSE_RECEIPT.md` and `POST_DEMO_ACTIVATION_HANDOFF.md`
were strong in Killer Demo, Launch Room and first-screen purchase flow, but Evidence Bundle could still feel like a
separate archive with no explicit handoff to the close-room ZIP.

## Implemented

1. Added `procurement_handoff.killer_demo_handoff`:
   - route: `/killer-demo`;
   - endpoint: `/api/v1/killer-demo/archive`;
   - archive filename: `<bundle_id>-killer-demo-archive.zip`;
   - hash header: `X-Killer-Demo-Archive-Sha256`;
   - open-first file: `OPEN_FIRST_KILLER_DEMO.md`;
   - post-demo files: `MEETING_CLOSE_RECEIPT.md/.json` and `POST_DEMO_ACTIVATION_HANDOFF.md/.json`;
   - role overlays for director, architect, security/procurement and developer/QA.

2. Added the bridge to:
   - `procurement-handoff.md`;
   - `OPEN_FIRST.md`;
   - Evidence Archive `README.md`;
   - Evidence Bundle portal handoff panel.

3. Preserved archive truth:
   - the ordinary Evidence Bundle ZIP still contains source evidence and procurement handoff files;
   - post-demo overlay files stay in the linked Killer Demo ZIP;
   - tests assert those overlay filenames are not emitted as standalone files in the Evidence Archive.

## Buyer Impact

The buyer can now use one chain without guessing:

1. Open Evidence Bundle ZIP for procurement evidence and required-file completeness.
2. Open linked Killer Demo ZIP for live-demo close artifacts.
3. Record both archive hashes in one intake/procurement ticket.
4. Send role-specific overlay files after the meeting without searching the wrong archive.

## Verification

- `tests/unit/test_evidence_bundle.py` checks the bridge shape, markdown, OPEN_FIRST, README and archive file boundary.
- Frontend build checks the typed portal panel.
