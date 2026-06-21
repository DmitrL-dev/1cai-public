# P0 Truth Sync and Rentgen Build Contract

Date: 2026-06-19.

## Purpose

Remove first-run confusion from the product handoff: docs must describe the live public-snapshot product, and the portal must not call a Rentgen build endpoint that the backend does not expose.

## Implemented

- `HANDOFF.md` current-truth block now states the downstream false-safe-zero guard and Buyer Brief/Buyer Pulse room bridges.
- `README.md` current status now names the false-safe-zero guard beyond `/change`.
- `docs/roadmap/MEGA_REALIZATION_PLAN_2026-06-18.md` marks the README/HANDOFF and `rentgenApi.build` P0 items done.
- Contract test added for `GET /api/v1/rentgen/build`, including the query-param shape used by `portal/src/lib/api-client.ts`.

## Verification

- `pytest tests/unit/test_rentgen_api_contract.py -q`
- Included in the focused P0 regression pass together with change-impact safety tests.

## Notes

- `GET /api/v1/rentgen/build` is intentionally a readiness/info endpoint for the prebuilt SQLite store, not an online rebuild trigger.
- `scripts/start_rentgen.ps1` remains the rebuild/start path for local dev; it prints the actual portal port if `:3000` is busy.
