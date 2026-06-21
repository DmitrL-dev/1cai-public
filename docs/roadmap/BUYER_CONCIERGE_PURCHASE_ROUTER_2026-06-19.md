# Buyer Concierge Purchase Router - 2026-06-19

## Goal

Buyer Concierge already reduces first-screen confusion with role cards, pain picker and shortest paths. This slice makes the first screen commercial as well: every role can now move from curiosity to a buyable local-license motion without hunting through the sidebar.

## Implemented

- Backend `purchase_router` in `src/services/rentgen/buyer_concierge.py`.
- Role cards now include `purchase_route`, `purchase_ask` and `proof_file`.
- Markdown export includes Purchase Router and role purchase prompts.
- API health includes `purchase_router_status` and `three_year_ai_rent`.
- Portal `/buyer-concierge` shows a purchase panel with Launch Room CTA, recommended purchase, AI-rent baseline, local-license anchor, break-even, quick actions, role prompts and close sequence.
- TypeScript contract updated in `portal/src/lib/api-client.ts`.

## Buyer Effect

- Director: sees `AI / month`, three-year AI rent, local-license anchor and Launch Room as the first purchase cockpit.
- Developer: sees a concrete defect proof as a paid proof-sprint entry, not only a code-quality finding.
- Architect: sees platform/update caveats as hardening or pilot scope.
- Security/CIO: sees locality, SBOM/offline posture, Rights/RLS and evidence retention before optional AI add-ons.
- Vendor: sees audit evidence as a packaged rollout offer.

## Verification

- `python -m py_compile src/services/rentgen/buyer_concierge.py src/api/buyer_concierge_api.py`
- `python -m pytest tests/unit/test_buyer_concierge.py -q`
- `npm run build` in `portal`
- API smoke with `monthly_ai_subscription_cost=200000` should show `7 200 000 RUB`, `/launch-room` proof route and a visible `purchase_router.status`. Real configuration caveats can correctly keep it at `watch`.
