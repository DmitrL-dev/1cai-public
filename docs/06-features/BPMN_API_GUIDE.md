# BPMN API — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/bpmn`

## Обзор
**BPMN API** — работа с BPMN-диаграммами. Генерация, валидация, экспорт BPMN 2.0.

**Возможности:** 📊 BPMN Generation | ✅ Validation | 📤 Export (XML, SVG, PNG) | 📥 Import | 🔄 Conversion

## Quick Start
```python
# Генерация BPMN из текста
bpmn = await client.post("/api/v1/bpmn/generate", json={
    "description": "Процесс согласования документа: создание -> проверка -> утверждение -> архив"
})
print(bpmn.json()["xml"])  # BPMN 2.0 XML
```

## API Reference
```http
POST /api/v1/bpmn/generate
{"description": "Order processing: receive -> validate -> fulfill -> ship"}

Response:
{
  "xml": "<?xml version='1.0'?>...",
  "svg": "<svg>...</svg>",
  "elements": ["start", "task1", "task2", "end"]
}
```

## Export Formats
```python
# XML
xml = await client.get("/api/v1/bpmn/{id}/export?format=xml")

# SVG для отображения
svg = await client.get("/api/v1/bpmn/{id}/export?format=svg")

# PNG для документации
png = await client.get("/api/v1/bpmn/{id}/export?format=png")
```

## FAQ
**Q: Поддерживается ли BPMN 2.0?** A: Да, полная поддержка  
**Q: Можно ли импортировать из Camunda?** A: Да

---
**Документация:** [BPMN API](../api/BPMN_API.md)
