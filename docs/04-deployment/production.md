# 🚀 Production Deployment Guide

## Enterprise 1C AI Development Stack v4.1

**Полное руководство по production развертыванию**

---

## 📋 Pre-requisites

### Infrastructure:
- ✅ Kubernetes cluster (1.25+)
- ✅ kubectl configured
- ✅ Helm 3 installed
- ✅ Storage provisioner
- ✅ Ingress controller (nginx)
- ✅ cert-manager (для SSL)

### Resources (minimum):
- **3 nodes** × 16GB RAM each
- **200GB** total storage
- **8 CPUs** total
- **Public IPs** for ingress

---

## 🔐 Step 1: Security Setup

### 1.1 Generate SSL certificates:

```bash
# Self-signed (development)
./security/ssl-tls-setup.sh

# Production (Let's Encrypt via cert-manager)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
kubectl apply -f k8s/cert-manager-issuer.yaml
```

### 1.2 Create secrets:

```bash
# Strong passwords
POSTGRES_PASS=$(openssl rand -base64 32)
NEO4J_PASS=$(openssl rand -base64 32)

# Create Kubernetes secrets
kubectl create secret generic postgres-secret \
  --from-literal=username=admin \
  --from-literal=password=$POSTGRES_PASS \
  -n 1c-ai-stack

kubectl create secret generic neo4j-secret \
  --from-literal=auth=neo4j/$NEO4J_PASS \
  -n 1c-ai-stack

# API keys
kubectl create secret generic api-secrets \
  --from-literal=GITHUB_TOKEN=$GITHUB_TOKEN \
  --from-literal=NAPARNIK_API_KEY=$NAPARNIK_KEY \
  -n 1c-ai-stack

# Save passwords securely!
echo "PostgreSQL: $POSTGRES_PASS" > secrets.txt
echo "Neo4j: $NEO4J_PASS" >> secrets.txt
chmod 600 secrets.txt
```

**⚠️ ВАЖНО:** Сохраните `secrets.txt` в защищенном месте!

---

## 📦 Step 2: Deploy via Helm (Recommended)

```bash
# 1. Update values
nano helm/1c-ai-stack/values.yaml

# 2. Install
helm install 1c-ai-stack ./helm/1c-ai-stack \
  --namespace 1c-ai-stack \
  --create-namespace \
  --values helm/1c-ai-stack/values.yaml

# 3. Wait for pods
kubectl wait --for=condition=ready pod \
  --all \
  --namespace=1c-ai-stack \
  --timeout=300s

# 4. Check status
helm status 1c-ai-stack -n 1c-ai-stack
kubectl get pods -n 1c-ai-stack
```

---

## 📦 Step 3: Deploy Manually (Alternative)

```bash
# 1. Namespace
kubectl apply -f k8s/namespace.yaml

# 2. Secrets (created in Step 1)

# 3. ConfigMaps
kubectl apply -f k8s/configmaps/

# 4. Persistent Volumes
kubectl apply -f k8s/persistent-volumes/

# 5. Databases
kubectl apply -f k8s/deployments/postgres.yaml
kubectl apply -f k8s/deployments/neo4j.yaml

# Wait for databases
kubectl wait --for=condition=ready pod \
  -l component=database \
  -n 1c-ai-stack \
  --timeout=180s

# 6. API Gateway
kubectl apply -f k8s/deployments/api-gateway.yaml

# 7. Ingress
kubectl apply -f k8s/ingress.yaml

# 8. Network Policies
kubectl apply -f security/network-policy.yaml
```

---

## 📊 Step 4: Deploy Monitoring

### 4.1 Docker Compose (development/staging):

```bash
docker-compose -f docker-compose.monitoring.yml up -d

# Access:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
# Alertmanager: http://localhost:9093
```

### 4.2 Kubernetes (production):

```bash
# Install Prometheus Operator
helm repo add prometheus-community \
  https://prometheus-community.github.io/helm-charts

helm install prometheus \
  prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.adminPassword=YOUR_SECURE_PASSWORD

# Access Grafana
kubectl port-forward -n monitoring \
  svc/prometheus-grafana 3000:80
```

---

## 🔄 Step 5: Data Migration

### 5.1 Create migration job:

```yaml
# k8s/jobs/migration-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: data-migration
  namespace: 1c-ai-stack
spec:
  template:
    spec:
      containers:
      - name: migrator
        image: 1c-ai/migrator:latest
        command: ["python", "migrate_all.py"]
        env:
        - name: POSTGRES_HOST
          value: postgres
        envFrom:
        - secretRef:
            name: postgres-secret
      restartPolicy: OnFailure
```

```bash
kubectl apply -f k8s/jobs/migration-job.yaml
kubectl logs -f job/data-migration -n 1c-ai-stack
```

---

## ✅ Step 6: Verification

### 6.1 Check all pods running:

```bash
kubectl get pods -n 1c-ai-stack

# Expected:
# NAME                           READY   STATUS    RESTARTS
# postgres-xxxxx                 1/1     Running   0
# neo4j-xxxxx                    1/1     Running   0
# api-gateway-xxxxx              1/1     Running   0
# api-gateway-xxxxx              1/1     Running   0
# api-gateway-xxxxx              1/1     Running   0
```

### 6.2 Test endpoints:

```bash
# Get external IP
kubectl get svc api-gateway -n 1c-ai-stack

# Test health
curl http://EXTERNAL_IP/health

# Test API
curl http://EXTERNAL_IP/api/graph/configurations
```

### 6.3 Check monitoring:

```bash
# Prometheus targets
open http://PROMETHEUS_URL/targets

# Grafana dashboards
open http://GRAFANA_URL
# Login: admin / YOUR_PASSWORD
# Import dashboard: monitoring/grafana/dashboards/overview.json
```

---

## 🔍 Step 7: Load Testing

```bash
# Install k6
brew install k6  # macOS
# or wget https://github.com/grafana/k6/releases

# Run load test
k6 run tests/load/api-load-test.js

# Monitor in Grafana during load test
```

---

## 📈 Step 8: Monitoring Setup

### 8.1 Import Grafana dashboards:

```bash
# Overview dashboard
curl -X POST http://admin:password@localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @monitoring/grafana/dashboards/overview.json
```

### 8.2 Configure alerts:

```bash
# Slack webhook
kubectl create secret generic alertmanager-config \
  --from-literal=SLACK_WEBHOOK_URL=$SLACK_WEBHOOK \
  -n monitoring

# Apply alertmanager config
kubectl apply -f monitoring/alertmanager/alertmanager.yml
```

### 8.3 Verify alerting:

```bash
# Test alert
kubectl exec -it deployment/api-gateway -n 1c-ai-stack -- killall python

# Check Alertmanager
open http://ALERTMANAGER_URL
# Should see firing alert within 2 minutes
```

---

## 🔒 Step 9: Security Hardening

### 9.1 Network policies:

```bash
kubectl apply -f security/network-policy.yaml
```

### 9.2 RBAC:

```bash
# Service account
kubectl create serviceaccount 1c-ai-sa -n 1c-ai-stack

# Role binding
kubectl create rolebinding 1c-ai-binding \
  --clusterrole=edit \
  --serviceaccount=1c-ai-stack:1c-ai-sa \
  -n 1c-ai-stack
```

### 9.3 Pod Security Standards:

```bash
kubectl label namespace 1c-ai-stack \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

---

## 💾 Step 10: Backup Strategy

### 10.1 Database backups:

```bash
# PostgreSQL backup cronjob
kubectl apply -f k8s/jobs/postgres-backup-cronjob.yaml

# Neo4j backup
kubectl apply -f k8s/jobs/neo4j-backup-cronjob.yaml
```

### 10.2 Manual backup:

```bash
# PostgreSQL
kubectl exec -it postgres-xxxxx -n 1c-ai-stack -- \
  pg_dump -U admin knowledge_base > backup.sql

# Neo4j
kubectl exec -it neo4j-xxxxx -n 1c-ai-stack -- \
  neo4j-admin backup --to=/backups
```

---

## 📊 Success Criteria

### ✅ Deployment successful if:

- [ ] All pods running and ready
- [ ] Health check endpoints respond
- [ ] API accessible via ingress
- [ ] SSL certificates valid
- [ ] Monitoring dashboards showing data
- [ ] Alerts configured and testing
- [ ] Backups running automatically
- [ ] Network policies applied
- [ ] Secrets properly managed
- [ ] Load test passed (>1000 req/s)

---

## 🎯 Post-Deployment

### Day 1:
- Monitor all services
- Check logs for errors
- Verify all alerts work
- Test all endpoints

### Week 1:
- Review metrics
- Optimize resource limits
- Fine-tune autoscaling
- Update documentation

### Month 1:
- Performance review
- Security audit
- Capacity planning
- User feedback

---

## 🔄 Rollback Plan

### If deployment fails:

```bash
# Helm rollback
helm rollback 1c-ai-stack -n 1c-ai-stack

# Or kubectl
kubectl rollout undo deployment/api-gateway -n 1c-ai-stack

# Check status
kubectl rollout status deployment/api-gateway -n 1c-ai-stack
```

---

## 📞 Support

- Monitoring: http://grafana.example.com
- Alerts: http://alertmanager.example.com
- Logs: kubectl logs
- Metrics: http://prometheus.example.com

---

**Production deployment complete! 🚀**



