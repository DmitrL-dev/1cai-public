#!/usr/bin/env bash
set -euo pipefail

: "${VAULT_ADDR?must set VAULT_ADDR}"
: "${VAULT_TOKEN?must set VAULT_TOKEN}"

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")"/../../.. && pwd)
POLICY_FILE="$ROOT_DIR/infrastructure/vault/policies/1cai-app.hcl"

vault secrets enable -path=secret -version=2 kv || true
vault policy write 1cai-app "$POLICY_FILE"

vault auth enable kubernetes || true
vault write auth/kubernetes/config \
  kubernetes_host="$KUBERNETES_HOST" \
  kubernetes_ca_cert=@"${KUBERNETES_CA_CERT:-/var/run/secrets/kubernetes.io/serviceaccount/ca.crt}" \
  token_reviewer_jwt="${KUBERNETES_REVIEWER_JWT:-}"

vault write auth/kubernetes/role/1cai-app \
  bound_service_account_names=1cai-app \
  bound_service_account_namespaces=1cai \
  policies=1cai-app \
  ttl=24h

echo "Vault configured for 1cai-app"
