#!/usr/bin/env bash
set -euo pipefail

pip install --upgrade pip pip-audit bandit safety >/dev/null

bandit -q -r src || echo "[warn] bandit found issues"
pip-audit || echo "[warn] pip-audit found issues"
safety check || echo "[warn] safety found issues"
