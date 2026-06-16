# 1cAI Backup And Restore

## Backup Scope

Back up these paths together:

- `data/*.json`
- `data/*.ndjson`
- `data/*.db`
- `data/test_evidence_bundles/`
- `policy/`
- customer runner profile files

## Backup Frequency

- Development: daily.
- Active enterprise delivery: before each release gate and at least hourly during CI windows.
- Regulated environments: align with customer retention policy.

## Restore Procedure

1. Stop backend and runner processes.
2. Restore `data/` and `policy/` from the same backup point.
3. Start backend.
4. Run smoke checks from the deployment guide.
5. Open `/workbench` and verify artifact, audit, policy and test counts.

## Integrity Checks

- Audit export should parse as NDJSON.
- Artifact graph health should report `status=ok`.
- Canonical metadata snapshots should list without JSON errors.
