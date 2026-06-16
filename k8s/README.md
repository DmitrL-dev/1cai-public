# Kubernetes Deployment

## Enterprise 1C AI Development Stack

Production deployment на Kubernetes.

---

## 📋 Prerequisites

- Kubernetes cluster (1.25+)
- kubectl configured
- Helm 3 (для Helm Chart)
- Storage provisioner
- Ingress controller (nginx recommended)

---

## 🚀 Quick Deploy

### Метод 1: Kubectl (ручной)

```bash
# 1. Create namespace
kubectl apply -f namespace.yaml

# 2. Create secrets
kubectl create secret generic postgres-secret \
  --from-literal=username=admin \
  --from-literal=password=YOUR_PASSWORD \
  -n 1c-ai-stack

kubectl create secret generic neo4j-secret \
  --from-literal=auth=neo4j/YOUR_PASSWORD \
  -n 1c-ai-stack

# 3. Apply ConfigMaps
kubectl apply -f configmaps/

# 4. Create Persistent Volumes
kubectl apply -f persistent-volumes/

# 5. Deploy databases
kubectl apply -f deployments/postgres.yaml
kubectl apply -f deployments/neo4j.yaml

# 6. Deploy API
kubectl apply -f deployments/api-gateway.yaml

# 7. Setup Ingress
kubectl apply -f ingress.yaml

# 8. Check status
kubectl get pods -n 1c-ai-stack
```

### Метод 2: Helm Chart (рекомендуется)

```bash
# 1. Install chart
helm install 1c-ai-stack ./helm/1c-ai-stack \
  --namespace 1c-ai-stack \
  --create-namespace \
  --set postgresql.password=YOUR_PASSWORD \
  --set neo4j.password=YOUR_PASSWORD

# 2. Check status
helm status 1c-ai-stack -n 1c-ai-stack

# 3. Get services
kubectl get svc -n 1c-ai-stack
```

---

## 📊 Verify Deployment

```bash
# Pods status
kubectl get pods -n 1c-ai-stack

# Services
kubectl get svc -n 1c-ai-stack

# Logs
kubectl logs -f deployment/api-gateway -n 1c-ai-stack

# Port forward for testing
kubectl port-forward svc/api-gateway 8080:80 -n 1c-ai-stack
```

---

## 🔧 Configuration

### Secrets (IMPORTANT!)

```bash
# PostgreSQL
kubectl create secret generic postgres-secret \
  --from-literal=username=admin \
  --from-literal=password=STRONG_PASSWORD \
  -n 1c-ai-stack

# Neo4j
kubectl create secret generic neo4j-secret \
  --from-literal=auth=neo4j/STRONG_PASSWORD \
  -n 1c-ai-stack

# API keys
kubectl create secret generic api-secrets \
  --from-literal=GITHUB_TOKEN=your_token \
  --from-literal=OPENAI_API_KEY=your_key \
  -n 1c-ai-stack
```

### Persistent Storage

Edit `persistent-volumes/*.yaml` to match your storage:
- Local path
- NFS
- Cloud storage (AWS EBS, GCP PD, Azure Disk)

---

## 📈 Scaling

### Manual scaling:

```bash
# Scale API Gateway
kubectl scale deployment api-gateway --replicas=5 -n 1c-ai-stack
```

### Auto-scaling (HPA already configured):

```bash
# Check HPA
kubectl get hpa -n 1c-ai-stack

# Describe HPA
kubectl describe hpa api-gateway-hpa -n 1c-ai-stack
```

---

## 🔒 Security

### Network Policies

```bash
# Apply network policies
kubectl apply -f ../security/network-policy.yaml
```

### RBAC (if needed)

```bash
# Create service account
kubectl create serviceaccount 1c-ai-sa -n 1c-ai-stack

# Bind role
kubectl create rolebinding 1c-ai-binding \
  --clusterrole=edit \
  --serviceaccount=1c-ai-stack:1c-ai-sa \
  -n 1c-ai-stack
```

---

## 📊 Monitoring

Monitoring stack included in `docker-compose.monitoring.yml`

Or deploy to Kubernetes:
```bash
# Prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

# Use provided dashboards
kubectl apply -f ../monitoring/grafana/dashboards/
```

---

## 🔄 Updates

### Rolling update:

```bash
# Update image
kubectl set image deployment/api-gateway \
  api=1c-ai/api-gateway:1.1.0 \
  -n 1c-ai-stack

# Check rollout
kubectl rollout status deployment/api-gateway -n 1c-ai-stack
```

### Rollback:

```bash
kubectl rollout undo deployment/api-gateway -n 1c-ai-stack
```

---

## 🗑️ Cleanup

```bash
# Delete namespace (removes everything)
kubectl delete namespace 1c-ai-stack

# Or use Helm
helm uninstall 1c-ai-stack -n 1c-ai-stack
```

---

## 📞 Troubleshooting

### Pod not starting:

```bash
kubectl describe pod POD_NAME -n 1c-ai-stack
kubectl logs POD_NAME -n 1c-ai-stack
```

### Service not accessible:

```bash
kubectl get svc -n 1c-ai-stack
kubectl describe svc SERVICE_NAME -n 1c-ai-stack
```

### PVC not binding:

```bash
kubectl get pvc -n 1c-ai-stack
kubectl describe pvc PVC_NAME -n 1c-ai-stack
```

---

## 📚 Resources

- [Kubernetes Docs](https://kubernetes.io/docs/)
- [Helm Docs](https://helm.sh/docs/)
- Main project: [START_HERE.md](../docs/01-getting-started/README.md)







