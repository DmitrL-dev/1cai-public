# Enterprise Trust Center - 2026-06-19

## Why This Slice Exists

Buyer demos now have Scenario Hub, Guided Demo, Pilot Launchpad and Demo Command Center. The remaining enterprise objection is trust: security, CIO, architecture board and procurement need one route that answers locality, SBOM, offline delivery, rights/RLS, platform caveats and artifact verification without forcing them through the whole product.

Enterprise Trust Center turns implemented evidence surfaces into a buyer-safe trust pack:

- closed-contour/offline readiness;
- productization gate and known gaps;
- SBOM inventory and offline bundle controls;
- Evidence Bundle SHA-256 manifest;
- Rights/RLS and security posture gates;
- Platform Doctor and update caveats;
- procurement documents and pilot acceptance.

## Implemented

- Backend service: `src/services/rentgen/enterprise_trust_center.py`
- API: `POST /api/v1/enterprise-trust-center/build`
- Health: `GET /api/v1/enterprise-trust-center/health`
- Portal: `/enterprise-trust-center`
- Evidence Bundle artifacts: `enterprise-trust-center.json/.md` and `rentgen-security-questionnaire.json/.md`
- Security questionnaire handoff inside the same report: sections, owners, send files, verification steps and readiness gates.
- Analysis depth control: preview/standard/deep limits for first-run speed vs production-grade security/Rights coverage.
- Navigation: sidebar, home fast entry, Demo Center, Pilot Launchpad, Guided Demo, Scenario Hub, Business Case, Evidence Bundle route allow-lists.
- Buyer Brief Bridge: `trust_room_bridge` carries the first-minute room map into Trust Center before Security Questionnaire.

## Report Shape

The report contains:

- `trust_controls`: local contour, productization gate, SBOM, offline bundle, hash manifest, rights/RLS, security posture, platform/update, pilot route.
- `security_questions`: direct answers for code locality, SBOM, artifact integrity, roles/RLS, platform upgrade and AI subscription displacement.
- `security_questionnaire`: buyer-forwardable questionnaire with data-locality, SBOM/offline delivery, artifact integrity, Rights/RLS, static security, platform/update, AI subscription displacement and pilot acceptance sections.
- `trust_room_bridge`: Buyer Brief role cards, proof readiness, meeting flow, first files and close question.
- `procurement_pack`: security whitepaper, SBOM, offline manifest, Evidence Bundle, Platform Doctor, Rights/RLS, Business Case, Pilot Launchpad.
- `install_modes`: closed-contour pilot, enterprise local license, vendor rollout.
- `risk_register`: normalized risks from productization, offline readiness, security posture, Rights/RLS and Platform Doctor.
- `exports`: markdown/manifest routes for the approval pack.

## Security Questionnaire

The questionnaire adds the handoff that enterprise buyers usually ask for after the first impressive demo:

- `ready_to_send` and `ready_to_approve` gates;
- eight sections mapped to implemented product routes and trust controls;
- evidence files for each answer, including `rentgen-security-questionnaire.md`, `evidence-bundle-manifest.json`, SBOM/offline, Rights/RLS, platform, business case and pilot files;
- blockers and caveats inherited from failed/warn trust controls;
- verification steps for security, release manager, architect and pilot owner.

This makes the Trust Center usable as a procurement/security attachment, not just an internal diagnostic page.

## First-Run Speed

The Trust Center portal now starts in `preview` depth:

- full metadata graph, static security scan and Rights/RLS matrix are deferred for a faster first build;
- `standard` and `deep` depth remain available for production approval;
- `source_signals` records the selected depth and numeric scan limits;
- preview maps missing-fact platform/pilot risks to `watch` so the first handoff stays navigable, while the risk register still lists the caveats;
- preview reports carry an explicit caveat that full approval requires standard/deep coverage.

`GET /api/v1/enterprise-trust-center/health` now uses the shared buyer pulse and no longer builds either the full report or the synthetic quick Trust Center report. It keeps `controls`, questionnaire status and blocker counters, and adds `purchase_status`, `three_year_ai_rent` and `source: management-fast-pulse`.

## Product Effect

This reduces "what is this monster?" confusion for enterprise buyers:

- developers still get concrete 1C defect proof;
- architects still get platform/topology proof;
- directors still get money and pilot offers;
- security and procurement now get one trust route and a ready questionnaire before they ask for it.
- security and procurement also see the same Buyer Brief room map before the longer questionnaire.

The sales story becomes: local product asset first, optional AI credits second.

## Verification

- `python -m py_compile` for new/changed backend services and APIs.
- `python -m pytest tests/unit/test_enterprise_trust_center.py -q`
- API build smoke confirms `management-buyer-brief`, `buyer-brief.md`/`buyer-pulse.md` first files and `/killer-demo` in proof routes.
- `python -m pytest tests/unit/test_enterprise_value_fast_health.py -q`
- Evidence Bundle regression was extended to require `enterprise-trust-center` artifact and markdown manifest entry.
- Frontend build should verify the questionnaire contract and `/enterprise-trust-center` panel.

Full frontend/backend regression should include:

- `python -m pytest tests/unit/test_enterprise_trust_center.py tests/unit/test_evidence_bundle.py tests/unit/test_demo_command_center.py tests/unit/test_pilot_launchpad.py tests/unit/test_scenario_hub.py -q`
- `npm run build` from `portal/`
- live smoke for unauth/auth API, Evidence Bundle inclusion and `/enterprise-trust-center` route.
