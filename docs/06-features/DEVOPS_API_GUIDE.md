# DevOps API — User Guide

**Version:** 1.0 | **Status:** ✅ Production Ready

## Overview
DevOps API предоставляет endpoints для автоматизации CI/CD, мониторинга, deployment.

## Endpoints

### Analyze Logs
```http
POST /api/v1/devops/analyze-logs
{
  "log_path": "/var/log/1c",
  "time_range": "24h"
}

Response:
{
  "errors": 12,
  "warnings": 45,
  "insights": [...]
}
```

### Optimize Pipeline
```http
POST /api/v1/devops/optimize-pipeline
{
  "pipeline_file": "ci-cd.yml"
}

Response:
{
  "optimized_pipeline": "...",
  "improvements": [...]
}
```

### Cost Analysis
```http
GET /api/v1/devops/cost-analysis?period=month
```

### Auto-scaling
```http
POST /api/v1/devops/autoscale
{
  "min_instances": 2,
  "max_instances": 10
}
```

**See:** [DevOps Agent Guide](../03-ai-agents/DEVOPS_AGENT_GUIDE.md)
