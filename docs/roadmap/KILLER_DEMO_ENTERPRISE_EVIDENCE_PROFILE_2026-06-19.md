# Killer Demo Enterprise Evidence Profile - 2026-06-19

## Why

Killer Demo is the first buyer route, but `/api/v1/killer-demo/build` was always composing Evidence Bundle with update, rights/RLS, lock radar and extension safety disabled. That kept the first path light, but it also meant an architect, security lead or operations owner could ask for enterprise proof and the presenter had to leave the killer route to rebuild a separate bundle.

## Implemented

- Added `evidence_profile` to `KillerDemoRequest` with `buyer` as the default and `enterprise` as the deep proof profile.
- Added targeted request flags: `include_update`, `include_rights`, `include_lock_radar`, `include_extension_safety` and `lock_radar_log_path`.
- Enterprise profile turns on Update War Room, Rights/RLS, Lock Radar and Extension Safety while still keeping `include_killer_demo=False` to avoid recursive bundle builds.
- Killer Demo proof packet now selects and prioritizes enterprise artifact files when they exist: `productization-readiness.md`, `rights-rls.md`, `update-war-room.md`, `lock-radar.md`, `extension-safety.md`.
- Developer/QA and architect/security handoff lists now mention the relevant enterprise files when present.
- Portal Killer Demo inputs now expose Buyer/Enterprise profile selection, deep proof toggles and Tech Journal path.
- API client request type includes the new profile and include flags.

## Verification

```text
pytest tests/unit/test_killer_demo_api.py tests/unit/test_killer_demo_path.py -q
8 passed

npm.cmd run build
passed
```

## Product Effect

The first demo can remain fast and understandable, while the same route can switch into a serious enterprise proof package for architecture, security, operations and procurement without sending the seller to a different workflow.
