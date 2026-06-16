# Nested Learning - API Documentation

**Версия:** 1.0  
**Статус:** ✅ Production Ready  
**API Endpoint:** `/api/v1/nested-learning`

---

## Обзор

**Nested Learning** — революционная технология многоуровневого обучения AI моделей для 1C:Предприятие. Позволяет моделям учиться на разных уровнях абстракции одновременно.

**Ключевые возможности:**
- 🧠 Multi-level Learning (3 уровня)
- 🎯 Adaptive Model Selection
- 📊 Performance Optimization
- 🔄 Continuous Learning
- 📈 Quality Improvement

---

## API Reference

### Start Training Session

```http
POST /api/v1/nested-learning/train
Content-Type: application/json

{
  "dataset": "bsl_code_samples",
  "levels": 3,
  "model": "gpt-4-turbo",
  "config": {
    "level1": {"focus": "syntax"},
    "level2": {"focus": "semantics"},
    "level3": {"focus": "architecture"}
  }
}

Response:
{
  "session_id": "nl_123",
  "status": "training",
  "estimated_time": "2h 30m",
  "levels_progress": {
    "level1": 0,
    "level2": 0,
    "level3": 0
  }
}
```

### Get Training Status

```http
GET /api/v1/nested-learning/train/{session_id}

Response:
{
  "session_id": "nl_123",
  "status": "in_progress",
  "progress": 45,
  "current_level": 2,
  "levels_progress": {
    "level1": 100,
    "level2": 45,
    "level3": 0
  },
  "metrics": {
    "accuracy": 0.87,
    "loss": 0.23
  }
}
```

### Inference with Nested Learning

```http
POST /api/v1/nested-learning/infer
{
  "model_id": "nl_model_123",
  "input": "Функция ПолучитьДанные()...",
  "use_all_levels": true
}

Response:
{
  "prediction": "...",
  "confidence": 0.95,
  "level_contributions": {
    "level1": 0.3,
    "level2": 0.5,
    "level3": 0.2
  }
}
```

### Get Model Info

```http
GET /api/v1/nested-learning/models/{model_id}

Response:
{
  "id": "nl_model_123",
  "name": "BSL Code Generator",
  "levels": 3,
  "trained_at": "2025-11-27T12:00:00Z",
  "metrics": {
    "accuracy": 0.92,
    "precision": 0.89,
    "recall": 0.91
  },
  "performance": {
    "inference_time_ms": 234,
    "throughput": "150 req/s"
  }
}
```

---

## Python SDK

```python
from nested_learning import NestedLearningClient

# Initialize client
client = NestedLearningClient(api_key="your_key")

# Start training
session = client.train(
    dataset="bsl_samples",
    levels=3,
    config={
        "level1": {"focus": "syntax"},
        "level2": {"focus": "semantics"},
        "level3": {"focus": "architecture"}
    }
)

# Monitor progress
while session.status != "completed":
    status = client.get_status(session.id)
    print(f"Progress: {status.progress}%")
    time.sleep(60)

# Use model for inference
result = client.infer(
    model_id=session.model_id,
    input="Функция ПолучитьДанные()..."
)

print(f"Prediction: {result.prediction}")
print(f"Confidence: {result.confidence}")
```

---

## Configuration

```yaml
# nested_learning.yml
levels:
  - name: "syntax"
    model: "gpt-3.5-turbo"
    focus: "code syntax and structure"
    
  - name: "semantics"
    model: "gpt-4"
    focus: "code meaning and logic"
    
  - name: "architecture"
    model: "gpt-4-turbo"
    focus: "system design and patterns"

training:
  batch_size: 32
  epochs: 10
  learning_rate: 0.001
  
optimization:
  adaptive_selection: true
  performance_threshold: 0.85
```

---

## Error Codes

- `400` - Invalid request
- `404` - Model not found
- `429` - Rate limit exceeded
- `500` - Training failed
- `503` - Service unavailable

---

## Rate Limits

- Training: 10 sessions/hour
- Inference: 1000 requests/minute
- Model listing: 100 requests/minute

---

**Документация:**
- [User Guide](user_guide.md)
- [Monitoring Dashboards](monitoring_dashboards.md)
- [Performance Benchmarks](performance_benchmarks.md)
