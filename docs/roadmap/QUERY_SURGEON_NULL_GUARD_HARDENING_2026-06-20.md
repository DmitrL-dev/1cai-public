# Query Surgeon NULL Guard Hardening - 2026-06-20

## What Changed

- Fixed mojibake in the LEFT JOIN NULL guard diagnostic message and safe options.
- The deterministic BSL diagnostics now recognize Russian `ЕстьNULL` / `ЕСТЬ NULL` guards correctly inside mixed projection lines.
- Added contextual support for multiline `ВЫБОР/КОГДА НЕ <field> ЕСТЬ NULL` branches so guarded fields are not reported as false positives.
- Commented-out LEFT JOIN lines no longer create phantom aliases.
- Findings now include `field_ref`, risk text, safe options and test expectations for MR/QA handoff.
- Standards Review UI renders the field reference, risk, safe options and tests directly in the finding card.
- The default Standards Review sample now demonstrates the 1C-specific LEFT JOIN/NULL case instead of a generic unsafe-code example.

## Buyer Impact

Developers see a concrete 1C query defect, the safe rewrite choices and the regression checks in one screen. QA receives the exact missing-row and existing-row checks needed to prove the fix without changing row counts, grouping or totals unexpectedly.

## Verification

- `python -m py_compile src/services/bsl_diagnostics.py`
- `pytest tests/unit/test_standards_review.py -q`
- `npm run build` in `portal`
