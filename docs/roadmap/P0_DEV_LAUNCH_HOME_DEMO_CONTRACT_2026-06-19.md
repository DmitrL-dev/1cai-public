# P0 Dev Launch, Home, Demo Contract - 2026-06-19

## Closed Scope

- `scripts/start_rentgen.ps1` starts a development profile with `ENVIRONMENT=development`, a process-local `JWT_SECRET`, backend, portal, port fallback and buyer-facing route handoff.
- Portal Dev Mode uses real demo credentials (`admin/admin123`) and then calls `/api/v1/auth/me`; it no longer relies on a fake `dev-token`.
- The module auth API returns a real JWT that opens protected routes through `JWTUserContextMiddleware`.
- Home first-screen data is anchored by `GET /api/v1/management/buyer-brief`: primary motion, role cards, proof readiness, meeting flow and Buyer Pulse.
- Demo story is complete enough for the first buyer path: first value, Query Surgeon NULL case, guided route, role-specific steps and exportable role reports.

## Regression Locks

- `tests/unit/test_dev_launch_contract.py`
- `tests/unit/test_dev_auth_contract.py`
- `tests/unit/test_management_demo_intake.py`
- `tests/unit/test_executive_dashboard.py`
- Existing governance guard: `tests/unit/test_auth_governance.py`

## Verification

```text
pytest tests/unit/test_dev_launch_contract.py tests/unit/test_dev_auth_contract.py tests/unit/test_management_demo_intake.py tests/unit/test_executive_dashboard.py tests/unit/test_auth_governance.py -q
27 passed
```

Known warning: local `requests` dependency warning from the Python environment.
