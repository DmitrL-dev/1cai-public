# Vendor Portfolio Decision Board

Date: 2026-06-19.

Vendor Portfolio now turns one-client audits and multi-client portfolio mode into a commercial decision board.

## Implemented

- Single audit `deal_board`: recommended motion, primary package, next paid step, role sparks and proof packet.
- Single audit `vendor_room_bridge`: Buyer Brief role cards, proof readiness, meeting flow, first files and close question before Deal Board.
- Portfolio `decision_board`: next commercial move, risk/watch/ready segments, offer sequence and proof packet.
- Fast health: `GET /api/v1/vendor-portfolio/health` uses buyer pulse and does not build Platform Doctor, Intake or audit reports.
- UI: `/vendor-portfolio` shows Deal Board for one client and Decision Board for portfolio mode.
- Tests: `tests/unit/test_vendor_portfolio.py`.

## Buyer Value

1. Partner/franchisee sees which client to sell to first and what package to lead with.
2. Architect sees risk clients separated from ready clients before promises are made.
3. Director gets a buyer-safe sequence from audit to offer to evidence packet.
4. Portfolio mode becomes a sales cockpit, not a passive table.

## Verification

- `python -m pytest tests/unit/test_vendor_portfolio.py -q`
- API audit smoke confirms `management-buyer-brief`, `buyer-brief.md`/`buyer-pulse.md` first files and `/killer-demo` in proof routes.
- `python -m pytest tests/unit/test_enterprise_value_fast_health.py -q`
- `npm run build`
