#!/bin/bash

# SSL/TLS Certificate Setup
# Enterprise 1C AI Development Stack

set -e

echo "Setting up SSL/TLS certificates..."

# Create directory
mkdir -p nginx/ssl

# Self-signed certificate for development
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/selfsigned.key \
  -out nginx/ssl/selfsigned.crt \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=1C AI Stack/CN=localhost"

echo "✓ Self-signed certificate created"

# For production, use Let's Encrypt:
# 1. Install cert-manager in Kubernetes
# 2. Create ClusterIssuer
# 3. Annotate Ingress with cert-manager

cat > k8s/cert-manager-issuer.yaml << 'EOF'
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF

echo "✓ Cert-manager configuration created"
echo ""
echo "For production:"
echo "1. kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml"
echo "2. kubectl apply -f k8s/cert-manager-issuer.yaml"
echo "3. Ingress will automatically get SSL certificates"

