# DevOps Guarded Automation Contract - 2026-06-20

## Why

The DevOps API still exposed legacy placeholder language and the `/ai/evolve/metrics` route pointed to a
method that did not exist. The infrastructure analysis service also returned a shape that the route did not
surface, which made static analysis look empty.

## Implemented

- Replaced placeholder/stub/phantom wording with an explicit offline static Compose analysis contract.
- Made `analyze_infrastructure` return the route-compatible fields:
  - `static_analysis`;
  - `runtime_containers`;
  - `services_status`;
  - `recommendations`.
- Added Compose service inventory, healthcheck coverage, exposed port map, networks, volumes and readiness recommendations.
- Marked runtime collection honestly as `not_collected_without_docker_sdk`.
- Replaced legacy self-evolution responses with `disabled_by_policy` guarded automation status pointing to `/safe-autopilot`.
- Added missing `get_metrics` implementation for `/ai/evolve/metrics`.
- Replaced stale module README claims about autonomous improvements with the guarded automation contract.

## Buyer Impact

Operations and security reviewers see honest offline evidence instead of a broken runtime promise.
The product also avoids suggesting autonomous self-modification; Safe Autopilot remains the governed route for
plan, impact, diff, tests, evidence and approval.

## Verification

- `python -m py_compile src/modules/devops_api/services/devops_service.py src/modules/devops_api/api/routes.py tests/unit/test_devops_guarded_automation.py`
- `pytest tests/unit/test_devops_guarded_automation.py -q`
