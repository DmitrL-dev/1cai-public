# Governance Center UI

Date: 2026-06-19.

Approval workflow and audit-chain APIs now have buyer-visible portal pages instead of living only in Swagger or Evidence Bundle exports.

## Implemented

- Portal route: `/approvals`
  - Lists EDT-MCP approval records.
  - Filters by status.
  - Creates scoped `edt_mcp_call` approval requests.
  - Approves or rejects requested records through authenticated API calls.
  - Shows linked record and argument constraints.
- Generic approval API now writes product audit events for requested, approved and rejected decisions.
- Portal route: `/audit`
  - Shows audit-chain verification: valid, total, chained, legacy and broken counts.
  - Lists recent audit events with actor, action, category, outcome, target and id.
  - Filters by actor/action/category/target.
  - Exports JSONL/JSON audit evidence.
  - Exports SIEM-ready JSONL through `/api/v1/audit/siem-export`.
- Sidebar navigation: Trust & Ops now includes Approvals and Audit Log.
- Home adds Approvals and Audit Log fast entries, plus director/QA role actions.
- Evidence Bundle Governance Proof now routes to `/approvals`.

## Buyer Value

1. Security sees the approval and audit controls as a product surface, not hidden backend plumbing.
2. Developers can create and inspect scoped approval records without touching Swagger.
3. Architects can verify the audit hash-chain before sharing a proof archive.
4. Directors see that governance is operational in the product, not just promised in a whitepaper.

## Verification

- `npm run build`
- `python -m py_compile src/services/rentgen/evidence_bundle.py src/api/evidence_bundle_api.py src/api/approval_api.py src/api/audit_api.py`
- Live API smoke: `/api/v1/approvals`, `/api/v1/audit/verify`, `/api/v1/audit/events`.
- SIEM smoke: `/api/v1/audit/siem-export?format=jsonl` returns `schema: rentgen.audit.siem.v1` and `content_sha256`.
- Live create smoke: `POST /api/v1/approvals/edt-mcp` creates an `approval.requested` audit event and keeps audit-chain valid.
- Live route smoke: `/approvals` and `/audit` return 200 on the running portal at `http://127.0.0.1:3001`.

## Caveat

`agent-browser` daemon failed to start in this local Windows session, so browser snapshots were unavailable. HTTP route checks and production build passed.
