# Test Factory v1

Date: 2026-06-19.

## Purpose

Test Factory turns changed 1C modules or a diff into a release-ready test package:
what to run now, what to generate, what to verify manually, and what to attach as evidence.

## Implemented

- Backend service: `src/services/rentgen/test_factory.py`
- API: `POST /api/v1/test-factory/build`, `GET /api/v1/test-factory/health`
- UI: `/testing` is now a Test Factory screen over the existing coverage matrix
- Evidence Bundle artifact: `test-factory.json` and `test-factory.md`
- Deterministic YAxUnit and Vanessa skeletons for coverage gaps
- Honest fallback when the Rentgen graph store is unavailable: changed modules become explicit test gaps
- False-safe-zero guard: rows carry `impact_measured`, `coverage` and `coverage_caveat`; unmeasured impact becomes high-priority release risk instead of `impact 0`
- Tests: `tests/unit/test_test_factory.py`, plus Evidence Bundle coverage

## Product Value

- Developers get run-now commands instead of a vague risk score.
- QA gets smoke, regression, manual checks and test data needs in one place.
- Architects and release owners see whether coverage is exact, planned or missing.
- Directors get evidence that the product reduces release uncertainty, not just code review effort.

## Caveats

- Generated skeletons are starting points; customer fixtures and acceptance data are still required.
- Live YAxUnit/Vanessa execution depends on the local customer test profile.
- When graph data is unavailable, Test Factory reports gaps instead of pretending impact is zero.
- When a module is absent from the call graph, generated tests are still useful but do not prove blast-radius safety; the release owner must close the coverage caveat.
