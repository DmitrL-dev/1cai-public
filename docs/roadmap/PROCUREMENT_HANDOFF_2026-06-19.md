# Evidence Bundle Procurement Handoff

Date: 2026-06-19.

Evidence Bundle now produces a buyer-forwardable procurement handoff on top of the hashed artifact bundle and ZIP archive.

## Implemented

- Backend `procurement_handoff` in `POST /api/v1/evidence-bundle/build`.
- Summary fields for required files, missing files, blockers, recipients and forward readiness.
- Required buyer files: Buyer Brief, Buyer Pulse, Board Pack, Commercial Offer Studio, Enterprise Trust Center, Security Questionnaire, Business Case, Pilot Launchpad, Launch Room, Killer Demo, Governance Proof, Safe Autopilot, Test Factory and Productization.
- Required role files: developer, architect, director, QA, ops and vendor reports are generated from the role demo story and travel as separate artifacts.
- Role recipients: director/sponsor, architect/CTO, security/procurement and developer/QA.
- Verification steps for archive hash, manifest SHA-256, governance proof, commercial packet and delivery caveats.
- ZIP archive now includes `procurement-handoff.json` and `procurement-handoff.md`.
- ZIP archive now includes `OPEN_FIRST.md` with buyer-readable start steps, role packets, readiness and verification flow.
- ZIP archive and manifest now include `rentgen-security-questionnaire.json/.md`, matching the Trust Center send-files list.
- `/evidence-bundle` UI shows the handoff status, `OPEN_FIRST.md`, gates, sorted role packets, verification checklist and required file table.
- `POST /api/v1/evidence-bundle/build` exposes `open_first_markdown`, and the UI can preview/download `OPEN_FIRST.md` before downloading the ZIP.
- Role packet cards prioritize Buyer Brief, Buyer Pulse, role reports, Security Questionnaire, Trust Center and technical proof files, with direct links to the supporting routes.
- `/api/v1/evidence-bundle/health` is fast-pulse based and exposes liveness/procurement signal without building the deep bundle; full required-file completeness remains in `/build`.

## Buyer Value

1. Procurement receives one explicit send packet instead of reverse-engineering the archive.
2. Security gets manifest/hash verification and governance routes before the approval meeting.
3. Directors see which files support the paid ask and purchase order.
4. Architects can turn unresolved platform/offline caveats into scope instead of blocking the deal late.
5. Developers and QA get the exact Safe Autopilot/Test Factory proof needed to trust the technical change path.
6. The first-screen Buyer Brief and purchase pulse are hashed required files, so procurement can verify the room map, AI-rent and proof-route signals that opened the meeting.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py src/api/evidence_bundle_api.py`
- `pytest tests/unit/test_evidence_bundle.py -q`
- `npm run build`
