# Home Buyer Start

Date: 2026-06-19.

## Purpose

The home page now starts with a buyer-first decision surface before the deep engineering dashboard.
This reduces the "monster product" effect by showing the purchase path first and the specialist workbench second.

## Implemented

- Added a top buyer-start section on `/`.
- Primary entries: Launch Room, Killer Demo, Board Pack and Evidence Bundle.
- Governance chain entries: Approve, Audit, Activate and Realize.
- Live executive signals are reused for score, red areas and review queue.
- Home Buyer Pulse calls the fast `GET /api/v1/management/buyer-pulse` endpoint to show purchase-spine status, Concierge status, three-year AI-rent line, proof routes and governance gates without building deep deal artifacts on page load.
- Home Buyer Brief calls the fast `GET /api/v1/management/buyer-brief` endpoint to provide the first-minute room map: primary motion, role cards, proof readiness, meeting flow and embedded Buyer Pulse.
- The same Buyer Pulse now materializes in Evidence Bundle as `buyer-pulse.json/.md`, so the first-screen signal can be forwarded and hash-verified.
- The existing role dashboard and deep workbench links remain available below the buyer-start layer.

## Product Value

- A director sees the paid motion and proof export before the technical surface.
- A developer or architect still has a route into code, platform, tests and architecture.
- Procurement and security see approval/audit proof from the first screen.
- The first screen now has live deal health: Launch Room readiness, Concierge role/path count and the local-license vs AI-rent signal are visible before deep navigation.
- Role/proof guidance now comes from backend contract, so Home, docs and buyer routes stay aligned instead of duplicating first-screen logic in UI.
- The first click no longer depends on knowing the entire product map.

## Verification

- `npm run build` in `portal/` passed.
- API smoke should cover `/api/v1/management/buyer-brief` because Home renders it before deep buyer modules.
- Live route smoke for `/` should be used together with `/launch-room`, `/approvals` and `/audit` during demo checks.
