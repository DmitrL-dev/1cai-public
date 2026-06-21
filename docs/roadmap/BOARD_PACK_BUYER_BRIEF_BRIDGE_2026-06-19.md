# Board Pack Buyer Brief Bridge

Date: 2026-06-19.

Board Pack now carries the same Buyer Brief room map as Home, Launch Room, Killer Demo and Evidence Bundle.

## Implemented

- New `board_room_bridge` in `build_board_pack`.
- `/api/v1/board-pack/build` builds `buyer_brief` from the fast buyer-brief service and passes it into the board decision packet.
- Board Pack proof packet starts with `buyer-brief.md` and `buyer-pulse.md`.
- Summary includes board-room role, proof and meeting-step counts.
- `/board-pack` UI shows a Board room bridge panel before board snapshot, close packet and risk sections.
- `proof_routes` now includes Buyer Brief meeting flow routes, including `/killer-demo`.

## Buyer Effect

The board packet starts with the buying committee map: who is in the room, which proof each role needs, what files can be forwarded and what paid question the board should answer.

## Verification

- `python -m py_compile src/services/rentgen/board_pack.py src/api/board_pack_api.py tests/unit/test_board_pack.py`
- `python -m pytest tests/unit/test_board_pack.py -q`
- `npm run build`
