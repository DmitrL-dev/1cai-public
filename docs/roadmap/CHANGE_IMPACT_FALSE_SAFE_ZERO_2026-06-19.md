# Change Impact False-Safe-Zero Guard

Date: 2026-06-19.

## Purpose

Prevent a dangerous buyer-facing lie: `impact_total = 0` must never look safe when the changed module is absent from the Rentgen call graph. A zero is safe only when impact is measured and the graph coverage is explicit.

## Implemented

- `build_change_plan` already classifies impact coverage with `impact_measured`, `coverage` and `coverage_caveat`.
- `quality_api.review-diff` now carries the same contract for diff-mode Change Impact.
- Test Coverage Matrix rows now include `impact_measured`, `coverage`, `coverage_caveat` and `summary.unmeasured_impact`.
- Test Factory treats unmeasured impact as release risk, adds an architect-owned manual proof check and avoids `impact 0` wording.
- Release Readiness exposes `summary.unmeasured_impact_modules`, persona coverage signals, markdown summary and warning-severity gate actions.
- `/change`, `/testing` and `/release-readiness` show unknown impact explicitly with warning/danger tone.

## Why It Matters

- Developer: sees that a form or unresolved module needs focused tests and graph/metadata proof.
- Architect: can challenge graph coverage instead of trusting a quiet zero.
- QA: gets run-now tests plus a manual impact proof task.
- Director/release owner: sees measured impact and unknown impact as separate release facts.

## Verification

- `pytest tests/unit/test_rentgen_change_plan.py tests/unit/test_change_plan_forms.py tests/unit/test_test_coverage_matrix.py tests/unit/test_test_factory.py tests/unit/test_release_readiness.py tests/unit/test_standards_review.py -q`
- `npm run build` in `portal`

## Remaining Hardening

- Extend the same coverage contract into every future impact-like report before it reaches a green status.
- Add visual regression coverage for `/change`, `/testing` and `/release-readiness` once Playwright smoke tests are stable in CI.
