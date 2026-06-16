#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)
CHAOS_DIR="$ROOT_DIR/infrastructure/chaos/litmus"

EXPERIMENT=${1:-pod-delete}

case "$EXPERIMENT" in
  pod-delete)
    kubectl apply -f "$CHAOS_DIR/pod-delete.yaml"
    kubectl apply -f "$CHAOS_DIR/chaos-engine.yaml"
    ;;
  network)
    kubectl apply -f "$CHAOS_DIR/pod-network-latency.yaml"
    kubectl apply -f "$CHAOS_DIR/chaos-engine-network.yaml"
    ;;
  *)
    echo "Unknown experiment: $EXPERIMENT" >&2
    exit 1
    ;;
esac
