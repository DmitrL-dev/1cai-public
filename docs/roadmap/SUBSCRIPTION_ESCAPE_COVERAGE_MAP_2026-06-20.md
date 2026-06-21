# Subscription Escape Coverage Map - 2026-06-20

## What Changed

- `/copilot-coverage` remains API/route-compatible, but the visible portal page is now framed as `Rentgen Subscription Escape Map`.
- The API product name and OpenAPI tag now describe subscription-escape/local-asset coverage rather than a Copilot clone.
- Productization and Executive Dashboard labels now say subscription escape coverage.
- `docs/COPILOT_COVERAGE.md` keeps its historical filename but now opens as a Rentgen subscription escape coverage map.
- Added regression coverage to prevent the buyer-facing API response from returning to `Copilot` product naming.

## Buyer Impact

The hidden comparison map now supports the core sales story: Rentgen is a local 1C evidence asset with optional AI, not another monthly coding-assistant subscription. This makes the competitive comparison useful instead of confusing.

## Verification

- `python -m py_compile src/api/copilot_coverage_api.py src/services/productization_readiness.py src/services/rentgen/executive_dashboard.py`
- `pytest tests/unit/test_copilot_coverage.py tests/unit/test_productization_readiness.py tests/unit/test_executive_dashboard.py -q`
- `npm run build` in `portal`
