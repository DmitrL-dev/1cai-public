# 📊 Monitoring

See [MONITORING_GUIDE.md](MONITORING_GUIDE.md) for complete monitoring setup guide.

---

## Quick Start:

```bash
# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# Access:
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000
```

---

## Quick Health Checks:

```bash
# FastAPI
curl http://localhost:8000/health

# PostgreSQL
docker exec 1c-ai-postgres pg_isready

# Redis
docker exec 1c-ai-redis redis-cli PING
```

---

For complete guide see: [MONITORING_GUIDE.md](MONITORING_GUIDE.md)

