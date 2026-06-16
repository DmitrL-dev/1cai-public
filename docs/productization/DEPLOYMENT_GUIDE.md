# 1cAI Deployment Guide

## Baseline On-Prem Profile

1. Install Python 3.11 and Node 20+.
2. Install project dependencies.
3. Build Rentgen store when call graph data is available.
4. Build the portal with `npm run build` in `portal`.
5. Start the backend with the existing FastAPI entrypoint.
6. Serve the portal through the existing web server or Vite preview for local validation.

## Required Local Data

- `data/rentgen.db` for whole-configuration impact.
- `data/artifact_graph.json` for internal ALM traceability.
- `data/audit_log.ndjson` for product audit events.
- `data/canonical_metadata.json` for metadata snapshots.
- `data/test_runs.json` for test evidence.

## Configuration

- Set a non-default JWT secret before production.
- Configure service tokens for CI and internal integrations.
- Configure runner profiles for YAxUnit, Vanessa and 1C:Tester per customer environment.
- Keep external adapters optional unless customer contract includes them.

## Smoke Checks

- `GET /api/v1/artifacts/health`
- `GET /api/v1/audit/events`
- `GET /api/v1/enterprise/iam/readiness`
- `GET /api/v1/testing/runners`
- Portal route `/workbench`
