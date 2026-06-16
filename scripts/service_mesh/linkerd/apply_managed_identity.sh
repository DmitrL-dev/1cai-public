#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 4 ]]; then
  echo "Usage: $0 <resource-group> <identity-name> <keyvault-name> <linkerd-namespace>" >&2
  exit 1
fi

RG=$1
IDENTITY=$2
KEYVAULT=$3
NS=$4

IDENTITY_INFO=$(az identity show -g "$RG" -n "$IDENTITY" --query '{clientId:clientId,principalId:principalId}' -o json)
CLIENT_ID=$(echo "$IDENTITY_INFO" | jq -r '.clientId')
PRINCIPAL_ID=$(echo "$IDENTITY_INFO" | jq -r '.principalId')

az keyvault set-policy -n "$KEYVAULT" --secret-permissions get list --object-id "$PRINCIPAL_ID"

kubectl create secret generic linkerd-identity -n "$NS" --from-literal="AZURE_CLIENT_ID=$CLIENT_ID" --dry-run=client -o yaml | kubectl apply -f -

kubectl annotate secret linkerd-identity -n "$NS" kubernetes.io/service-account.name=linkerd-identity --overwrite

echo "Managed identity $IDENTITY configured for Key Vault $KEYVAULT and stored in secret $NS/linkerd-identity"
