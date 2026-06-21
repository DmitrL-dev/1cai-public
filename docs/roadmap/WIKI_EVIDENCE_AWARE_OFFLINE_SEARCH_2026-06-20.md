# Wiki Evidence-Aware Offline Search - 2026-06-20

## Why

The legacy Wiki service could still return a fabricated `stub answer` and fixed mock sources for Ask Wiki.
That is risky for buyer trust: a local 1C engineering product must not pretend to have RAG evidence when
no local evidence was found.

## Implemented

- Replaced `WikiService.ask_wiki` stub output with an evidence-aware offline answer contract:
  - `mode=offline-evidence-search`;
  - `coverage=no_query`, `no_local_evidence` or `local_wiki_evidence`;
  - `sources`;
  - `evidence`;
  - `caveats`.
- Added lexical local wiki search over stored pages for Ask Wiki.
- Replaced fixed mock Wiki search results with an offline lexical index fallback.
- Kept optional Qdrant/embedding adapters as real optional paths and supported sync/async adapter methods.
- Replaced random namespace fallback IDs with deterministic UUIDs for repeatable local behavior.
- Fixed dead `src.database` imports in Wiki service, comments and sync worker.
- Added regression tests for no-evidence answers, evidence-backed answers and offline lexical search.

## Buyer Impact

Architects and developers now see honest local evidence behavior. If the product has no wiki evidence, it
says so and asks for sync/addition instead of inventing an answer. If evidence exists, the response carries
sources and snippets that can be inspected.

## Verification

- `python -m py_compile src/services/wiki/service.py src/services/wiki/search.py src/services/wiki/sync_worker.py src/services/wiki/comments.py tests/unit/test_wiki_evidence_search.py`
- `pytest tests/unit/test_wiki_evidence_search.py -q`
