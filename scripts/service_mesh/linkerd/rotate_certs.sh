#!/usr/bin/env bash
set -euo pipefail

dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(cd "$dir/../../.." && pwd)
CERT_DIR=${CERT_DIR:-$ROOT_DIR/infrastructure/service-mesh/linkerd/certs}
NS=${1:-linkerd}
SECRET_NAME=${2:-linkerd-identity-issuer}

mkdir -p "$CERT_DIR"

bash "$dir/bootstrap_certs.sh" "$CERT_DIR"
bash "$dir/deploy_issuer_secret.sh" "$NS" "$SECRET_NAME" "$CERT_DIR/root-ca.crt" "$CERT_DIR/issuer.crt" "$CERT_DIR/issuer.key"

kubectl rollout restart deploy/linkerd-identity -n "$NS"

printf '[linkerd] certificates rotated and identity deployment restarted\n'
