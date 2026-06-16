#!/usr/bin/env bash
set -euo pipefail

: "${ARGOCD_SERVER:=localhost:8080}"
: "${ARGOCD_TOKEN:=}"

if ! command -v argocd >/dev/null 2>&1; then
  echo "[gitops] argocd CLI not found" >&2
  exit 1
fi

if [ -z "$ARGOCD_TOKEN" ]; then
  echo "[gitops] ARGOCD_TOKEN is required" >&2
  exit 1
fi

argocd login "$ARGOCD_SERVER" --grpc-web --insecure --auth-token "$ARGOCD_TOKEN"
argocd app sync 1cai-stack
argocd app sync observability-stack
