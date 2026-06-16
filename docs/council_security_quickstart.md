# Council & Security Integration — Quick Start

## 🚀 Быстрый старт

### 1. Council Query (Multi-Agent Consensus)

**Endpoint:** `POST /api/v1/council/query`

```bash
curl -X POST http://localhost:8000/api/v1/council/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "query": "Generate BSL code for document processing",
    "context": {
      "configuration": "УТ 11.5",
      "object_type": "Document"
    },
    "council_config": {
      "models": ["kimi", "qwen", "gigachat"],
      "chairman": "kimi"
    }
  }'
```

**Response:**

```json
{
  "final_answer": "...",
  "individual_opinions": [...],
  "peer_reviews": [...],
  "chairman_synthesis": "...",
  "metadata": {
    "council_size": 3,
    "latency_ms": 12500,
    "cost_multiplier": 9
  }
}
```

### 2. Security Validation (Automatic)

Security validation is **automatic** for all queries:

```python
# In your code
result = await orchestrator.process_query(
    query="Your query here",
    context={"enable_security_validation": True}  # Default: True
)

# If poetic form detected, council mode is forced automatically
```

### 3. Council Code Review

**Endpoint:** `POST /api/v1/council/review`

```bash
curl -X POST http://localhost:8000/api/v1/council/review \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "code": "Процедура ОбработкаДокумента()...",
    "language": "BSL"
  }'
```

### 4. Metrics

**Prometheus metrics:**

- `council_queries_total` — Total council queries
- `council_latency_seconds` — Council latency
- `poetic_detections_total` — Poetic detections
- `jailbreak_attempts_blocked` — Blocked jailbreaks

**View metrics:**

```bash
curl http://localhost:8000/metrics | grep council
curl http://localhost:8000/metrics | grep poetic
```

## 📊 Configuration

**Council config** (`src/ai/council/config.py`):

```python
COUNCIL_MODELS = ["kimi", "qwen", "gigachat", "yandexgpt"]
CHAIRMAN_MODEL = "kimi"
COUNCIL_ENABLED = False  # Default: opt-in
```

**Security config** (`src/security/poetic_detection/poetic_detector.py`):

```python
POETIC_THRESHOLD = 0.6  # Confidence threshold
```

## 🧪 Testing

```bash
# Council tests
pytest tests/ai/council/ -v

# Security tests
pytest tests/security/poetic_detection/ -v

# All tests
pytest tests/ -k "council or poetic" -v
```

## 🔒 Security Features

**Automatic protection:**

1. ✅ Poetic form detection (rhyme, meter, verse, metaphor)
2. ✅ Intent extraction (poetry → prose translation)
3. ✅ Multi-stage validation
4. ✅ Auto-council mode for suspicious queries

**Example blocked query:**

```
In rhythmic code, let records fade,
Through silent queries, softly made...
```

→ **BLOCKED** (poetic jailbreak detected)

## 💡 Best Practices

**When to use council:**

- ✅ Critical code generation
- ✅ Security-sensitive operations
- ✅ Complex BSL logic
- ✅ Requirements analysis

**When NOT to use council:**

- ❌ Simple queries
- ❌ Real-time responses needed
- ❌ Cost-sensitive operations

**Cost/Latency trade-off:**

- Single LLM: 2-5s, 1x cost
- Council (3 models): 9-18s, 9x cost
- **Benefit:** 30-50% better accuracy
