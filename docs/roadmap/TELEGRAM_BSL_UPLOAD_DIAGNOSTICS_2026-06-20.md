# Telegram BSL Upload Diagnostics - 2026-06-20

## What Changed

- Telegram `.bsl`, `.os` and `.txt` uploads now run local `analyze_bsl` diagnostics.
- The handler downloads the file, decodes UTF-8/UTF-8 BOM/CP1251 text and returns a plain-text report.
- The report includes LOC, procedure/function counts, max nesting, severity counts and top findings.
- Top findings now surface the first diagnostic `safe_options` entry and first `test_expectations` entry, so LEFT JOIN/NULL findings arrive with an immediate safe fix pattern and a check to run.
- BSL upload decoding/report formatting moved into `src/telegram/bsl_upload_report.py`, making the buyer-facing report testable without importing the full `aiogram` bot stack.
- The old "BSL analysis is in development" reply was removed from the reachable upload path.
- Telegram formatter responses and `/start` text were rewritten into clean Telegram-safe Markdown instead of mojibake.

## Buyer Impact

Telegram is no longer a dead-end demo surface for BSL files. A developer can send a module and immediately see deterministic local findings, the safest first fix option and the expected verification check without cloud AI or a fake "coming soon" response, while help/search/error/stat responses stay readable.

## Verification

- `python -m py_compile src/telegram/handlers.py src/services/bsl_diagnostics.py`
- targeted `rg` confirms the old TODO/under-development BSL upload wording is gone from the handler.
- `python -m py_compile src/telegram/formatters.py`
- `python -m py_compile src/telegram/bsl_upload_report.py src/telegram/handlers.py`
- `pytest tests/unit/test_telegram_bsl_upload_report.py tests/unit/test_standards_review.py -q` -> 18 passed.
