# Legacy Database Import Compatibility - 2026-06-20

## Why

Several legacy routes, security helpers and test fixtures still imported `src.database`, but the active
database implementation lives in `src.infrastructure.db.connection`. That made those modules fail at import
time before they could even return a guarded offline/degraded response.

## Implemented

- Added `src/database.py` as a compatibility module that re-exports:
  - `create_pool`;
  - `close_pool`;
  - `get_pool`;
  - `get_db_pool`;
  - `get_db_connection`;
  - `check_pool_health`.
- Kept new code free to import the infrastructure module directly while preserving legacy routes.
- Added a regression test proving the shim exports the same function objects as the active connection module.

## Buyer Impact

The product is less fragile during demos and closed-contour installs: older routes no longer fail just because
their import path lagged behind the infrastructure refactor.

## Verification

- `python -m py_compile src/database.py tests/unit/test_database_compat.py`
- `pytest tests/unit/test_database_compat.py tests/unit/test_wiki_evidence_search.py -q`
