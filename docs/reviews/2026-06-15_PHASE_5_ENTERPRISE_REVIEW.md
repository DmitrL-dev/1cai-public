# Phase 5 Enterprise IAM Review

Date: 2026-06-15

## Scope Reviewed

- Service: `src/services/enterprise_iam.py`
- API: `src/api/enterprise_api.py`
- Router mount: `src/app/routers.py`
- Audit integration: `src/services/audit_log.py`
- Tests: `tests/unit/test_enterprise_iam.py`, `tests/unit/test_product_audit_log.py`

## Findings

1. Medium: OIDC/SAML/LDAP/SCIM are modeled and validated but not performing live protocol handshakes yet. This is intentionally an internal readiness/config layer, not a customer-specific IdP integration.
2. Medium: access checks accept roles/permissions as request payload in the current API tests. Production endpoints should bind them from authenticated `CurrentUser`.
3. Medium: project boundaries are JSON-backed. Large multi-tenant deployments should move this to DB-backed policy storage.
4. Low: no UI yet for enterprise readiness and project boundary administration.

No blocking defects were found in the completed IAM readiness slice.

## Product Fit

The slice improves enterprise readiness without depending on external BA or IdP products:

- IAM config validates local JWT, service-token, OIDC, SAML, LDAP and SCIM provider declarations.
- Readiness report highlights default JWT secret, missing service tokens, disabled federation and missing project boundaries.
- Project/tenant boundaries define allowed roles, permissions and data roots.
- Access-check gives deterministic allowed/denied decisions for project-scoped actions.
- IAM config and boundary changes emit product audit events.

This helps leadership and admins see what is ready for enterprise rollout and what must be configured during paid customer implementation.

## Enterprise Readiness

- Offline/on-prem: local JSON config.
- Governance: boundaries can be used by future write/run/import actions.
- Audit: config and boundary writes are logged.
- Integration posture: OIDC/SAML/LDAP/SCIM are declared as adapters, not hard dependencies.
- Remaining work: auth-bound actor enforcement, DB storage and actual IdP handshake adapters.

## Test Evidence

Command executed:

```powershell
C:\Python311\python.exe -m pytest tests\unit\test_enterprise_iam.py tests\unit\test_product_audit_log.py -q
```

Result: 7 passed.

## Residual Risk

The IAM slice is ready as an internal readiness and boundary-governance layer. It is not yet a complete enterprise identity federation implementation.

## Next Actions

1. Bind enterprise API actor/roles/permissions to authenticated `CurrentUser`.
2. Add OIDC discovery/JWKS validation and SAML metadata validation.
3. Enforce project boundaries on risky metadata/test/EDT-MCP actions.
4. Add UI for readiness findings and boundary administration.
