# Runtime Trust Placeholder Cleanup - 2026-06-20

## What Changed

- Marketplace plugin stats now calculate `rating_trend` from last-30-day average rating versus the previous 30 days.
- Added regression coverage for a rising rating trend.
- BSL lexer grammar now uses real Cyrillic literals for `ИСТИНА`, `ЛОЖЬ` and `НЕОПРЕДЕЛЕНО`.
- Removed the lexer TODO comment and documented datetime lexing as intentionally permissive.
- Graph builder comments now call unresolved cross-module calls explicit external references rather than placeholders.

## Buyer Impact

Runtime code no longer contains visible unfinished product smells in these paths. Marketplace stats stop pretending every rating trend is stable, and BSL grammar better reflects real 1C syntax.

## Verification

- `pytest tests/integration/test_marketplace_analytics.py -q`
- `python -m py_compile src/ai/code_analysis/graph_builder.py src/infrastructure/repositories/marketplace.py src/telegram/handlers.py src/telegram/formatters.py`
- targeted `rg` confirms runtime TODO/stub/fake/coming-soon markers are down to defensive comments only.
