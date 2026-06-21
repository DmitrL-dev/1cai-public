# Evidence Bundle Role Packets

Date: 2026-06-20.

## Why

Procurement handoff already listed recipient send-files, but the ZIP still required a reader to extract the right subset from `OPEN_FIRST.md` or the UI. That is too much friction for a director, architect, security owner or developer who only needs their packet.

## Added

- `packet_file` on every procurement recipient.
- `ROLE_DIRECTOR_SPONSOR.md`, `ROLE_ARCHITECT_CTO.md`, `ROLE_SECURITY_PROCUREMENT.md` and `ROLE_DEVELOPER_QA.md` inside the Evidence Bundle ZIP.
- `procurement_handoff.recipient_packets` with filename, Markdown, SHA-256, routes and send files for direct UI/API download.
- Forwarding kit fields per role packet: subject, body, `.txt` filename and attachment list for buyer-forwardable email/ticket notes.
- `ROLE_DIRECTOR_SPONSOR-forwarding-note.txt`, `ROLE_ARCHITECT_CTO-forwarding-note.txt`, `ROLE_SECURITY_PROCUREMENT-forwarding-note.txt` and `ROLE_DEVELOPER_QA-forwarding-note.txt` inside the Evidence Bundle ZIP.
- Role packet and forwarding-note filenames in `OPEN_FIRST.md`, `procurement-handoff.md`, `archive_contents` and archive acceptance receipt boundary.
- Role packet markdown with decision, send-files, manifest SHA/status, routes, verification and linked Killer Demo ZIP boundary.
- Evidence Bundle UI shows each recipient packet filename, downloads the role packet Markdown and exports the same `.txt` forwarding note that is present in the ZIP.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py`
- `pytest tests/unit/test_evidence_bundle.py -q`
- `npm run build` in `portal`

## Buyer Impact

The ZIP is no longer only a raw proof archive. It carries one stakeholder-ready Markdown file and one copy-paste forwarding note per role, so the presenter can forward a narrow packet without explaining the whole product surface again.
