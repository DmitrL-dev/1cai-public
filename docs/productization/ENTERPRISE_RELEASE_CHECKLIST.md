# 1cAI Enterprise Release Checklist

## Required

- Artifact graph health is ok.
- Requirements have implementation and verification coverage.
- Change sets have impact analysis.
- Test evidence is stored and has no failed runs for the release scope.
- Policy evaluations are pass or explicitly waived.
- Metadata drift and rights diff are reviewed.
- Audit events exist for key gate decisions.
- Enterprise IAM readiness has no high findings.
- Backup is taken before release.

## Evidence Links

- `/api/v1/artifacts/health`
- `/api/v1/artifacts/matrix`
- `/api/v1/policies/evaluations`
- `/api/v1/testing/runs`
- `/api/v1/metadata/canonical-snapshots`
- `/api/v1/audit/events`
- `/api/v1/enterprise/iam/readiness`
