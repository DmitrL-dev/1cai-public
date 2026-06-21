# Commercial Assumption Sync

Date: 2026-06-19.

Killer Demo and Evidence Bundle now carry the same commercial assumptions as Business Case, Board Pack and Commercial Offer Studio. This protects the buyer-facing story from showing one AI-rent baseline on the finance pages and another one inside the proof/demo archive.

## Implemented

- `POST /api/v1/killer-demo/build` accepts `assumptions`.
- `POST /api/v1/evidence-bundle/build` and `/archive` accept `assumptions`.
- `build_evidence_bundle(...)` forwards assumptions into every generated Business Case branch.
- `/killer-demo` and `/evidence-bundle` expose `AI / month` input on the first setup panel.
- TypeScript API contracts include assumptions for Killer Demo and Evidence Bundle requests.
- Evidence Bundle emits a top-level `commercial_assumptions` receipt and repeats it in `OPEN_FIRST.md`, `procurement-handoff.md`, archive README and the UI side panel.
- Evidence Bundle regression verifies Business Case, Board Pack and Killer Demo all show the same three-year AI-rent baseline.

## Buyer Value

1. The presenter can enter the customer's actual AI subscription budget once and keep the numbers aligned across demo, board pack and archive.
2. Procurement does not receive an Evidence Bundle whose pricing argument contradicts the live demo.
3. The anti-subscription story stays anchored to buyer assumptions instead of default demo constants.
4. A forwarded ZIP explains the commercial baseline before the buyer opens deep Business Case files.

## Verification

- `python -m py_compile src/api/killer_demo_api.py src/api/evidence_bundle_api.py src/services/rentgen/evidence_bundle.py`
- `python -m pytest tests/unit/test_evidence_bundle.py tests/unit/test_killer_demo_path.py -q`
- `npm run build`
- API smoke with `monthly_ai_subscription_cost=200000`:
  - Killer Demo one-page order: `7 200 000 RUB`.
  - Evidence Bundle Business Case: `7200000`.
  - Evidence Bundle Board Pack and Killer Demo artifacts: `7 200 000 RUB`.
