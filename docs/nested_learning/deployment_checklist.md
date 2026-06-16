# Nested Learning - Deployment Checklist

**Версия:** 1.0 | **For:** DevOps, SRE

## Pre-Deployment

### Infrastructure

- [ ] GPU servers provisioned (NVIDIA A100 recommended)
- [ ] PostgreSQL 15+ deployed
- [ ] Redis 7.0+ deployed
- [ ] S3-compatible storage configured
- [ ] Monitoring (Prometheus + Grafana) setup

### Configuration

- [ ] Environment variables set
- [ ] Model registry initialized
- [ ] API keys configured
- [ ] Rate limits configured
- [ ] Logging configured

### Testing

- [ ] Unit tests passed (>90% coverage)
- [ ] Integration tests passed
- [ ] Performance tests passed
- [ ] Load tests passed (1000 req/s)

## Deployment Steps

### 1. Database Setup

```bash
# Create database
psql -U postgres -c "CREATE DATABASE nested_learning;"

# Run migrations
alembic upgrade head

# Verify
psql -U postgres -d nested_learning -c "SELECT * FROM models LIMIT 1;"
```

### 2. Model Deployment

```bash
# Upload pre-trained models to S3
aws s3 cp models/ s3://bucket/nested-learning/models/ --recursive

# Register models in database
python scripts/register_models.py
```

### 3. Service Deployment

```bash
# Build Docker image
docker build -t nested-learning:latest .

# Deploy to Kubernetes
kubectl apply -f k8s/nested-learning-deployment.yml

# Verify pods
kubectl get pods -l app=nested-learning
```

### 4. Configuration

```bash
# Set environment variables
export NESTED_LEARNING_ENABLED=true
export NESTED_LEARNING_LEVELS=3
export NESTED_LEARNING_GPU=true

# Restart services
kubectl rollout restart deployment/nested-learning
```

## Post-Deployment

### Verification

- [ ] Health check passes: `GET /health`
- [ ] Training endpoint works: `POST /api/v1/nested-learning/train`
- [ ] Inference endpoint works: `POST /api/v1/nested-learning/infer`
- [ ] Metrics exported to Prometheus
- [ ] Grafana dashboards showing data

### Monitoring

```bash
# Check logs
kubectl logs -f deployment/nested-learning

# Check metrics
curl http://localhost:8000/metrics | grep nested_learning

# Check Grafana
open http://grafana:3000/d/nested-learning
```

### Performance Testing

```bash
# Load test
k6 run load_test.js

# Expected results:
# - p95 latency < 500ms
# - Throughput > 100 req/s
# - Error rate < 0.1%
```

## Rollback Plan

```bash
# If issues occur:
kubectl rollout undo deployment/nested-learning

# Verify rollback
kubectl rollout status deployment/nested-learning
```

## Troubleshooting

**Issue:** High latency  
**Solution:** Check GPU utilization, increase replicas

**Issue:** Out of memory  
**Solution:** Reduce batch size, add more RAM

**Issue:** Training fails  
**Solution:** Check dataset format, verify GPU drivers

## Success Criteria

✅ All health checks pass  
✅ Latency p95 < 500ms  
✅ Throughput > 100 req/s  
✅ Error rate < 0.1%  
✅ Monitoring dashboards working  
✅ No critical alerts

---

**См. также:**
- [Implementation Plan](implementation_plan.md)
- [Monitoring Dashboards](monitoring_dashboards.md)
