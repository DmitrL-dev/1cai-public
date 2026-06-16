#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-linkerd-ci}
KIND_VERSION=${KIND_VERSION:-v1.29.2}

cleanup() {
  echo "[linkerd-ci] deleting kind cluster $CLUSTER_NAME"
  kind delete cluster --name "$CLUSTER_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if ! command -v kind >/dev/null 2>&1; then
  echo "[linkerd-ci] installing kind $KIND_VERSION"
  curl -Lo ./kind.exe https://kind.sigs.k8s.io/dl/$KIND_VERSION/kind-windows-amd64
  chmod +x ./kind.exe
  mv ./kind.exe /usr/local/bin/kind
fi

if ! command -v linkerd >/dev/null 2>&1; then
  echo "[linkerd-ci] installing linkerd CLI"
  curl -sL https://run.linkerd.io/install | sh
  export PATH=$HOME/.linkerd2/bin:$PATH
fi

kind create cluster --name "$CLUSTER_NAME"

export PATH=$HOME/.linkerd2/bin:$PATH

linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd check

linkerd viz install | kubectl apply -f -
linkerd check --proxy

echo "[linkerd-ci] smoke test completed"
