# Wiki Static UI Evidence Shell - 2026-06-20

## Why

The API root still advertises `/wiki-ui`, and FastAPI mounts `src/static/wiki` there. The old static page
called non-mounted `/api/v1/wiki` CRUD/search endpoints and showed legacy stub content, which could make a
buyer think the product had broken documentation/RAG surfaces.

## Implemented

- Replaced the old static Wiki CRUD page with a buyer-safe evidence shell.
- Removed fake recent pages and stub comments.
- Added links to the buyer-ready proof routes:
  - Evidence Bundle;
  - Killer Demo;
  - Launch Room;
  - Outcome Ledger.
- Added graceful Wiki API status detection.
- Added evidence search messaging that reports missing API state instead of showing fabricated pages.
- Added regression coverage over the static HTML.

## Buyer Impact

If someone opens `/wiki-ui`, they now see a clear evidence handoff shell instead of a broken legacy wiki app.
The page points back to proof routes that can actually support a purchase conversation.

## Verification

- `python -m py_compile src/app/factory.py tests/unit/test_static_wiki_ui.py`
- `pytest tests/unit/test_static_wiki_ui.py -q`
