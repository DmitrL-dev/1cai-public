# P2 Rights/RLS Diff - 2026-06-19

## Implemented

- `build_rights_rls` now accepts `baseline_config_path`.
- Rights diff compares role/object/right fingerprints between baseline and current EDT/XML sources.
- Added dangerous rights raise `diff.status = risk`, add a `rights-diff-added-dangerous` finding and block the release gate.
- `GET /api/v1/rights-rls/analyze` accepts `baseline_path`.
- Rights/RLS portal page now has a `Baseline path` field and a `Rights diff` panel.
- Markdown export includes a `Rights Diff` section.

## Verification

```text
pytest tests/unit/test_rights_rls.py -q
3 passed

npm.cmd run build
passed
```
