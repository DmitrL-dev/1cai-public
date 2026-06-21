# Vendor Portfolio Buyer Brief Bridge

Date: 2026-06-19.

Vendor Portfolio now carries the same Buyer Brief room map as Home, Buyer Concierge, Value Packs, Business Case and deal-route screens.

## Implemented

- New `vendor_room_bridge` in `build_vendor_portfolio`.
- `/api/v1/vendor-portfolio/audit` and portfolio audit branches build `buyer_brief` from the fast buyer-brief service and pass it into Vendor Portfolio.
- Single-audit portfolio summary includes vendor-room role, proof and meeting-step counts.
- `/vendor-portfolio` UI shows Buyer Room Map before Deal Board.
- `proof_routes` includes Buyer Brief meeting-flow routes, including `/killer-demo`.

## Buyer Effect

The partner/franchisee audit starts with who is in the room, which proof files are ready and which paid motion should follow. The audit no longer looks like a passive technical report; it becomes a buyer-forwardable path from role pain to work package, offer and evidence archive.

## Verification

- `python -m py_compile src/services/rentgen/vendor_portfolio.py src/api/vendor_portfolio_api.py tests/unit/test_vendor_portfolio.py`
- `python -m pytest tests/unit/test_vendor_portfolio.py -q`
- API audit smoke confirms `management-buyer-brief`, five role cards, four proof items, four meeting steps, first files `buyer-brief.md`/`buyer-pulse.md`, `/killer-demo` route and three-year AI-rent line.
- `npm run build`
