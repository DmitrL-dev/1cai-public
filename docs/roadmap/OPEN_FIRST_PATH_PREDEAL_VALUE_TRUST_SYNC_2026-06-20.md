# Open-First Path Pre-Deal Value Trust Sync - 2026-06-20

## What Changed

- Added shared backend helper `src/services/rentgen/open_first_path.py` for a stable four-step `orient/prove/close/verify` buyer path.
- Buyer Brief, Launch Room, Pilot Launchpad and Outcome Ledger now use the shared helper instead of local duplicate fallback logic.
- Buyer Concierge, Scenario Hub, Demo Command Center, Guided Demo, Business Case, Value Packs, Vendor Portfolio, Commercial Offer Studio, Board Pack and Enterprise Trust Center now expose `open_first_path`.
- Each affected room bridge now includes `open-first-path.md`, routes from the open-first path, Markdown output and a summary/portfolio open-first counter.
- Portal API types now share `OpenFirstPathItem`.
- Added shared portal component `OpenFirstPathList` and rendered it in all affected pre-deal/value/trust room bridges.
- Launch Room, Pilot Launchpad and Outcome Ledger now reuse the same `OpenFirstPathList` component for consistent buyer path rendering.

## Buyer Impact

The buyer can enter from role, pain, value, vendor audit, commercial offer, board approval or trust review and still see the same compact path: orient the room, prove one claim, close the next paid step and verify the packet. This lowers first-screen confusion and keeps every buyer-facing room connected to the same purchase motion.

## Verification

- `python -m py_compile src/services/rentgen/open_first_path.py src/services/rentgen/buyer_concierge.py src/services/rentgen/scenario_hub.py src/services/rentgen/demo_command_center.py src/services/rentgen/guided_demo.py src/services/rentgen/business_case.py src/services/rentgen/value_packs.py src/services/rentgen/vendor_portfolio.py src/services/rentgen/commercial_offer_studio.py src/services/rentgen/board_pack.py src/services/rentgen/enterprise_trust_center.py`
- `pytest tests/unit/test_buyer_concierge.py tests/unit/test_scenario_hub.py tests/unit/test_demo_command_center.py tests/unit/test_guided_demo.py tests/unit/test_business_case.py tests/unit/test_value_packs.py tests/unit/test_vendor_portfolio.py tests/unit/test_commercial_offer_studio.py tests/unit/test_board_pack.py tests/unit/test_enterprise_trust_center.py -q` -> 20 passed.
- `npm run build` in `portal`
