# ML Predictor Encoding Trust Cleanup - 2026-06-20

## What Changed

- Replaced mojibake docstrings, comments and log/error messages in `src/modules/ml/domain/predictor.py`.
- Kept behavior unchanged: model training, prediction, probability, evaluation and ensemble logic are the same.
- Runtime logs now use clear ASCII English messages instead of corrupted Russian text.

## Buyer Impact

If optional ML paths surface in logs, support traces or diagnostics, they now look like maintained product code rather than a broken encoding artifact.

## Verification

- `python -m py_compile src/modules/ml/domain/predictor.py`
- targeted `rg` confirms runtime mojibake markers are gone; only the regression assertion that forbids mojibake remains.
