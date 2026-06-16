# 1cAI Upgrade Guide

## Pre-Upgrade

1. Back up `data/`, `policy/` and runner profiles.
2. Export audit log.
3. Record current `/api/v1/enterprise/iam/readiness`.
4. Run focused unit tests for active governance areas.

## Upgrade

1. Deploy backend code.
2. Deploy portal build.
3. Keep old local stores unless migration notes require transformation.
4. Rebuild Rentgen store only when input call graph or schema changes.

## Post-Upgrade

1. Run smoke checks.
2. Open `/workbench`.
3. Validate policy evaluations still load.
4. Validate latest metadata snapshot and drift.
5. Run a dry-run test runner plan.

## Rollback

Restore the previous code bundle and matching `data/` backup. Do not mix new stores with old code unless a migration is explicitly documented.
