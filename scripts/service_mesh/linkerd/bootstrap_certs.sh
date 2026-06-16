#!/usr/bin/env bash
set -euo pipefail

# Requires openssl
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")"/../../.. && pwd)
CERT_DIR=${1:-$ROOT_DIR/infrastructure/service-mesh/linkerd/certs}
mkdir -p "$CERT_DIR"

ROOT_CA="$CERT_DIR/root-ca"
ISSUER="$CERT_DIR/issuer"

openssl genrsa -out "$ROOT_CA.key" 4096
openssl req -x509 -new -nodes -key "$ROOT_CA.key" -sha256 -days 3650 -out "$ROOT_CA.crt" -subj "/CN=linkerd-trust-anchor"

openssl genrsa -out "$ISSUER.key" 4096
cat > "$CERT_DIR/issuer.cnf" <<'EOF'
[ req ]
distinguished_name = req_distinguished_name
prompt = no
[ req_distinguished_name ]
CN = identity.linkerd.cluster.local
[ v3_ca ]
subjectAltName = DNS:identity.linkerd.cluster.local
basicConstraints = CA:TRUE
keyUsage = digitalSignature, keyEncipherment, keyCertSign
EOF

openssl req -new -key "$ISSUER.key" -out "$ISSUER.csr" -config "$CERT_DIR/issuer.cnf"
openssl x509 -req -in "$ISSUER.csr" -CA "$ROOT_CA.crt" -CAkey "$ROOT_CA.key" -CAcreateserial \
  -out "$ISSUER.crt" -days 730 -extensions v3_ca -extfile "$CERT_DIR/issuer.cnf"

echo "Trust anchor: $ROOT_CA.crt"
echo "Issuer cert: $ISSUER.crt"
echo "Issuer key: $ISSUER.key"
