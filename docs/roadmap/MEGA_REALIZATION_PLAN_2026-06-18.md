# Mega plan: превратить 1С:Рентген в продукт, который хотят купить

Дата: 2026-06-18.

> RC0 Release Gate, 2026-06-20: backend unit suite is green (738 passed, 1 skipped), portal lint/build pass, FastAPI route-auth smoke exposes 369 routes with gateway/knowledge routes protected; build is suitable for controlled paid pilots, not GA production until clean-branch, Docker, staging, security and ops gates in `RC0_RELEASE_GATE_2026-06-20.md` are closed.

Цель: сделать не "еще один AI-чат для 1С", а локальный инженерный штаб для 1С-разработки, архитектуры, сопровождения и управления релизами. Клиент должен за первые минуты понять, что продукт делает, где его боль, сколько риска уже найдено, что делать дальше и почему это дешевле и надежнее вечной облачной AI-подписки.

> Implementation status, 2026-06-19: Волна 0 закрыта в P0-срезе; из Волны 1 реализованы role-based
> Home, complete demo story, role reports и markdown export; из Волны 2 реализован Configuration Intake
> Wizard v1 (`/configurations`, `POST /api/v1/management/intake/plan`); из Волны 3 реализован первый
> Query Surgeon rule `join-field-null-guard` для полей из LEFT JOIN без `ЕстьNULL`/`ЕСТЬ NULL`;
> из Волны 4 реализован Platform Doctor v1 (`/platform-doctor`, `GET /api/v1/platform-doctor/analyze`);
> из Волны 5 реализован Lock Radar v1 (`/lock-radar`, `POST /api/v1/lock-radar/analyze`);
> из Волны 5 реализован Extension Safety v1 (`/extension-safety`, `POST /api/v1/extension-safety/analyze`);
> из Волны 4/5 реализован Update War Room v1 (`/update-war-room`, `POST /api/v1/update-war-room/plan`);
> из Волны 3/5 реализован Rights & RLS Simulator v1 (`/rights-rls`, `GET /api/v1/rights-rls/analyze`);
> из Волны 7 реализован Value Packs Center v1 (`/value-packs`, `GET /api/v1/value-packs/catalog`);
> из Волны 5/7 реализован Evidence Bundle v1 (`/evidence-bundle`, `POST /api/v1/evidence-bundle/build`, `POST /api/v1/evidence-bundle/archive`);
> из Волны 7 реализован Vendor Portfolio v1 + portfolio mode + commercial decision board (`/vendor-portfolio`, `GET /api/v1/vendor-portfolio/audit`, `POST /api/v1/vendor-portfolio/portfolio`);
> Vendor Portfolio Buyer Brief Bridge adds `vendor_room_bridge`, passes Buyer Brief into vendor audits and shows primary motion, vendor motion, role cards, proof readiness, meeting flow and close question before Deal Board.
> из Волны 7 реализован Business Case v1 (`/business-case`, `POST /api/v1/business-case/build`);
> из enterprise-hardening реализован Productization Console v1 (`/productization`, `/api/v1/productization`);
> Enterprise Trust Center Security Questionnaire adds buyer-forwardable sections, owners, send files, verification steps and readiness gates for security/procurement handoff.
> Enterprise Trust Center First-Run Depth adds preview/standard/deep scan profiles and lightweight health so the first buyer click stays understandable while deep approval remains available.
> Enterprise Trust Buyer Brief Bridge adds `trust_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md`, passes Buyer Brief through the trust build chain and shows primary motion, trust motion, role cards, proof readiness, meeting flow and close question before Security Questionnaire.
> Board Pack v1 (`/board-pack`, `POST /api/v1/board-pack/build`) compresses Concierge, Trust, Offer, Business Case and Evidence Bundle into one board-level buying motion.
> Board Pack Close Packet adds board-level paid ask, one-page order, approval/audit/evidence checkout gates, buyer commitments and governance proof routes to the director decision artifact.
> Board Pack Buyer Brief Bridge adds `board_room_bridge`, starts the Board Pack proof packet with `buyer-brief.md`/`buyer-pulse.md` and shows primary motion, committee role cards, proof readiness, meeting flow and final board question before deep board sections.
> Outcome Ledger v1 (`/outcome-ledger`, `POST /api/v1/outcome-ledger/build`) turns the buying motion into 7/30/90-day adoption, metrics, risk burndown and expansion proof.
> Outcome Acceptance Rollup converts Pilot Launchpad sign-off rows into outcome routes, proof files, next owner/window and claim readiness.
> Outcome Governance Refresh adds approval/audit/evidence/trust gates and Day 7/30/60/90 proof refresh to `/outcome-ledger`.
> Outcome Ledger Buyer Brief Bridge adds `outcome_room_bridge`, starts proof packet/exports with `buyer-brief.md`/`buyer-pulse.md` and shows primary motion, outcome motion, role cards, proof readiness, meeting flow and outcome question before value/adoption sections.
> Outcome Ledger Post-Purchase Proof Spine adds Day 0 receipt continuity to `/outcome-ledger`: `MEETING_CLOSE_RECEIPT.md`, `POST_DEMO_ACTIVATION_HANDOFF.md`, `archive-acceptance-receipt.md/.json` and `killer-demo-manifest.json` now appear in proof/export surfaces, acceptance rollup fallback, markdown and UI.
> Pilot Activation Contract adds selected paid offer, invoice trigger, Day 0/7/30 milestones, buyer commitments and approval/audit/evidence gates to `/pilot-launchpad`.
> Pilot Launchpad Buyer Brief Bridge adds `pilot_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md` and shows primary motion, activation motion, role cards, proof readiness, meeting flow and activation question before pilot offers.
> Pilot Acceptance Register adds Day 0/1/7/30 owner sign-off rows with decision, route, evidence file, status, blocker and next action to `/pilot-launchpad`.
> Launch Room v1 (`/launch-room`, `POST /api/v1/launch-room/build`) gives the buyer one start cockpit with next best action, role paths, meeting modes, route health and proof packet.
> Launch Room Buyer Journey connects Close -> Activate -> Govern -> Realize with checkout, activation and governance gates, plus `/approvals` and `/audit` in the proof packet.
> Launch Room Acceptance Signals bring Outcome acceptance rows, watch/blocked counts and claim readiness into the first buyer cockpit.
> Launch Room Purchase Spine puts AI/month, three-year rent, local-license anchor, break-even, invoice trigger and proof routes into the first buyer cockpit.
> Launch Room Purchase Artifact Sync puts `OPEN_FIRST_KILLER_DEMO.md`, `MEETING_CLOSE_RECEIPT.md`, `POST_DEMO_ACTIVATION_HANDOFF.md` and `killer-demo-manifest.json` into Launch Room proof/evidence surfaces so the cockpit matches the actual post-demo handoff.
> Launch Room Archive Acceptance Receipt Sync adds `archive-acceptance-receipt.md/.json` to purchase artifacts, proof packet and buyer room bridge so the first buying cockpit points to the same dual-archive procurement receipt as Evidence Bundle.
> Launch Room Buyer Brief Bridge adds `buyer_room_bridge`, starts the Launch Room proof packet with `buyer-brief.md`/`buyer-pulse.md` and shows primary motion, role cards, proof readiness and meeting flow before deep cockpit phases.
> Launch Room Open-First Bridge carries `open_first_path` into the cockpit bridge, markdown and portal UI, preserving the same orient/prove/close/verify route from Home and Buyer Room Packet.
> Buyer Concierge Purchase Router brings the same local-license buying motion to the first role/pain screen: role-specific purchase asks, AI-rent baseline, Launch Room primary CTA, close sequence and buyer-forwardable proof files.
> Buyer Concierge Buyer Brief Bridge adds `concierge_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md`, passes Buyer Brief into its pre-deal child reports and shows primary motion, role cards, proof readiness, meeting flow and close question before Purchase Router.
> Buyer Room Packet Pre-Deal Role Controls add shared packet download/verify actions to Buyer Concierge, Scenario Hub, Demo Command Center, Guided Demo, Business Case, Value Packs and Vendor Portfolio so role-first, value-first and vendor-first buyers can attach the same verified open-first packet before the deep workbench.
> Deal Nav Value/Vendor Discovery adds Value Packs and Vendor Portfolio to the Deal sidebar and Home quick-start/fallback cards so buyable packaging and pre-sale audit are visible without route hunting.
> Buyer Fast Health moves Home, Launch Room health and Buyer Concierge health onto a shared fast buyer pulse so liveness checks stay near-instant while deep `/build` routes remain proof-complete.
> Home Open-First Buyer Rail adds a compact four-step orient/prove/close/verify path to the first screen, driven by Buyer Brief artifacts when available and backed by Launch Room/Killer Demo/Evidence/Pilot fallbacks while data loads.
> Open-First Path Backend Contract promotes that four-step path into `buyer_brief.open_first_path`, Buyer Room Packet `open-first-path.json/.md`, Buyer Brief/Evidence Markdown and packet verification so the first-screen route is a hashable buyer artifact.
> Open-First Path Evidence/Killer Sync materializes `open-first-path.json/.md` in Evidence Bundle, ranks it into Killer Demo proof packets, shows it in close-room Buyer Room Map and starts role handoffs with that file.
> Post-Purchase Open-First Path Continuity carries `open_first_path` into Pilot Launchpad and Outcome Ledger bridges, markdown and portal UI, keeping the orient/prove/close/verify route visible through Day 0 activation and Day 30 outcome claims.
> Open-First Path Pre-Deal/Value/Trust Sync moves the same orient/prove/close/verify path into Buyer Concierge, Scenario Hub, Demo Command Center, Guided Demo, Business Case, Value Packs, Vendor Portfolio, Commercial Offer Studio, Board Pack and Enterprise Trust Center with shared backend/frontend helpers and tests.
> Killer Demo Open-First Path Panel promotes the Evidence Bundle `open-first-path` JSON into `proof_packet.open_first_path`, Killer Demo markdown and the portal Proof Packet panel so close-room buyers see the four-step route, not just the filename.
> Evidence Bundle Fast Health keeps `/api/v1/evidence-bundle/health` on the same fast pulse while `/build` and `/archive` remain full proof-generation paths.
> Deal Fast Health extends that same contract to Board Pack, Commercial Offer Studio, Outcome Ledger and Killer Demo so buyer-facing liveness never builds the full proof chain.
> Pre-Deal Fast Health extends fast-pulse liveness to Pilot Launchpad, Demo Command Center, Guided Demo and Scenario Hub while keeping their `/build` routes proof-complete.
> Enterprise/Value Fast Health extends the same buyer-pulse liveness contract to Business Case, Vendor Portfolio, Value Packs and Enterprise Trust Center, so value/trust route checks never launch deep proof generation.
> Value Packs Buyer Brief Bridge adds `value_room_bridge`, passes Buyer Brief into the package catalog and shows primary motion, package motion, role cards, proof readiness, meeting flow and close question before package cards.
> Test Factory v1 (`/testing`, `POST /api/v1/test-factory/build`) turns changed modules into run-now tests, YAxUnit/Vanessa skeletons, manual checks and evidence.
> Change Impact False-Safe-Zero Guard propagates `impact_measured`, `coverage` and `coverage_caveat` through change impact, diff review, Test Coverage Matrix, Test Factory and Release Readiness, so zero impact is never shown as safe when graph coverage is missing.
> README/HANDOFF Truth Sync updates the current-truth entry points for buyer-room bridges and false-safe-zero downstream coverage; `rentgenApi.build` is confirmed by contract test against `GET /api/v1/rentgen/build`.
> Archi Legacy Optional Guard keeps `/api/v1/archi` available for legacy GraphService users but health now reports `legacy_optional_*`, `core=false` and Neo4j requirement instead of making the SQLite Rentgen product look unhealthy.
> Archi Export Counts fixes legacy `/api/v1/archi/export` async execution and returns actual ArchiMate element/relationship counts from the generated XML instead of `0/0`.
> Core/Optional Dependency Split keeps `requirements.txt` as baseline and moves OpenAI, Qdrant, sentence-transformers and Neo4j into `requirements-optional.txt`; heavy ML remains in `requirements-ml.txt`.
> Demo Command Center Buyer Brief Bridge adds `demo_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md` and shows primary motion, presenter opening, role cards, proof readiness, meeting flow and close question before live stages.
> Killer Demo Path v1 (`/killer-demo`, `POST /api/v1/killer-demo/build`) compresses Launch Room, Test Factory, Trust Center, Board Pack, Outcome Ledger and Evidence Bundle into one buyer-ready presentation route with role sparks, proof moments and close scripts.
> Killer Demo Proof Packet extends that route with bundle-aware SHA-256 files, ZIP archive handoff and role-specific instructions for developer/QA, architect/security and director/sponsor.
> Killer Demo Deal Readiness adds blockers, next paid step, role acceptance and close checklist so the presenter knows whether to ask for purchase, proof sprint or hardening scope.
> Local Asset Case inside Killer Demo ties Business Case, Trust Center, Productization and Evidence Bundle into the message: buy local 1C evidence, not endless generic AI rent.
> Killer Demo Close Signals show what the customer can repeat and which roles accepted the proof before the meeting ends.
> Killer Demo Committee Close Board shows accepted/blocked buying committee roles, role-specific send files and the final procurement/scope question.
> Killer Demo Objection Router gives the presenter one panel for size/confusion, AI subscription, security, developer proof, proof forwarding, price-before-proof and after-purchase objections with route, proof file, owner, status and close question.
> Killer Demo Security Questionnaire Sync adds `rentgen-security-questionnaire.md` to architect/security proof packet handoff and the security objection answer.
> Killer Demo Proof Packet Priority orders visible proof files so demo, security questionnaire, Trust Center, tests, Safe Autopilot and governance proof appear before lower-signal manifest entries.
> Killer Demo Buyer Brief Sync puts `buyer-brief.md`/`buyer-pulse.md` at the front of the proof packet, exposes `proof_packet.room_map`, starts role handoff with Buyer Brief and points proof-forwarding objections to the buyer room map.
> Role Handoff Materialization adds developer, architect, director, QA, ops and vendor role reports as separate Evidence Bundle JSON/Markdown artifacts and Killer Demo recipient handoff files.
> Business Case Subscription Escape adds three-year AI-rent baseline, local-license anchor, break-even months, stakeholder lines and guardrails so finance sees a product purchase instead of another token bill.
> Business Case Buyer Brief Bridge adds `business_room_bridge`, passes Buyer Brief into Business Case and shows primary motion, director value motion, role cards, proof readiness, meeting flow and close question before money levers and subscription escape.
> Commercial Offer Procurement Dossier adds recommended purchase, local-vs-AI-rent line, license models, procurement artifacts, approval matrix and red lines inside Offer Studio.
> Commercial Offer Subscription Escape Sync carries three-year rent, local-license anchor, break-even and guardrails into the one-page order and procurement dossier.
> Commercial Offer Buyer Brief Bridge adds `offer_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md` and shows primary motion, recommended purchase, role cards, proof readiness, meeting flow and close question before procurement/pricing sections.
> Board/Killer Subscription Escape Sync projects the same three-year AI rent, local-license anchor and break-even into Board Pack and Killer Demo close artifacts.
> Deal Archive Receipt Sync adds `archive-acceptance-receipt.md` to Commercial Offer Studio procurement/evidence requirements and Board Pack close evidence so the paid ask names the dual-archive receipt before signature.
> Commercial Assumption Sync passes buyer AI-rent assumptions through Killer Demo and Evidence Bundle so live demo, board pack and ZIP artifacts do not fall back to default pricing numbers.
> Evidence Bundle Commercial Receipt repeats AI/month, three-year rent, local-license anchor and break-even in bundle JSON, OPEN_FIRST, procurement handoff, archive README and UI.
> Evidence Bundle UI now exports the full bundle JSON, Markdown, manifest and unsigned ZIP proof archive with archive SHA-256.
> Evidence Bundle Procurement Handoff adds buyer-forwardable required files, recipient packets, verification steps, readiness gates and `procurement-handoff.json/.md` inside the ZIP archive.
> Evidence Bundle Security Questionnaire Materialization adds `rentgen-security-questionnaire.json/.md` to artifacts, manifest, required files and ZIP so Trust Center send-files are real proof files.
> Evidence Bundle Role Packet UI turns procurement recipients into sorted send-ready cards with role reports, Security Questionnaire, Trust Center proof and route links.
> Evidence Bundle OPEN_FIRST adds a buyer-readable ZIP/UI entry point with role packets, readiness, blockers/review items and verification flow so downloaded archives do not feel like raw dumps.
> Evidence Bundle Buyer Pulse Materialization adds `buyer-pulse.json/.md` as a required, hash-verifiable proof file so the first-screen purchase signal travels with procurement.
> Evidence Bundle Buyer Brief Materialization adds `buyer-brief.json/.md` as a required, hash-verifiable proof file so the first-minute room map, role cards, proof readiness and meeting flow travel with procurement.
> Evidence Bundle Buyer Room Plan Materialization adds `buyer-room-plan.json/.md` as a required, hash-verifiable proof file, exposes it in OPEN_FIRST/README/archive receipt and the Evidence Bundle UI, and syncs Killer Demo proof packet handoff to the single first route and close question.
> Evidence Bundle Buyer Room Packet Controls add direct `Buyer Room Packet ZIP` download/verify actions to `/evidence-bundle`, with local SHA-256 comparison and endpoint verification status beside the archive controls.
> Evidence Bundle Role Packets materializes `ROLE_DIRECTOR_SPONSOR.md`, `ROLE_ARCHITECT_CTO.md`, `ROLE_SECURITY_PROCUREMENT.md`, `ROLE_DEVELOPER_QA.md` and matching `ROLE_*-forwarding-note.txt` files inside the ZIP and `procurement_handoff.recipient_packets`, with manifest-aware send-file status, forwarding subject/body/attachments and direct UI Markdown/text downloads for each stakeholder.
> Evidence Bundle Archive Manifest adds `archive-manifest.json` to the ZIP, API archive headers, receipt boundaries and Evidence Bundle UI, hashing generated files such as `OPEN_FIRST.md`, role packets and forwarding notes separately from source `manifest.json`.
> Dual Archive Verify Guide adds `VERIFY_ARCHIVE.md` to both Evidence Bundle and Killer Demo ZIPs, with each guide covered by its archive manifest so procurement sees exact hash/header/boundary steps inside the downloaded package.
> Archive Verify Endpoints add `POST /api/v1/evidence-bundle/archive/verify` and `POST /api/v1/killer-demo/archive/verify`, plus portal verify cards, so buyers can validate both ZIPs and the embedded Evidence manifest before forwarding files.
> Archive Verification Receipt adds `verification_receipt` and Markdown receipt downloads to Evidence/Killer ZIP verification, turning pass/warn/fail checks into ticket-ready procurement evidence with expected headers, findings and embedded Evidence status.
> Dual Archive Verification Packet adds `POST /api/v1/evidence-bundle/archive/verify-dual` and portal `Verify Both ZIPs`, proving Evidence ZIP and linked Killer Demo ZIP as one pair with `same_evidence_archive_hash` plus combined JSON/Markdown packet downloads.
> Procurement Verification Packet ZIP adds `POST /api/v1/evidence-bundle/archive/verification-packet` and portal `Verification Packet ZIP`, packaging dual verification, both archive receipts and a hash table into one small security/procurement ticket attachment.
> Verification Packet Buyer Path Sync surfaces `archive-verification-packet.zip` in Buyer Pulse, Buyer Brief, Launch Room, Killer Demo proof packet, Meeting Close Receipt and Post-Demo Activation Handoff so the first screen, close room and procurement handoff all point to the same verifiable ZIP.
> Evidence Bundle Verification Packet Handoff Sync adds `verification_packet`, `control_attachments`, recipient packet attachments and pair-level verification gate/step while keeping the Evidence/Killer/Verification ZIP boundaries explicit.
> Post-Purchase Verification Packet Continuity carries `archive-verification-packet.zip` into Pilot Launchpad Day 0 activation, acceptance register, exports and Outcome Ledger post-purchase proof spine so outcome claims require the same pair-level archive receipt accepted by procurement.
> First Screen Procurement Handoff adds `purchase_path.procurement_handoff` to Buyer Pulse/Brief and Home, giving procurement/security an open order for Evidence ZIP, Killer Demo ZIP, Verification Packet ZIP, close receipt and activation handoff before they enter the deep workbench.
> Launch Room Procurement Handoff Sync mirrors the same open order inside `purchase_spine`, Launch Room markdown and UI so buyers who start from the cockpit still see exact files and hash headers before deep navigation.
> Killer Demo Procurement Open Order extends `proof_packet.procurement_handoff` with the same open order, attachments and acceptance line so the live close room ends with exact procurement headers and files.
> First Screen Verification Packet Downloads add click-only `Verification Packet ZIP` downloads with local SHA-256 comparison to Home and Launch Room so the earliest buyer screens can produce the procurement control ZIP directly.
> Verification Packet Shared Portal Controls unifies Home, Launch Room, Killer Demo, Pilot Launchpad, Outcome Ledger and Evidence Bundle on one ZIP download component with local SHA-256 comparison, status display and consistent error handling.
> Verification Packet Pre-Deal Role Controls adds the shared Verification Packet ZIP download to Buyer Concierge, Scenario Hub, Demo Command Center, Guided Demo, Business Case, Value Packs, Vendor Portfolio, Commercial Offer Studio, Board Pack and Enterprise Trust Center so role/value/trust buyers can attach the same pair-level procurement control ZIP without leaving their room.
> First Screen Buyer Room Packet adds `GET /api/v1/management/buyer-room-packet` and shared Home packet download/verify controls, giving the first screen a compact open-first archive with Buyer Brief, Buyer Pulse, Buyer Room Plan, Purchase Path, Procurement Handoff and packet SHA-256.
> Buyer Room Packet Purchase Path Sync makes `rentgen-buyer-room-packet.zip` a first-class Buyer Pulse/Brief purchase artifact, send file and first procurement handoff step with `X-Buyer-Room-Packet-Sha256`.
> Buyer Room Packet Verify adds `GET /api/v1/management/buyer-room-packet/verify`, Home verify UX and CORS header exposure for packet/archive/manifest hashes so browser procurement controls see the same SHA-256 evidence as tests and curl.
> Buyer Room Packet Decision Room Controls add a shared portal packet download/verify component and surface it in Board Pack, Commercial Offer Studio and Enterprise Trust Center so director/procurement/security rooms can attach the same verified open-first packet.
> Launch Room Buyer Room Packet Sync carries the same open-first ZIP into Launch Room purchase spine, proof packet, buyer room bridge, markdown and portal download controls.
> Launch Room Buyer Room Packet Verify Sync adds the same verify action to `/launch-room`, showing packet status, hash-table status, open-first status, archive SHA-256 and finding count from the cockpit.
> Killer Demo Buyer Room Packet Sync carries the same open-first ZIP into close-room procurement handoff, room map, commercial close requirements, meeting receipt and activation handoff.
> Killer Demo Buyer Room Packet Verify Sync adds close-room download and verify controls for `rentgen-buyer-room-packet.zip`, including local SHA-256 match and endpoint verification status.
> Post-Purchase Buyer Room Packet Continuity carries `rentgen-buyer-room-packet.zip` into Pilot Launchpad Day 0 handoff, procurement pack, acceptance register, exports and Outcome Ledger post-purchase proof spine.
> Post-Purchase Buyer Room Packet Verify Continuity adds direct packet download/verify controls to Pilot Launchpad and Outcome Ledger so Day 0 activation and Day 30 outcome claims can attach the same verified open-first packet.
> Buyer Room Packet Shared Portal Controls unifies Home, Launch Room, Killer Demo, Pilot Launchpad, Outcome Ledger, Evidence Bundle and pre-deal/value/trust rooms on the same ZIP/verify component, keeping local SHA-256 comparison and endpoint verification consistent across the buyer path.
> Evidence Bundle Killer Demo Handoff Bridge adds `procurement_handoff.killer_demo_handoff`, OPEN_FIRST/README guidance and portal visibility for the linked Killer Demo ZIP so `MEETING_CLOSE_RECEIPT.md` and `POST_DEMO_ACTIVATION_HANDOFF.md` are forwarded from the close-room archive without pretending they live in the ordinary Evidence Bundle ZIP.
> Evidence Bundle Archive Acceptance Receipt adds `archive_acceptance_receipt` plus `archive-acceptance-receipt.json/.md` to the portal and ZIP so procurement records Evidence Archive and linked Killer Demo ZIP filenames, hash headers, open-first files and file boundaries in one ticket.
> Evidence Bundle Dual Archive Download adds a linked Killer Demo ZIP button to `/evidence-bundle` and exposes `X-Killer-Demo-Archive-Sha256` from `/api/v1/killer-demo/archive`, so procurement can download both archives and record both hashes from one screen.
> Killer Demo Archive Header Sync makes `X-Killer-Demo-Archive-Sha256` the named close-room ZIP hash across proof packet, meeting receipt, archive README/open-first helpers, Evidence Bundle bridge and tests while preserving `X-Archive-Sha256` as a compatibility response header.
> Evidence Bundle Killer Manifest Receipt Guard names `killer-demo-manifest.json` in the Evidence ZIP README and locks it in the linked archive receipt boundary, so procurement has an explicit manifest file for the Killer Demo archive hash.
> Offline Delivery Passport adds buyer-ready `DELIVERY_PASSPORT.json/.md` to Productization offline archives, verifies passport-to-manifest SHA-256 and shows signature/gate/role handoff in `/productization`.
> Productization Trust Sync marks the existing tamper-evident audit hash chain as implemented, keeps `/api/v1/audit/verify` in the trust story and leaves live SIEM streaming as customer-adapter hardening.
> Audit SIEM Handoff adds `/api/v1/audit/siem-export`, SIEM-ready JSONL/JSON with chain-valid context and SHA-256, a `/audit` download button and Governance Proof `siem_handoff`.
> Anti-monster sidebar pass groups the growing product into Start, Deal, Engineering and Trust & Ops sections without removing deep routes.
> Anti-monster home pass separates the first four buyer actions (Killer Demo, Launch Room, Configuration Intake, Evidence Bundle) from deep workbench entries.
> Legacy Mock Route Redirects convert hidden `/wiki`, `/bpmn` and `/marketplace` mock/sample pages into redirects toward Evidence Bundle, Architecture and Value Packs, so stray URLs no longer expose unfinished generic UI.
> Legacy AI / IDE Route Redirects convert hidden `/copilot`, `/code-review`, `/rentgen` and `/ide` legacy pages into redirects toward Safe Autopilot, Quality, Home and Delivery Workbench, removing old generic AI/IDE positioning from direct URLs.
> Subscription Escape Coverage Map reframes `/copilot-coverage` and related productization/executive labels as a Rentgen local-asset/subscription-escape map while keeping the compatibility endpoint and adding regression coverage against old Copilot product naming.
> Grounded Codegen Review-Ready Contract removes raw `TODO` scaffolds from the backend/MCP local BSL generator and returns guarded-review-ready contracts with explicit owner, rights, audit and test gates.
> No Raw TODO Scaffolds removes unfinished placeholder output from the BSL editor sample, Copilot fallback completions and Python/Jest test generators, with UTF-8 BSL keyword coverage and regression tests.
> No Stub Language Buyer Surfaces removes remaining stub/заглушка wording from reference scenario reports and Launch Room artifact summaries, and makes OAuth string-user ids stable instead of collapsing to one compatibility id.
> Query Surgeon NULL Guard Hardening fixes mojibake in LEFT JOIN diagnostics, recognizes Russian `ЕстьNULL`/`ЕСТЬ NULL` guards in mixed and multiline cases, ignores commented joins and exposes safe options/tests in Standards Review UI/Markdown.
> DevOps Guarded Automation Contract turns legacy DevOps endpoints into honest offline Compose analysis, fixes `/ai/evolve/metrics` and marks autonomous self-modification as disabled by policy with `/safe-autopilot` as the approved route.
> LLM Gateway Offline Fallback Naming renames no-provider diagnostics from placeholder to offline fallback, adds fallback reasons and refreshes gateway tests around the current `get_client` contract.
> Wiki Evidence-Aware Offline Search removes fabricated Ask Wiki/RAG stub answers, adds local evidence/caveat coverage, offline lexical search and fixes dead wiki database imports.
> Legacy Database Import Compatibility adds `src/database.py` as a shim over `src.infrastructure.db.connection`, keeping older routes/security helpers/test fixtures importable during the refactor.
> Wiki Static UI Evidence Shell replaces the mounted `/wiki-ui` legacy CRUD/stub page with a buyer-safe evidence shell that routes users to Evidence Bundle, Killer Demo, Launch Room and Outcome Ledger.
> Role Router Offline Contract removes `agent: "placeholder"` and fake pending integrations from `RoleBasedRouter`, replacing them with an honest `offline_role_router` contract with coverage, caveats, required evidence and role-specific next actions.
> Multi-Role Agents Evidence Contract removes fabricated BA/QA/MCP fixture answers, keeps baseline agent imports optional-safe and returns source-backed offline contracts instead of fake success metrics.
> Security Offline Contracts make missing LLM/CVE/SAST/DAST integrations explicit: baseline security imports work, regex scans are bounded, CVE absence is not treated as proof of safety and DAST/SAST gaps return measured=false contracts.
> Kubernetes Offline Contract makes deploy/scale/status/log calls return explicit `offline_kubernetes_contract` with `applied=false`, required evidence and caveats when kubeconfig/adapter is not configured.
> RAS Monitor Evidence Contract adds `get_cluster_health`, removes the fake cluster fallback and marks unavailable/partial RAS reads as no/partial evidence instead of healthy platform state.
> LLM Provider Strategies Offline Contract replaces autogenerated TODO strategy docs and `skipped` provider responses with a consistent `offline_provider_contract` for GigaChat, YandexGPT, Naparnik, Ollama and Tabnine.
> Dashboard Evidence Contract removes synthetic executive/developer dashboard money, growth, tasks, PRs, CI and quality scores, replacing them with measured/not-measured sections and caveats.
> Analytics Evidence Contract removes hardcoded owner/executive/PM/developer analytics numbers and ROI mock monetization, returning measured/not-measured dashboard contracts and `roi_measured=false` without a value model.
> Runtime Evidence Hardening removes product-facing fabricated runtime outputs from Architect MCP, graph metrics, performance, SQL optimization, technology selection, CI/CD test totals, secure developer apply, code review, Copilot generation, memory consolidation and health checks.
> ML Predictor Encoding Trust Cleanup removes mojibake docstrings, comments and log/error messages from the sklearn predictor layer, keeping runtime traces readable and enterprise-safe.
> Telegram BSL Upload Diagnostics replaces the "analysis in development" document reply with real local BSL diagnostics for `.bsl/.os/.txt` uploads, including UTF-8/CP1251 decoding, metrics, severity counts and top findings, and cleans Telegram formatter/start text from mojibake.
> Telegram BSL Upload Safe-Fix Report extracts BSL upload decoding/reporting into a testable helper and adds first safe option plus first test expectation to each top finding, so a LEFT JOIN/NULL upload produces a fix pattern and verification check immediately in Telegram.
> Runtime Trust Placeholder Cleanup removes remaining product-code TODO/fake/stub smells by calculating Marketplace rating trend, restoring Cyrillic BSL lexer literals for `ИСТИНА/ЛОЖЬ/НЕОПРЕДЕЛЕНО`, and renaming graph-builder external call comments as unresolved references instead of placeholders.
> Home Buyer Start adds a first-screen purchase path with Launch Room, Killer Demo, Board Pack, Evidence Bundle and approve/audit/activate/realize governance chain links.
> Home Buyer Pulse adds fast `/api/v1/management/buyer-pulse` for `/`: purchase status, three-year AI-rent line, proof routes and governance gates are visible before deep navigation without building deep deal artifacts.
> Home Buyer Brief adds fast `/api/v1/management/buyer-brief` and drives `/` role/proof cards from backend: primary motion, room line, role cards, proof readiness, meeting flow and embedded Buyer Pulse.
> Buyer Room Plan adds a one-route live-demo operator plan to `/api/v1/management/buyer-brief` and Home: role, start route, proof file, close question and send files are chosen before the buyer sees the full workbench.
> First Screen Purchase Path adds `purchase_path` to Buyer Pulse/Brief and Home, showing Launch Room -> Killer Demo ZIP -> `MEETING_CLOSE_RECEIPT.md` -> `POST_DEMO_ACTIVATION_HANDOFF.md` -> Outcome Ledger before the buyer enters deep workbench pages.
> First Screen Archive Receipt Sync adds `archive-acceptance-receipt.md/.json` to Buyer Pulse/Brief purchase files and Home purchase path cards so the first screen names the procurement receipt for dual-archive hash recording.
> Home Purchase Files Manifest Visibility shows `purchase_path.send_files` on the first screen and locks `killer-demo-manifest.json` in Buyer Pulse/Brief, so procurement sees the manifest together with receipt and activation files before opening deep pages.
> Guided Demo Buyer Brief Bridge adds `guided_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md` and shows primary motion, guided path, role cards, proof readiness, meeting flow and close question before the guided buyer route.
> Scenario Hub Buyer Brief Bridge adds `scenario_room_bridge`, starts exports with `buyer-brief.md`/`buyer-pulse.md` and shows primary motion, recommended path, role cards, proof readiness, meeting flow and close question before the pain-led scenario gallery.
> Local Launch Handoff now prints Launch Room, Killer Demo, Board Pack, Approvals and Audit URLs from `scripts/start_rentgen.ps1`.
> Killer Demo Opening Brief adds first-click guidance, 30-second talk track, role entries and anti-confusion responses so a new buyer starts from one route instead of the whole product map.
> Portal Code Splitting adds TanStack Router autoCodeSplitting and Rollup manual chunks, removing the 500KB Vite warning while keeping chunk limits honest.
> Safe Autopilot v1 (`/safe-autopilot`, `POST /api/v1/safe-autopilot/plan`) implements the read-only Ask/Plan/Impact/Diff/Tests/Evidence/Approval route with no direct apply, approval handoff, blocked dangerous actions, AI-independence/local-first contract, deterministic patch blueprints, manual-review diff proposals for LEFT JOIN NULL guards and Evidence Bundle export.
> Safe Autopilot NULL Guard Refinement deduplicates real query candidates, avoids blind `ЕстьNULL` wrapping in join conditions and ignores `Справочник.<Имя>.ПустаяСсылка` type qualifiers as aliases.
> Query Surgeon Mixed NULL Guard Refinement flags unguarded joined fields hidden beside guarded fields on the same SELECT line, checks `ЕстьNULL` / `ЕСТЬ NULL` against the concrete `Alias.Field`, and suppresses real Unicode `ON/ПО/И/ИЛИ/ГДЕ` condition continuations; the user sample `Есть NULL.txt` now returns zero false join-null findings.
> Safe Autopilot Approval Request (`POST /api/v1/safe-autopilot/approval-request`) creates a real authenticated `write_module_source` approval record from the handoff panel, with module scope constraints and audit event.
> Governance Proof in Evidence Bundle adds `governance-proof.json/.md` to build/archive output with approval records, Safe Autopilot linkage, audit-chain verification and recent audit events.
> Governance Center UI adds buyer-visible `/approvals` and `/audit` pages for scoped approval records, approve/reject decisions, audit-chain verification, recent audit events and JSONL/JSON export.
> Commercial Offer Close Packet adds the final paid ask, one-page order, mutual action plan, buyer commitments, proof requirements and checkout gates through `/approvals`, `/audit` and `/evidence-bundle`.
> Killer Demo Commercial Close Packet projects that paid ask into `/killer-demo`, adds approval/audit checkout routes to proof paths and carries `governance-proof` in the role-aware proof packet.
> Killer Demo Procurement Handoff Sync makes `proof_packet.ready_to_forward` depend on archive plus effective procurement handoff readiness, exposes blockers/missing/review counts in API/UI/Markdown, and treats the current `rentgen-killer-demo-path.md` export as the intentional coverage for recursive `killer-demo.md`.
> Killer Demo Enterprise Evidence Profile adds buyer/enterprise depth controls to `/killer-demo/build`, optional Update/Rights/Lock/Extension evidence, Tech Journal path handoff and proof-packet priority for enterprise artifacts.
> Killer Demo One-Action Archive adds `POST /api/v1/killer-demo/archive`, merging Evidence Bundle ZIP files with the current demo markdown, `killer-demo.json`, `proof-packet.json` and `killer-demo-manifest.json` for one buyer-forwardable download.
> Killer Demo Role Packet Archive adds concise `OPEN_FIRST_KILLER_DEMO.md`, role-specific `ROLE_*.md` packets and role packet hashes into `killer-demo-manifest.json`.
> Killer Demo Archive Proof Contract exposes `proof_packet.killer_archive`, shows it in the portal Proof Packet and prepends `Killer Demo ZIP` to Commercial Close evidence requirements.
> Killer Demo Role Packet Contract adds `proof_packet.handoff[*].role_packet` and shows the exact `ROLE_*.md` filename in the portal handoff cards, aligned with archive manifest entries.
> Killer Demo Role Packet Availability adds `available_files`, `missing_files` and `availability_status` to each handoff, and role packet markdown now separates files present in the archive from files not included in the current build/profile.
> Killer Demo Role Packet Rollup adds `proof_packet.role_packet_rollup`, summary counts and a portal `Role pkts` metric so presenters see ready/partial/missing packet coverage before forwarding the buyer ZIP.
> Killer Demo Forwarding Kit Bridge surfaces Evidence Bundle `recipient_packets` in `proof_packet.forwarding_kit`, Meeting Close Receipt and Post-Demo Activation Handoff, and the portal shows the same role notes across Proof Packet, Close Receipt and Activation cards so post-demo stakeholder messages stay tied to the same role packets.
> Killer Demo Manifest Headers expose `X-Killer-Demo-Manifest`, `X-Killer-Demo-Manifest-Sha256` and `X-Killer-Demo-Manifest-Files` from the close-room ZIP download and show them in Killer Demo/Evidence Bundle UIs.
> Killer Demo Meeting Close Receipt adds `MEETING_CLOSE_RECEIPT.md/.json` to the buyer ZIP and portal, capturing accepted roles, blockers, next paid step, send files and archive verification in one post-demo purchasing artifact.
> Killer Demo Post-Demo Activation Handoff adds `POST_DEMO_ACTIVATION_HANDOFF.md/.json`, route chain, gates, invoice trigger, Day 7 proof and Day 30 outcome path so the receipt flows into paid activation instead of becoming a static archive.

Главная формула:

> 1С:Рентген = локальный control plane для 1С: конфигурация, код, метаданные, роли, запросы, тесты, релизы, инциденты, архитектура и AI-действия в одном доказательном контуре.

AI важен, но не является источником истины. Источник истины: локальный граф конфигурации, детерминированные правила, evidence, тесты, approvals и история решений.

## 1. Исследовательские выводы

### 1.1. Где сейчас болит у 1С-команд

1. Конфигурация стала больше головы команды.
   - Типовые решения, расширения, доработки, внешние обработки, обмены, регламентные задания и права живут вместе, но обычно анализируются кусками.
   - Разработчик часто видит модуль, но не видит полный blast radius: формы, регистры, роли, RLS, события, подписки, отчеты, обмены, тесты и релизы.

2. EDT/Git обещают современный процесс, но переход сложный.
   - EDT официально переносит единицу разработки в файловый проект и дает Git-подход.
   - На практике у команд остаются конфигуратор, хранилище, EDT, XML-конфликты, Git LFS, разные версии платформы и импорт крупных ERP-проектов.
   - Рынку нужен не еще один IDE, а слой, который объясняет, что происходит между этими инструментами.

3. Производительность крупных баз остается постоянной болью.
   - Запросы, временные таблицы, индексы, вложенные запросы, полные соединения, блокировки, длинные транзакции, фоновые задания, СКД, RLS и права.
   - Руководителю не нужен "список SQL", ему нужен ответ: какая операция тормозит бизнес, кто владелец, какой релиз принес, какой фикс безопасен.

4. Платформа сама по себе становится отдельным фактором риска.
   - Версии 8.3/8.5, режим совместимости, новые возможности технологического журнала/OpenMetrics, изменения поведения запросов, тестирования, интерфейса, расширений.
   - Большая боль: "можно ли обновлять платформу/типовую/расширение и что сломается?" Сейчас это часто решается опытом конкретного эксперта.

5. AI-подписки дают скорость, но не дают доверия.
   - Для 1С-клиентов код и конфигурации часто содержат коммерческую тайну, персональные данные, учетные процессы и конкурентную логику.
   - Облачный AI с помесячной оплатой воспринимается как вечный расход и риск утечки.
   - У продукта должен быть режим "без внешнего AI": анализ, gates, отчеты, evidence, тесты и value работают локально.

6. Архитекторы и директора тонут в несвязанных артефактах.
   - Требования в одном месте, код в другом, тесты отдельно, релизы в CI, инциденты в тикетах, архитектура в картинках, права в конфигурации.
   - Покупать захотят не "генератор кода", а систему, где любое изменение превращается в понятный пакет: причина, риск, impact, тесты, решение, approval, релиз, rollback.

### 1.2. Внешние опоры исследования

- Официальная архитектура 1С подчеркивает разделение платформы и прикладного решения, а также центральность метаданных. Значит, продукт должен анализировать не только BSL, а всю модель конфигурации: https://v8.1c.ru/platforma/obzor-arkhitektury-platformy/
- Документация EDT описывает переход от инфобазы как единицы разработки к проектам в файловой системе и VCS. Значит, наш продукт должен быть control plane поверх EDT/Git, а не заменой EDT: https://1c-dn.com/library/1c_enterprise_development_tools_what_is_1c_enterprise_development_tools/
- Документация 1Ci по EDT фиксирует преимущества нескольких конфигураций, разных версий платформы, файлового хранения и Git, но это же создает потребность в системной навигации и governance: https://kb.1ci.com/1C_Enterprise_Platform/1C_Enterprise_Platform_Overview/1C_Enterprise_Development_Tools/1C_Enterprise_Development_Tools/
- Сообщество прямо обсуждает проблемы хранилища, блокировки объектов, непрозрачную историю, ручное решение XML-конфликтов и сложность перехода на EDT/Git: https://habr.com/ru/companies/otus/articles/1039852/
- Есть реальные issue по медленному импорту больших ERP-конфигураций в EDT: https://github.com/1C-Company/1c-edt-issues/issues/1332
- Методические материалы 1С по крупным системам и технологическим вопросам выделяют мониторинг, производительность, блокировки, расследование проблем и эксплуатационное качество как отдельную дисциплину: https://v8.1c.ru/metod/books/61555.htm и https://v8.1c.ru/metod/books/42721.htm
- В 8.3.25 1С расширила технологический журнал, OpenMetrics, возможности временных таблиц и автоматизированного тестирования. Это готовая база для нашего "Platform Doctor": https://v8.1c.ru/platforma/news/novoe-v-platforme-8-3-25/
- Стандарты 1С отдельно описывают оптимальные условия запросов, ограничения на соединения с вложенными запросами, избыточные блокировки, минимизацию клиентского кода и требования к конфигурации: https://its.1c.ru/db/v8std
- Рынок AI coding assistants движется к подписке и usage-based модели: GitHub Copilot Business/Enterprise публично позиционируется как per-user/month и AI credits; JetBrains AI Enterprise также продается per-user/month. Это усиливает нашу ставку на локальный продукт с покупкой/лицензией и опциональным AI: https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/ и https://www.jetbrains.com/ide-services/ai-enterprise/
- Enterprise-команды опасаются утечки source code в SaaS AI и shadow AI. Это подтверждает ставку на закрытый контур, локальные индексы и управляемые политики: https://www.wwt.com/wwt-research/how-to-securely-implement-ai-coding-assistants-across-the-enterprise

## 2. Текущие слабости продукта

Эти пункты надо закрывать первыми, потому что именно они создают эффект "монстра".

### 2.1. Клиент может растеряться

Сейчас много страниц, API и сильных модулей, но нет одного понятного пути:

- что подключить первым;
- сколько времени займет анализ;
- где главный результат;
- что делать разработчику;
- что смотреть директору;
- чем отличаются quality, rentgen, management, governance, operations, EDT-MCP;
- какой сценарий demo и какой сценарий production.

Решение: роль-ориентированный стартовый экран и единый "пакет ценности" после анализа конфигурации.

### 2.2. Часть обещаний шире фактической готовности

Найденные проблемы из ревью:

- запуск backend ломается без явного JWT_SECRET;
- Dev Mode UI не работает с защищенными API, потому что кладет фиктивный `dev-token`;
- часть legacy routers не монтируется;
- Archi API имеет неверный prefix и старую Neo4j-зависимость;
- change UI не показывает `coverage` и caveat, из-за чего может визуально вернуться ложный "0 impact";
- frontend/backend расходятся по `rentgenApi.build`;
- core requirements все еще тащат тяжелые/старые зависимости, хотя позиционирование уже "локально и без внешних сервисов";
- документы местами устарели и спорят с реальным состоянием.

Решение: "truth cleanup" до любых новых вау-фич.

### 2.3. Недостает убийственных 1С-сценариев

Есть сильный граф и readiness, но пока не хватает фич, которые клиент мгновенно узнает как свою боль:

- "почему база тормозит после релиза?";
- "что сломает обновление платформы/типовой?";
- "где права дают лишний доступ?";
- "какие запросы надо переписать?";
- "какие соединения/NULL в запросах дают неверный результат?";
- "какие расширения опасны?";
- "какие тесты реально надо прогнать?";
- "можно ли выпустить сегодня?";
- "какой разработчик/подсистема несет больше риска?";
- "как франчайзи быстро оценить клиента перед продажей проекта?"

Решение: не разбрасывать фичи, а сделать 10 "сценариев-витрин", каждый с ролью, входом, результатом, evidence и next action.

## 3. Новое позиционирование

### 3.1. Не продавать как "AI для 1С"

Плохая формула:

> "У нас AI генерирует BSL".

Слабость: клиент сравнит с Copilot, Cursor, ChatGPT, JetBrains, локальными LLM и спросит про цену за токены.

Сильная формула:

> "Мы ставим внутри компании локальный Рентген 1С. Он строит карту конфигурации, находит риски, объясняет impact, выбирает тесты, готовит релизное решение и дает AI действовать только через доказательства и approvals".

### 3.2. Один продукт, разные глаза

Разработчик должен увидеть:

- что поменять;
- где риск;
- какие тесты;
- почему именно так;
- как безопасно применить через EDT/branch/MR.

Архитектор должен увидеть:

- карту подсистем;
- циклы и скрытые зависимости;
- границы модулей;
- data flow;
- права/RLS;
- platform upgrade impact;
- ADR и правила архитектуры.

Директор должен увидеть:

- можно ли выпускать;
- сколько риска в релизе;
- где bottleneck;
- как это снижает аварии и ручную экспертизу;
- почему это покупка локального актива, а не вечная подписка на внешнюю магию.

Франчайзи/вендор должен увидеть:

- быструю оценку клиента;
- портфель конфигураций;
- фабрику обновлений;
- коммерческие отчеты до внедрения;
- способ продавать аудит, сопровождение и модернизацию быстрее.

Эксплуатация должна увидеть:

- инцидент -> релиз -> код -> запрос -> блокировка;
- техжурнал и OpenMetrics как понятный RCA;
- рекомендации по платформе/кластеру/СУБД;
- rollback/readiness.

ИБ/комплаенс должны увидеть:

- локальность;
- audit trail;
- approvals;
- risky operations;
- секреты;
- права;
- отчетность.

## 4. UX-анти-монстр: как клиент не должен потеряться

### 4.1. Первый экран

Первый экран не должен быть landing page и не должен быть dashboard из 30 карточек.

Он должен отвечать на три вопроса:

1. Что вы хотите проверить?
2. Кто вы сегодня?
3. Где ваша конфигурация?

Структура:

- верхняя строка: `1С:Рентген`, статус локального контура, текущая конфигурация;
- центр: один большой вход `Подключить конфигурацию` и рядом `Открыть демо`;
- ниже: 6 ролевых режимов:
  - Разработчик;
  - Архитектор;
  - Руководитель;
  - QA/релиз;
  - Эксплуатация;
  - Франчайзи/вендор.

После выбора роли продукт меняет язык, а не скрывает функции.

### 4.2. Первый результат за 5 минут

После подключения конфигурации клиент должен получить не "индекс завершен", а:

- общий score;
- 5 самых дорогих рисков;
- 3 быстрые победы;
- 1 релизный риск;
- 1 производительный риск;
- 1 архитектурный риск;
- какие данные покрыты, а какие еще не подключены;
- кнопка `Собрать отчет для роли`.

Запрещено показывать "0 impacted", если покрытие неполное. Всегда показывать coverage/caveat.

### 4.3. Навигация

Сократить верхний уровень до 9 пунктов:

1. Главная.
2. Конфигурации.
3. Риски.
4. Изменения.
5. Тесты.
6. Релизы.
7. Архитектура.
8. Эксплуатация.
9. AI-штаб.

Администрирование, интеграции, users, policies, API keys, data sources - в отдельный системный раздел, не в основной рабочий поток.

### 4.4. Язык интерфейса

Не писать:

- "artifact graph matrix";
- "governance evidence";
- "MCP toolsets";
- "coverage score partial".

Писать:

- "что связано";
- "почему риск";
- "что проверить";
- "можно выпускать";
- "данных недостаточно";
- "требуется подтверждение";
- "действие опасное";
- "отчет для директора";
- "отчет для разработчика".

Под капотом могут оставаться graph, MCP, governance, policy engine.

## 5. Десять фич, ради которых захотят купить

### 5.1. Configuration Genome

Полная генетическая карта конфигурации:

- объекты метаданных;
- модули;
- процедуры/функции;
- формы;
- команды;
- роли/RLS;
- регистры;
- документы;
- отчеты/СКД;
- запросы;
- обмены;
- подписки на события;
- регламентные задания;
- расширения;
- внешние обработки;
- версии платформы и режимы совместимости.

Результат: архитектор впервые видит конфигурацию как систему, а не как дерево объектов.

### 5.2. Impact Oracle

Ответ на вопрос: "что сломается, если я изменю это?"

Вход:

- модуль/процедура/объект;
- diff;
- issue;
- requirement;
- расширение;
- обновление типовой;
- обновление платформы.

Выход:

- affected modules;
- affected metadata;
- forms;
- roles/RLS;
- queries;
- tests;
- релизы;
- owners;
- риск ложного нуля;
- coverage/caveat.

### 5.3. Query Surgeon

1C query doctor:

- NULL в левом соединении;
- необходимость `Есть NULL` / `ЕстьNULL` / внутреннего соединения;
- соединения с вложенными запросами;
- разыменование составных ссылок;
- полное внешнее соединение;
- условия не по индексам;
- запросы в цикле;
- временные таблицы и индексы;
- СКД-риски;
- RLS-влияние на запрос.

Выход:

- найденная проблема;
- объяснение на 1С-языке;
- безопасный rewrite;
- риск изменения результата;
- unit/behavior test;
- ссылка на стандарт/правило.

### 5.4. Lock Radar

Status 2026-06-19: v1 реализован как `src/services/rentgen/lock_radar.py`, `POST /api/v1/lock-radar/analyze`
и страница `/lock-radar`. Покрывает `TLOCK`/`TTIMEOUT`/`TDEADLOCK`, affected modules, impact/test gaps,
actions/runbook и опциональное включение в Evidence Bundle.

RCA блокировок:

- TLOCK/TDEADLOCK/TTIMEOUT;
- длинные транзакции;
- порядок записи документов;
- регистры и наборы записей;
- регламентные задания;
- фоновые обмены;
- SQL wait patterns;
- связь с релизом и кодом.

Выход:

- "кто с кем конфликтует";
- какая операция бизнеса страдает;
- какой код/запрос вызывает;
- что переписать;
- какой тест/нагрузочный сценарий нужен.

### 5.5. Platform Doctor

Диагностика платформы и окружения:

- версия платформы;
- режим совместимости;
- клиент/сервер;
- кластер;
- СУБД;
- технологический журнал;
- OpenMetrics;
- license events;
- web/thin/mobile clients;
- extensions compatibility;
- known release changes;
- 8.3 -> 8.5 readiness.

Выход:

- "можно обновляться";
- "что проверить перед обновлением";
- "какие платформенные возможности можно использовать";
- "какие старые настройки мешают";
- "что опасно для производительности".

### 5.6. Update War Room

Фабрика обновлений:

- типовая конфигурация;
- доработанная конфигурация;
- расширения;
- vendor release;
- comparison/merge;
- support status;
- direct modifications;
- conflict explanation;
- test selection;
- release readiness.

Это фича для руководителей и франчайзи: меньше ручного героизма при обновлениях.

### 5.7. Rights & RLS Simulator

Проверка прав:

- кто видит лишнее;
- кто не видит нужное;
- где RLS ломает запрос;
- где роль дает опасную команду;
- где изменения формы открыли доступ;
- где external processing/tool может обойти контроль.

Выход:

- матрица роль -> объект -> действие;
- diff прав между релизами;
- security gate;
- evidence для ИБ.

### 5.8. Test Factory

Изменение автоматически превращается в тест-план:

- affected unit tests;
- affected Vanessa scenarios;
- manual checks;
- smoke suite;
- regression suite;
- test data needs;
- missing tests;
- generated test skeletons.

Результат: QA и разработчик не спорят "что прогонять"; продукт показывает почему.

### 5.9. Safe Autopilot

AI может действовать, но только через контур:

1. Понять задачу.
2. Собрать контекст.
3. Составить план.
4. Оценить impact.
5. Предложить diff.
6. Выбрать тесты.
7. Прогнать проверки.
8. Сформировать evidence.
9. Попросить approval для write/apply/deploy.

Никаких скрытых изменений в продуктиве. Это и продается как доверие.

### 5.10. Vendor Portfolio Cockpit

Для франчайзи/вендоров:

- список клиентов/конфигураций;
- health score;
- update readiness;
- технический долг;
- риски релиза;
- SLA/инциденты;
- оценка стоимости модернизации;
- pre-sale audit report;
- пакет коммерческого предложения.

Это превращает продукт из инструмента команды в источник выручки для партнеров.

## 6. Автономная программа реализации

### Волна 0. Правда, запуск и доверие

Срок: 3-5 дней.

Цель: убрать то, что ломает первое впечатление.

Работы:

1. Исправить локальный запуск:
   - `scripts/start_rentgen.ps1` задает безопасный dev JWT_SECRET, ENVIRONMENT=development или явно подсказывает;
   - backend не падает на тестовом/import-time сценарии;
   - health для liveness не дергает тяжелые внешние проверки.

2. Исправить Dev Mode:
   - либо выдавать настоящий short-lived dev JWT;
   - либо отключить Dev Mode для protected pages;
   - protected pages не должны показывать пустоту/401 без объяснения.

3. Закрыть false-zero:
   - change UI показывает `coverage`, `impact_measured`, `coverage_caveat`;
   - нули всегда сопровождаются "измерено" или "данных недостаточно".

4. Привести README/hand-off к реальности:
   - coverage 92%, не 100%;
   - pilot-ready, не production-complete;
   - что работает offline;
   - что optional.

5. Починить obvious API contracts:
   - `rentgenApi.build` GET/POST;
   - Archi prefix;
   - legacy routers либо помечены archived, либо реально монтируются.

Acceptance:

- `start_rentgen.ps1` поднимает продукт на чистой машине с понятным dev-профилем;
- frontend build проходит;
- focused backend tests проходят без ручного шаманства;
- smoke по protected pages проходит с dev login;
- change page не показывает опасный silent zero.

### Волна 1. Анти-монстр UX и демо-путь

Срок: 1-2 недели.

Цель: клиент понимает продукт за 30 секунд и получает результат за 5 минут.

Работы:

1. Новый Home/Workbench:
   - выбор роли;
   - подключить конфигурацию;
   - открыть демо;
   - последние анализы;
   - top risks;
   - "что делать дальше".

2. Demo dataset/story:
   - "ERP с тормозящим заказом";
   - "опасный LEFT JOIN без ЕстьNULL";
   - "изменение документа влияет на проведение и отчеты";
   - "обновление платформы требует проверки";
   - "права открывают лишний доступ";
   - "релиз нельзя выпускать без теста".

3. Role reports:
   - developer report;
   - architect report;
   - director report;
   - QA/release report;
   - ops report;
   - vendor audit report.

4. Навигация:
   - верхний уровень сократить;
   - MCP, raw APIs, internal governance убрать из главной витрины;
   - каждая страница начинается с ответа "что важно сейчас".

Acceptance:

- человек без инструкции может открыть демо и понять 3 главные ценности;
- директор видит go/no-go и деньги/риск;
- разработчик видит конкретную строку/модуль/тест;
- архитектор видит карту связей;
- UI не похож на набор лабораторных страниц.

### Волна 2. Configuration Intake Wizard

Срок: 2 недели.

Цель: продукт принимает реальную конфигурацию клиента без консультации разработчика продукта.

Источники:

- EDT project;
- Git repo;
- выгрузка XML;
- `.cf/.dt` через adapter;
- live infobase metadata export;
- extensions;
- external reports/processings;
- tech journal;
- test results;
- CI artifacts.

Работы:

1. Wizard:
   - выбрать источник;
   - проверить доступ;
   - показать что будет проиндексировано;
   - оценить время;
   - запустить;
   - показать coverage.

2. Incremental index:
   - snapshot;
   - diff;
   - rebuild only changed;
   - failed import diagnostics.

3. Coverage model:
   - code coverage of graph, not test coverage;
   - metadata coverage;
   - forms coverage;
   - rights coverage;
   - query coverage;
   - test coverage;
   - platform/ops coverage.

Acceptance:

- можно подключить минимум EDT/Git project;
- ошибки импорта объясняются человечески;
- после анализа видно, что покрыто и чего не хватает;
- API и UI не позволяют принять неполное покрытие за полный вывод.

### Волна 3. Deep 1C Pain Engines

Срок: 4-6 недель.

Цель: закрыть боли, которые узнает каждый сильный 1С-специалист.

Эпики:

1. Query Surgeon:
   - parser/extractor запросов из BSL и СКД;
   - правила NULL/ЕстьNULL/внутреннее соединение;
   - вложенные запросы в соединениях;
   - составные ссылки;
   - FULL OUTER JOIN;
   - индексные условия;
   - временные таблицы;
   - query rewrite suggestion;
   - regression test proposal.

2. Lock Radar:
   - import tech journal;
   - parse TLOCK/TDEADLOCK/TTIMEOUT;
   - correlate with modules/procedures;
   - show blocking graph;
   - propose code/query/transaction fixes.

3. Rights & RLS Simulator:
   - role/object/action matrix;
   - RLS query impact;
   - diff rights between snapshots;
   - risky privilege detection;
   - security report.

4. Extension Safety:
   - Status 2026-06-19: v1 реализован как `src/services/rentgen/extension_safety.py`, `POST /api/v1/extension-safety/analyze` и страница `/extension-safety`;
   - extension points;
   - borrowed objects;
   - overridden forms/commands;
   - conflict with updates;
   - support status.

5. Dead Code & Hotspot 2.0:
   - quality score by subsystem;
   - ownership;
   - trend;
   - cost/risk priority, not just count.

Acceptance:

- каждый engine имеет 1 demo case;
- каждый finding имеет evidence, severity, owner, suggested action;
- findings link to standards/local rules;
- top risks агрегируются в role reports.

### Волна 4. Platform Doctor

Срок: 3-4 недели.

Цель: закрыть самую дорогую боль - платформа, производительность, обновления и эксплуатация.

Работы:

1. Platform inventory:
   - platform version;
   - compatibility mode;
   - client/server;
   - cluster;
   - DBMS;
   - extensions;
   - web/mobile/thin usage;
   - license/log signals.

2. Release knowledge:
   - локальная база release notes;
   - правила для 8.3.x/8.5.x;
   - known changes mapped to config features.

3. OpenMetrics/tech journal:
   - import metrics;
   - baseline;
   - anomalies;
   - incident correlation.

4. Upgrade simulator:
   - current -> target platform;
   - affected mechanisms;
   - required checks;
   - tests;
   - rollout plan.

Acceptance:

- product can answer "можно ли обновлять платформу?";
- answer includes coverage and caveats;
- ops/director report includes business-level risk;
- no internet required after local knowledge bundle installed.

### Волна 5. Test Factory и Release Confidence

Срок: 3-5 недель.

Цель: релиз перестает быть верой.

Работы:

1. Test inventory:
   - YAxUnit;
   - Vanessa;
   - 1C automated testing;
   - manual test cases;
   - smoke/regression tags.

2. Affected tests:
   - trace from change to tests;
   - confidence score;
   - missing tests;
   - recommended manual checks.

3. Evidence:
   - test run import;
   - logs/screenshots/artifacts;
   - hash manifest;
   - trend and flaky history.

4. Release Confidence:
   - go/no-go;
   - waived risks;
   - untested affected areas;
   - rollback readiness;
   - director summary.

Acceptance:

- one change set produces test plan automatically;
- release report can be shown директору/QA/ИБ;
- no release page says "pass" if impacted tests are missing.

### Волна 6. Safe Autopilot

Срок: 4-6 недель.

Цель: дать горящие глаза разработчику, но не напугать ИБ и директора.

Работы:

1. Agent cockpit:
   - Ask;
   - Plan;
   - Impact;
   - Diff;
   - Tests;
   - Evidence;
   - Approval.

2. EDT-MCP/live tools:
   - read-only default;
   - write tools require approval;
   - execute tools require explicit actor/reason/scope;
   - audit every call.

3. Patch generator:
   - query fixes;
   - tests;
   - documentation;
   - small refactors;
   - no direct production write.

4. Local model strategy:
   - local RAG;
   - optional local LLM;
   - optional external LLM proxy with budget and redaction;
   - deterministic fallback always available.

Acceptance:

- developer can ask "исправь риск NULL в запросе" and gets safe plan+diff+test;
- dangerous action cannot run without approval;
- product still useful with AI disabled;
- every AI answer cites local evidence.

### Волна 7. Vendor Portfolio и коммерческая упаковка

Срок: 3-4 недели.

Цель: продукт становится покупкой, а не экспериментом.

Работы:

1. Portfolio mode:
   - organizations;
   - clients;
   - configurations;
   - snapshots;
   - risk trend;
   - update readiness;
   - SLA/incidents;
   - commercial audit reports.

2. Packs:
   - Developer Pack;
   - Architect Pack;
   - Release/QA Pack;
   - Platform Doctor Pack;
   - Vendor Portfolio Pack;
   - Enterprise Offline Pack.

3. Reports:
   - pre-sale audit;
   - modernization estimate;
   - platform upgrade estimate;
   - release risk;
   - support risk;
   - technical debt money map.

4. Licensing:
   - per installation / per configuration / per portfolio;
   - no mandatory token subscription;
   - AI credits optional only for external/cloud AI;
   - local AI appliance as premium option.

Acceptance:

- франчайзи может просканировать клиента и получить коммерческий отчет;
- директор видит ROI в снижении аварий, ручного анализа и подписочных расходов;
- pricing story does not depend on "сколько токенов сгорело".

### Волна 8. Enterprise hardening

Срок: 6-10 недель параллельно.

Работы:

1. Signed offline bundle:
   - installer;
   - SBOM;
   - hashes;
   - offline docs;
   - upgrade/rollback.

2. Storage hardening:
   - JSON stores behind contracts now;
   - DB-backed hot paths later;
   - migration path;
   - backups.

3. IAM:
   - OIDC/SAML;
   - LDAP/SCIM;
   - groups -> roles;
   - tenant/project boundaries;
   - SoD policies.

4. Audit:
   - append-only;
   - hash chain;
   - SIEM export;
   - retention.

5. Performance:
   - large config benchmarks;
   - incremental indexing;
   - memory budgets;
   - portal code splitting.

Acceptance:

- product can be installed in closed contour;
- security team has whitepaper and audit evidence;
- large configuration analysis has benchmark and progress UI;
- no hidden external dependency in baseline mode.

## 7. Immediate autonomous backlog

Не ждать уточнений. Брать в таком порядке.

### P0

1. Done 2026-06-19: Fix local launch and dev auth.
2. Done 2026-06-19: Fix change impact caveat in UI and downstream release/testing surfaces.
3. Done 2026-06-19: Fix README/HANDOFF truth mismatch.
4. Done 2026-06-19: Fix Archi prefix/status; keep as legacy optional outside Neo4j-free core.
5. Done 2026-06-19: Fix frontend/backend `rentgenApi.build` mismatch.
6. Done 2026-06-19: Split core vs optional dependencies.
7. Done 2026-06-19: Create new role-based home/workbench.
8. Done 2026-06-19: Add demo mode with one complete story.

### P1

1. Done 2026-06-19 v1: Configuration Intake Wizard for EDT/Git.
2. Done 2026-06-19 v1: Coverage/caveat model via shared Coverage Ledger and downstream false-safe-zero guards.
3. Query Surgeon v1 with NULL/ЕстьNULL and dangerous joins.
   Done 2026-06-19 v1: Query Surgeon is implemented through standards review with NULL/ЕстьNULL and dangerous join findings.
4. Done 2026-06-19 v1: Platform Doctor inventory.
5. Done 2026-06-19 v1: Test Factory affected test plan + missing tests.
6. Done 2026-06-19 v1: Director report.
7. Done 2026-06-19 v1: Developer report.
8. Done 2026-06-19 v1: Vendor audit report.

### P2

1. Done 2026-06-19 v1: Tech journal import and Lock Radar.
2. Done 2026-06-19 v1: Rights/RLS diff in analyzer/API/UI.
3. Done 2026-06-19 v1: Update War Room.
4. Done 2026-06-19 v1: Safe Autopilot Ask/Plan/Impact/Diff.
5. Done 2026-06-19 v1: Signed offline bundle skeleton.
6. Done 2026-06-19 v1: Portfolio mode.

## 8. Product metrics

Критерии, по которым продукт можно считать "клиент хочет купить".

1. Time to understand: до 30 секунд.
2. Time to first value: до 5 минут на demo, до 15 минут на реальной средней конфигурации.
3. False-safe-zero: 0 случаев. Любой ноль имеет coverage/caveat.
4. Offline value: минимум 80% витрин работают без внешнего AI.
5. Role fit: у каждой роли есть один главный отчет и один главный next action.
6. Evidence-first: любой риск имеет источник, affected scope и suggested action.
7. Safe action: любой write/apply/execute имеет approval/audit.
8. Demo close rate: после demo клиент может назвать минимум 3 свои боли, которые продукт закрыл.
9. Director value: есть отчет "что это экономит/снижает" без технического погружения.
10. Developer delight: есть сценарий, где продукт нашел конкретную ошибку в запросе и предложил безопасный fix+test.

## 9. Что не строить сейчас

1. Еще один общий чат без привязки к конфигурации.
2. Большой маркетинговый landing вместо рабочего продукта.
3. Облачный-only режим.
4. Автоматическое изменение продуктивной базы.
5. Красивые графики без actionable next step.
6. Роутеры/страницы, которые существуют только для галочки.
7. "100% coverage", если есть partial/unknown.
8. Новые тяжелые зависимости в baseline profile.
9. Собственные низкоуровневые аналоги EDT/BSL LS/YAxUnit/Vanessa, если можно интегрироваться.
10. AI-функции, которые не могут объяснить evidence.

## 10. Северная звезда

Клиент должен выйти из demo с мыслью:

> "Это не подписка на чужой AI. Это мой локальный центр управления 1С. Он знает мою конфигурацию, мои релизы, мои риски, мои тесты и мою платформу. AI тут не болтает, а работает под контролем доказательств".

Когда это почувствуют одновременно разработчик, архитектор, директор, QA, эксплуатация и франчайзи, продукт станет не "интересным инструментом", а покупкой, которую защищают внутри компании.
