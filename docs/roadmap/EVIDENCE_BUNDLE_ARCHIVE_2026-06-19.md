# Evidence Bundle ZIP Archive

Date: 2026-06-19.

Evidence Bundle now exports a portable unsigned ZIP proof archive in addition to on-screen JSON, Markdown and manifest downloads.

## Implemented

- Backend archive builder: `evidence_bundle_archive(report)`.
- API: `POST /api/v1/evidence-bundle/archive`.
- ZIP contains `OPEN_FIRST.md`, `manifest.json`, `bundle.json`, `evidence-bundle.md`, `README.md` and every artifact JSON/Markdown file.
- Buyer Pulse artifact: `buyer-pulse.json` and `buyer-pulse.md` are generated from the fast first-screen purchase signal and included in the manifest/ZIP.
- Buyer Brief artifact: `buyer-brief.json` and `buyer-brief.md` are generated from the fast first-minute buyer route and included in the manifest/ZIP.
- `OPEN_FIRST.md` gives the buyer a first-read guide with role packets, readiness state, blockers/review items and verification steps.
- Build response exposes the same guide as `open_first_markdown` for on-screen preview and standalone Markdown download.
- ZIP also contains `procurement-handoff.json` and `procurement-handoff.md` with role recipients, required files and verification steps.
- Security questionnaire artifact: `rentgen-security-questionnaire.json` and `rentgen-security-questionnaire.md` are generated from Enterprise Trust Center and included in the manifest/ZIP.
- Role handoff artifacts: `rentgen-developer-report`, `rentgen-architect-report`, `rentgen-director-report`, `rentgen-qa-report`, `rentgen-ops-report` and `rentgen-vendor-report` JSON/Markdown files are included when Demo Story is enabled.
- Governance proof artifact: `governance-proof.json` and `governance-proof.md` with approval records, audit-chain verification and recent audit events.
- Commercial assumptions flow through build/archive requests into every generated Business Case branch, so bundled Business Case, Board Pack and Killer Demo artifacts share the same AI-rent baseline.
- The bundle exposes `commercial_assumptions` at top level and repeats the receipt in `OPEN_FIRST.md`, `procurement-handoff.md`, README and the `/evidence-bundle` UI side panel.
- Response headers include `X-Archive-Sha256` and `X-Archive-Files`.
- UI: `/evidence-bundle` has a `ZIP archive` download action, shows archive SHA-256 after download, surfaces `OPEN_FIRST.md` and presents recipient-specific role packets for forwarding.
- Health is fast-pulse based; `POST /api/v1/evidence-bundle/build` and `/archive` remain the proof-complete paths.
- Tests: `tests/unit/test_evidence_bundle.py`.

## Buyer Value

1. Security and procurement receive one portable proof file instead of screenshots or scattered downloads.
2. Directors can forward the archive with a manifest and hash.
3. Architects and QA can verify artifact hashes against `manifest.json`.
4. Productization still owns signed/offline archives; Evidence Bundle gives fast approval/KP proof.
5. Security can verify that write approvals and audit integrity travel with the proof archive.
6. Procurement sees the same local-license vs AI-rent numbers that were shown in the live demo and board pack.
7. A forwarded ZIP has its commercial baseline visible before the recipient hunts through individual artifacts.
8. The first screen is no longer only a UI state: Buyer Brief and Buyer Pulse travel as hash-verifiable proof files.

## Verification

- `python -m pytest tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- API smoke with `monthly_ai_subscription_cost=200000` returns `7200000` in bundled Business Case and `7 200 000 RUB` in bundled Buyer Brief, Buyer Pulse, Board Pack and Killer Demo.
