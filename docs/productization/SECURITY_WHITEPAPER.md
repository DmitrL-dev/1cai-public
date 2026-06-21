# 1cAI Security Whitepaper

## Security Model

1cAI separates deterministic product truth from optional AI acceleration.

- Truth layer: local artifacts, metadata snapshots, policy evaluations, test evidence, approvals, waivers and audit log.
- AI layer: can propose, explain and draft, but cannot be the only evidence source for gates.

## Controls

- JWT/RBAC baseline.
- Service tokens for CI and integrations.
- Enterprise IAM readiness for OIDC, SAML, LDAP and SCIM configuration.
- Project/tenant boundaries for scoped actions.
- Policy-as-code gates for impact, tests, release, security and standards.
- Dry-run default for external test runner execution.
- Tamper-evident hash-chain audit events for artifact, policy, testing, metadata, IAM and agentic workflows.
- Audit verification endpoint: `GET /api/v1/audit/verify`.

## Current Gaps

- Live SIEM streaming is not implemented yet; export and hash-chain verification are local.
- Live OIDC/SAML handshakes are adapter-ready, not fully implemented.
- Path boundaries must be enforced before broad file import/run features are exposed to untrusted users.

## Deployment Requirements

- Replace default JWT secret.
- Disable demo users in production.
- Configure service tokens.
- Restrict filesystem access for runner/import endpoints.
- Back up local JSON/NDJSON stores.
