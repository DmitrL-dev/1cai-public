# Killer Demo One-Action Archive - 2026-06-19

## Why

Killer Demo could show a proof packet and Evidence Bundle could export a ZIP, but the presenter still needed separate actions to hand over the current demo markdown, proof packet JSON and evidence archive. That weakens the close: after a strong demo the buyer should receive one archive immediately.

## Implemented

- Added `POST /api/v1/killer-demo/archive`.
- The endpoint composes the same Killer Demo report and Evidence Bundle as `/build`.
- `proof_packet.killer_archive` now exposes endpoint, filename, open-first file, demo manifest, response hash headers and role packet filenames.
- Commercial Close Packet now prepends `Killer Demo ZIP` to evidence requirements so the paid ask points to the same one-action archive the presenter downloads.
- The endpoint starts from the Evidence Bundle ZIP and adds current-demo files into the same archive:
  - `README-KILLER-DEMO.md`
  - `OPEN_FIRST_KILLER_DEMO.md`
  - `rentgen-killer-demo-path.md`
  - `killer-demo.json`
  - `proof-packet.json`
  - `MEETING_CLOSE_RECEIPT.md`
  - `meeting-close-receipt.json`
  - `POST_DEMO_ACTIVATION_HANDOFF.md`
  - `post-demo-activation-handoff.json`
  - `killer-demo-manifest.json`
  - `ROLE_DEVELOPER_QA.md`
  - `ROLE_ARCHITECT_SECURITY.md`
  - `ROLE_DIRECTOR_SPONSOR.md`
- Response headers include:
  - `X-Archive-Sha256`
  - `X-Archive-Files`
  - `X-Evidence-Archive-Sha256`
- `OPEN_FIRST_KILLER_DEMO.md` is now a concise archive entry point with open order, procurement readiness and role packet index instead of a full report dump.
- `killer-demo-manifest.json` now includes role packet metadata plus SHA-256 checks for every added demo overlay file.
- `proof_packet.handoff[*].role_packet` names the exact `ROLE_*.md` file for each recipient, using the same filename helper as the archive builder.
- `proof_packet.handoff[*].available_files`, `missing_files` and `availability_status` now state what is really present in the current build/profile; `killer-demo.md` is resolved to `rentgen-killer-demo-path.md` when the current demo export covers it.
- `proof_packet.role_packet_rollup` aggregates ready/partial/missing recipient packets, missing file count and missing file names for the whole archive.
- `proof_packet.close_receipt` and `meeting_close_receipt` add the post-demo accepted-role/blocker/next-paid-step artifact to API, portal and ZIP.
- `proof_packet.activation_handoff` and `post_demo_activation_handoff` add the paid-start route chain, gates, invoice trigger, Day 7 proof and Day 30 acceptance path to API, portal and ZIP.
- `ROLE_*.md` files split `Available In This Archive` from `Not Included In This Build`, so buyer-profile archives do not pretend that enterprise-only files such as Rights/RLS or Lock Radar were attached.
- Portal Proof Packet now shows a dedicated `Killer Demo ZIP` card with endpoint, open-first file, manifest and role packets.
- Portal role handoff cards show availability status plus available/missing file lists.
- Portal summary now shows `Role pkts` and the Proof Packet section shows the role packet rollup before the recipient cards.
- Portal now includes a `Close receipt` download and Proof Packet card for `MEETING_CLOSE_RECEIPT.md/.json`.
- Portal now includes an `Activation` download and Proof Packet card for `POST_DEMO_ACTIVATION_HANDOFF.md/.json`.
- Portal Killer Demo now has a `Killer ZIP archive` button that downloads the merged archive and shows filename/hash/file count.
- API client exposes `killerDemoApi.archive(...)`.

## Verification

```text
pytest tests/unit/test_killer_demo_api.py tests/unit/test_killer_demo_path.py tests/unit/test_evidence_bundle.py -q
14 passed

npm.cmd run build
passed
```

## Product Effect

The seller can now finish the room with one buyer-forwardable ZIP from the Killer Demo screen. The archive contains the procurement handoff from Evidence Bundle plus the exact current Killer Demo proof and packet that were shown in the meeting; `killer-demo-manifest.json` gives SHA-256 checks for those added demo files without mutating the Evidence Bundle manifest. Role-specific `ROLE_*.md` packets make forwarding obvious for developer/QA, architect/security and director/sponsor, while the rollup tells the presenter whether packets are ready, partial or missing before anything leaves the room. `MEETING_CLOSE_RECEIPT.md/.json` turns the meeting outcome into a purchasing handoff: accepted roles, blockers, next paid step, send files and verification route. `POST_DEMO_ACTIVATION_HANDOFF.md/.json` keeps that close moving into paid start, invoice trigger, Day 7 proof and Day 30 acceptance.
