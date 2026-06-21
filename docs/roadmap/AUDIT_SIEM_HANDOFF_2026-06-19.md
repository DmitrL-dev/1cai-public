# Audit SIEM Handoff

Date: 2026-06-19.

Product audit proof now has a SIEM-ready handoff without pretending that live customer SOC streaming is already wired.

## Implemented

- Service export: `audit_log.export_siem_events(...)`.
- API: `GET /api/v1/audit/siem-export?format=jsonl|json&limit=...`.
- SIEM schema: `rentgen.audit.siem.v1`.
- Export includes normalized event fields, actor, target, correlation id, Rentgen audit id, `prev_hash`, chain-valid field, ingestion hints and `content_sha256`.
- Portal `/audit` adds a `SIEM` download button next to JSONL/JSON.
- Governance Proof now includes `siem_handoff`: endpoint, route, schema, recommended filename, event count, chain validity and export SHA-256.

## Buyer Value

Security and procurement can receive a SOC-friendly audit file and verify that the product audit chain was valid when the export was generated.

This is deliberately a handoff, not a claim of live SIEM streaming. Customer-specific Splunk/Elastic/MaxPatrol/etc. connectors remain adapter work.

## Verification

- `python -m py_compile src/services/audit_log.py src/api/audit_api.py src/services/rentgen/evidence_bundle.py tests/unit/test_product_audit_log.py tests/unit/test_evidence_bundle.py`
- `python -m pytest tests/unit/test_product_audit_log.py tests/unit/test_evidence_bundle.py -q`
- `npm run build`
