# 1cAI Admin Guide

## Daily Checks

- Open `/workbench`.
- Review enterprise readiness findings.
- Review recent audit events.
- Review failed policy evaluations and waivers.
- Review failed or warning test runs.

## Governance Stores

- Artifact graph: `data/artifact_graph.json`
- Change sets: `data/change_sets.json`
- Policy evaluations: `data/policy_evaluations.json`
- Waivers: `data/policy_waivers.json`
- Test runs: `data/test_runs.json`
- Canonical metadata: `data/canonical_metadata.json`
- Audit log: `data/audit_log.ndjson`

## Operational Rules

- Treat write/run/release actions as risky.
- Require review pack or explicit approval for high-risk delivery.
- Keep waivers temporary and remediation-backed.
- Use metadata drift and rights diff before release.
- Keep evidence bundles for CI and release gates.
