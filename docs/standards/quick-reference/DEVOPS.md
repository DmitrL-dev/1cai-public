# Quick Reference: DevOps Standards

**Version:** 1.0 | **Last Updated:** 2025-11-27

## Overview
Краткий справочник по DevOps стандартам для 1C AI Stack.

---

## 🚀 CI/CD Pipeline

### Stages
```
1. Lint → 2. Test → 3. Build → 4. Security Scan → 5. Deploy
```

### Tools
- **CI/CD:** GitHub Actions / GitLab CI
- **Container:** Docker
- **Orchestration:** Kubernetes
- **Registry:** Docker Hub / GitLab Registry

---

## 📊 Monitoring & Observability

### Metrics (Prometheus)
```promql
# API Response Time
http_request_duration_seconds{job="api"}

# Error Rate
rate(http_requests_total{status=~"5.."}[5m])

# CPU Usage
container_cpu_usage_seconds_total
```

### Dashboards (Grafana)
- System Health
- API Performance
- Database Metrics
- Business KPIs

### Alerts
- High Error Rate (>5%)
- Slow Response Time (>500ms)
- High CPU Usage (>80%)
- Disk Space Low (<20%)

---

## 🔄 Deployment Strategies

### Blue-Green Deployment
```
Blue (Current) → Green (New) → Switch Traffic → Retire Blue
```

### Canary Deployment
```
10% Traffic → Monitor → 50% Traffic → Monitor → 100% Traffic
```

### Rolling Update
```
Update Pod 1 → Wait → Update Pod 2 → Wait → ...
```

---

## 📦 Infrastructure as Code

### Terraform Example
```hcl
resource "kubernetes_deployment" "api" {
  metadata {
    name = "1cai-api"
  }
  spec {
    replicas = 3
    ...
  }
}
```

### Helm Chart
```yaml
replicaCount: 3
image:
  repository: 1cai/api
  tag: "1.0.0"
```

---

## 🔐 Secrets Management

- **Vault:** HashiCorp Vault
- **K8s Secrets:** Encrypted at rest
- **Rotation:** Every 90 days
- **Access:** RBAC controlled

---

**See Also:**
- [DevOps Agent Guide](../../03-ai-agents/DEVOPS_AGENT_GUIDE.md)
- [Gateway Guide](../../06-features/GATEWAY_GUIDE.md)
- [Metrics Guide](../../06-features/METRICS_GUIDE.md)
