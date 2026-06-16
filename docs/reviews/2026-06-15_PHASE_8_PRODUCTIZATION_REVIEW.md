# Phase 8 Productization Review

Date: 2026-06-15

## Scope Reviewed

- Productization docs: `docs/productization/SUPPORT_MATRIX.md`, `DEPLOYMENT_GUIDE.md`, `SECURITY_WHITEPAPER.md`, `ADMIN_GUIDE.md`, `BACKUP_RESTORE.md`, `UPGRADE_GUIDE.md`, `ADAPTER_GUIDE.md`, `ENTERPRISE_RELEASE_CHECKLIST.md`.
- Service: `src/services/productization_readiness.py`.
- API: `src/api/productization_api.py`.
- Router mount: `src/app/routers.py`.
- MCP: `productization_readiness` tool in `src/ai/mcp/server.py`.
- Tests: `tests/unit/test_productization_readiness.py`.

## Findings

### Medium

- `signed-offline-installer-missing`: Packaging docs now exist, but this slice does not build a signed offline installer or immutable artifact bundle. This is a release engineering follow-up, not a blocker for pilot readiness.
- `live-iam-handshakes-unverified`: Enterprise IAM readiness validates local config and boundaries, but OIDC/SAML/LDAP/SCIM live handshakes need customer or staging IdP validation.
- `external-runner-execution-unverified`: Test runner adapters are safe by default and support evidence import, but live YAxUnit/Vanessa/1C runner execution must be validated on a real Windows/1C runner.

### Low

- `audit-hash-chain-missing`: Audit is append-only NDJSON; hash chaining and SIEM streaming are still planned hardening.
- `json-store-scale-limit`: JSON stores are good for the control-plane skeleton and offline portability, but hot enterprise paths should move to database-backed storage.

## Product Fit

Phase 8 turns packaging from static docs into a machine-readable product readiness layer. This is useful for leadership, implementation teams, sales engineering and internal release owners because they can check whether the product is pilot-ready without opening every document manually.

The layer is intentionally deterministic and works without an LLM. It checks docs, strategy artifacts, governance services, test coverage files and review evidence, then returns `pass`, `warn` or `fail` with explicit residual gaps.

## Enterprise Readiness

- Offline/on-prem posture is represented in the support matrix and deployment/security docs.
- Governance, policy, audit, IAM, test evidence and agentic guardrails are part of the deliverable map.
- Known gaps are not hidden: installer signing, live IAM, live external runner execution and audit hardening remain visible warnings.
- The API can be used by UI, CI, release managers and MCP clients.

## Test Evidence

Command:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_productization_readiness.py -q
```

Result:

- 5 passed.
- 1 existing pytest-asyncio fixture deprecation warning.
- Existing RequestsDependencyWarning about urllib3/chardet mismatch.

## Residual Risk

The productization readiness score is not a legal certification or production acceptance test. It is a deterministic release-readiness control plane. Real customer production readiness still requires environment-specific validation: IdP integration, runner installation, backup restore drill, SIEM export, offline bundle signing and performance testing on the target 1C landscape.

## Next Actions

1. Build signed offline bundle manifest and installer profile.
2. Add hash-chained audit export and SIEM streaming adapter.
3. Add staging profiles for OIDC/SAML/LDAP/SCIM handshake tests.
4. Add real-runner smoke suites for YAxUnit, Vanessa and 1C:Tester.
5. Move high-volume JSON stores to DB-backed implementations behind the same service contracts.
