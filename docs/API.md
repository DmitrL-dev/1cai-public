# 📡 API Documentation

See [API_REFERENCE.md](API_REFERENCE.md) for complete API reference.

---

## Quick Links:

- **Full API Reference:** [API_REFERENCE.md](API_REFERENCE.md)
- **Interactive Docs:** http://localhost:8000/docs (Swagger UI)
- **OpenAPI Spec:** http://localhost:8000/openapi.json

---

## Quick Examples:

### Search Code

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"расчет НДС","limit":10}'
```

### Generate Code

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"description":"функция для отправки email"}'
```

---

For complete documentation see: [API_REFERENCE.md](API_REFERENCE.md)

