# Buyer Room Packet Pre-Deal Role Controls - 2026-06-20

## What Changed

- Buyer Concierge now exposes `Buyer Room Packet ZIP` and `Verify Buyer Room Packet` from the first role/pain screen.
- Scenario Hub now exposes the same controls next to pain-led route selection.
- Demo Command Center now exposes the same controls for presenters before and during the live route.
- Guided Demo and Business Case now expose the same packet controls beside their markdown/export actions.
- Value Packs now exposes the packet controls near the buyable pack summary, so packaging and licensing conversations can attach the same verified ZIP.
- Vendor Portfolio now exposes the packet controls beside the pre-sale audit markdown, before portfolio mode.
- All screens reuse the shared `BuyerRoomPacketControls` component with local SHA-256 comparison and endpoint verification status.

## Buyer Impact

Role-first, scenario-first, value-first and vendor-first buyers can leave with the same verified open-first packet without navigating through the whole product map. This reduces the "what do I open or send?" moment during discovery, live presentation, business-case review and pre-sale audit.

## Verification

- `npm run build` in `portal`
