#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)

if ! command -v checkov >/dev/null 2>&1; then
  echo "[security] checkov not available" >&2
  exit 1
fi

if ! command -v trivy >/dev/null 2>&1; then
  echo "[security] trivy not available" >&2
  exit 1
fi

checkov -d "$ROOT_DIR/infrastructure/terraform" --quiet
checkov -d "$ROOT_DIR/infrastructure/terraform/aws-eks" --quiet
checkov -d "$ROOT_DIR/infrastructure/terraform/azure-aks" --quiet

trivy fs --scanners config --quiet "$ROOT_DIR"
