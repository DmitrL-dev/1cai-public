# LLM Council API Documentation

## Overview

The LLM Council provides multi-agent consensus for improved AI response quality through a 3-stage process:

1. **Stage 1:** Multiple models provide independent responses
2. **Stage 2:** Models peer-review each other's responses
3. **Stage 3:** Chairman synthesizes final answer

## Endpoints

### POST /api/v1/council/query

Execute query with council consensus.

**Request:**

```json
{
  "query": "string",
  "context": {
    "configuration": "string",
    "object_type": "string"
  },
  "council_config": {
    "models": ["kimi", "qwen", "gigachat"],
    "chairman": "kimi",
    "timeout": 60
  }
}
```

**Response:**

```json
{
  "final_answer": "string",
  "individual_opinions": [
    {
      "model": "kimi",
      "response": "string"
    }
  ],
  "peer_reviews": [
    {
      "reviewer": "kimi",
      "rankings": [1, 2, 3],
      "reasoning": "string"
    }
  ],
  "chairman_synthesis": "string",
  "metadata": {
    "council_size": 3,
    "chairman": "kimi",
    "latency_ms": 12500,
    "cost_multiplier": 9
  }
}
```

### GET /api/v1/council/config

Get current council configuration.

**Response:**

```json
{
  "enabled": false,
  "default_models": ["kimi", "qwen", "gigachat", "yandexgpt"],
  "default_chairman": "kimi",
  "min_council_size": 2,
  "max_council_size": 8
}
```

### GET /api/v1/council/health

Check council health status.

**Response:**

```json
{
  "status": "healthy",
  "message": "Council orchestrator ready"
}
```

## Security Features

### Automatic Validation

All queries are automatically validated for:

- **Poetic form detection** (rhyme, meter, verse, metaphor)
- **Intent extraction** (poetry → prose translation)
- **Dangerous keywords** (SQL injection, system commands)

### Auto-Council Mode

When poetic form is detected (confidence > 0.6), council mode is automatically enabled for enhanced security.

## Performance

| Mode               | Latency | Cost | Accuracy |
| ------------------ | ------- | ---- | -------- |
| Single LLM         | 2-5s    | 1x   | Baseline |
| Council (3 models) | 9-18s   | 9x   | +30-50%  |

## Best Practices

**Use Council For:**

- ✅ Critical code generation
- ✅ Security-sensitive operations
- ✅ Complex BSL logic
- ✅ Requirements analysis

**Avoid Council For:**

- ❌ Simple queries
- ❌ Real-time responses
- ❌ Cost-sensitive operations

## Examples

### Basic Council Query

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/council/query",
    json={
        "query": "Generate BSL code for document processing",
        "context": {"configuration": "УТ 11.5"}
    },
    headers={"Authorization": f"Bearer {token}"}
)

result = response.json()
print(result["final_answer"])
```

### Custom Council Configuration

```python
response = httpx.post(
    "http://localhost:8000/api/v1/council/query",
    json={
        "query": "Review this BSL code for security issues",
        "council_config": {
            "models": ["kimi", "qwen"],  # Only 2 models
            "chairman": "kimi",
            "timeout": 30
        }
    }
)
```

### Manual Council Mode

```python
# Force council mode via context
response = httpx.post(
    "http://localhost:8000/api/v1/orchestrator/query",
    json={
        "query": "Generate code",
        "context": {"use_council": True}
    }
)
```

## Error Handling

**Common Errors:**

- `400 Bad Request` — Invalid council configuration
- `500 Internal Server Error` — Council processing error
- `503 Service Unavailable` — Council not initialized

**Error Response:**

```json
{
  "error": "Query blocked by security filters",
  "reason": "Potentially harmful intent detected in poetic form",
  "details": {
    "poetic_detected": true,
    "stage": "intent_extraction"
  }
}
```

## Monitoring

**Prometheus Metrics:**

- `council_queries_total` — Total queries
- `council_latency_seconds` — Latency distribution
- `poetic_detections_total` — Poetic form detections
- `jailbreak_attempts_blocked` — Blocked attempts

**Grafana Dashboard:**

- View at `/grafana/d/council-security`
