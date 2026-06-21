# Governance Proof in Evidence Bundle

Date: 2026-06-19.

Evidence Bundle now includes a governance proof artifact that ties Safe Autopilot approval requests to the tamper-evident product audit log.

## Implemented

- Backend artifact builder: `build_governance_proof(...)` in `src/services/rentgen/evidence_bundle.py`.
- Evidence Bundle option: `include_governance_proof`, enabled by default.
- API request field: `include_governance_proof`.
- UI toggle: `/evidence-bundle` -> `Governance proof`.
- Artifact route: `/approvals`.
- Archive content: `governance-proof.json` and `governance-proof.md`.
- Tests: `tests/unit/test_evidence_bundle.py`.

## What It Proves

- Recent approval records with actor, tool, risk, linked Safe Autopilot plan and argument constraints.
- Approval status counts: requested, approved, rejected, used and expired.
- Audit-chain verification from `audit_log.verify_chain()`.
- Recent audit events with actor/action/category/outcome and hash linkage.
- SIEM handoff with `/api/v1/audit/siem-export`, schema, recommended filename, chain-valid status and export SHA-256.
- Controls for write approval, separation of duties, tamper-evident audit and portable proof pack.

## Buyer Value

1. A developer can show that a risky write request is scoped before any apply path exists.
2. An architect or security reviewer can verify audit integrity from the same proof archive.
3. A director sees that Rentgen is not just producing advice: it records decisions, actors, scope and evidence.
4. Procurement receives a portable ZIP with JSON/Markdown proof and SHA-256 manifest entries.

## Verification

- `python -m py_compile src/services/rentgen/evidence_bundle.py src/api/evidence_bundle_api.py`
- `python -m pytest tests/unit/test_evidence_bundle.py -q`
- `npm run build`
- Live smoke: authenticated `POST /api/v1/evidence-bundle/build` and `/archive` include `governance-proof.json/.md`; archive response returns `X-Archive-Sha256`.
