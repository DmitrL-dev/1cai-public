# No Stub Language Buyer Surfaces - 2026-06-20

## What Changed

- `src/ai/scenario_examples.py` no longer returns `заглушка` wording in reference execution reports; it now labels them as dry-run reports without runtime evidence.
- `src/api/launch_room_api.py` renamed `_artifact_stub` to `_artifact_summary`, matching the fact that Launch Room summarizes already-built reports.
- `src/modules/auth/api/dependencies.py` no longer documents OAuth id conversion as a temporary stub and no longer collapses all non-numeric user ids to `1`.
- Added regression coverage for stable string user id mapping.

## Buyer Impact

Hidden or secondary product paths no longer leak unfinished-language signals during demos, logs or API exploration. Auth/OAuth compatibility is also safer because different string users now map to different stable numeric ids.

## Verification

- `python -m py_compile src/ai/scenario_examples.py src/api/launch_room_api.py src/modules/auth/api/dependencies.py`
- `pytest tests/unit/test_auth_dependencies.py tests/unit/test_launch_room.py -q`
- Targeted `rg` for `заглушка|stub|placeholder|TODO|fake` in the touched files
