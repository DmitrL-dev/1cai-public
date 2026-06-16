#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)
MANIFEST_DIR="$ROOT_DIR/infrastructure/argocd"

kubectl apply -k "$MANIFEST_DIR"
