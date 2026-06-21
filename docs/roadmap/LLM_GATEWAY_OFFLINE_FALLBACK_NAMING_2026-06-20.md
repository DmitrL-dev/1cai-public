# LLM Gateway Offline Fallback Naming - 2026-06-20

## Why

When no LLM provider was available, the gateway returned a diagnostic labeled `LLM placeholder` with
`placeholder=True`. That wording weakens the local-first product story: the fallback is not a fake answer,
it is an explicit offline diagnostic state.

## Implemented

- Renamed the no-provider diagnostic response to `LLM offline fallback`.
- Replaced `placeholder=True` metadata with:
  - `offline=True`;
  - `fallback=True`;
  - `fallback_reason=no_provider_available`.
- Added `fallback_reason=all_providers_unavailable` to the all-providers-failed fallback metadata.
- Updated stale LLM gateway tests from removed module-level client patching to the current `get_client` contract.
- Added regression coverage that verifies no-provider fallback is not labeled as a placeholder.

## Buyer Impact

Architects and security reviewers see an honest offline state instead of a fake generated answer.
The product language now supports the local-license story: provider outage is a governed offline mode, not
an unfinished placeholder.

## Verification

- `python -m py_compile src/services/llm_gateway.py tests/unit/test_llm_gateway.py tests/unit/test_llm_gateway_resilience.py`
- `pytest tests/unit/test_llm_gateway.py tests/unit/test_llm_gateway_resilience.py -q`
