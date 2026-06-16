#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-linkerd-chaos}
KIND_VERSION=${KIND_VERSION:-v0.22.0}

delete_cluster() {
  kind delete cluster --name "$CLUSTER_NAME" >/dev/null 2>&1 || true
}
trap delete_cluster EXIT

kind create cluster --name "$CLUSTER_NAME"

if ! command -v linkerd >/dev/null 2>&1; then
  curl -sL https://run.linkerd.io/install | sh
  export PATH=$HOME/.linkerd2/bin:$PATH
fi

export PATH=$HOME/.linkerd2/bin:$PATH

linkerd install --crds | kubectl apply -f -
linkerd install | kubectl apply -f -
linkerd check

curl -sL https://run.linkerd.io/emojivoto.yml | kubectl apply -f -

kubectl -n emojivoto rollout status deploy/web --timeout=120s
linkerd viz install | kubectl apply -f -
linkerd check --proxy

linkerd viz stat deploy -n emojivoto

echo "[linkerd-chaos] deleting web pod to simulate failure"
kubectl -n emojivoto delete pod -l app=web
sleep 5
kubectl -n emojivoto rollout status deploy/web
linkerd viz stat deploy -n emojivoto

echo "[linkerd-chaos] chaos scenario passed"
