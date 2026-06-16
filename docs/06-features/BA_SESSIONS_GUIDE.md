# BA Sessions — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/ba_sessions`

## Обзор
**BA Sessions API** — управление сессиями бизнес-аналитика. Создание, управление, экспорт результатов.

**Возможности:** 📝 Session Management | 📊 Requirements Tracking | 🎯 KPI Calculation | 📤 Export Results

## Quick Start
```python
# Создать сессию
session = await client.post("/api/v1/ba_sessions/create", json={
    "project": "1C Integration",
    "stakeholders": ["Product Owner", "Tech Lead"]
})

# Добавить требования
await client.post(f"/api/v1/ba_sessions/{session['id']}/requirements", json={
    "text": "Система должна поддерживать OAuth 2.0 аутентификацию"
})

# Экспорт
results = await client.get(f"/api/v1/ba_sessions/{session['id']}/export?format=pdf")
```

## API Reference
```http
POST /api/v1/ba_sessions/create
{
  "project": "CRM Integration",
  "stakeholders": ["CEO", "CTO"],
  "duration_minutes": 60
}

Response:
{
  "id": "session_123",
  "status": "active",
  "created_at": "2025-11-27T12:00:00Z"
}
```

## Export Formats
- PDF — полный отчет
- DOCX — редактируемый документ
- JSON — для интеграций
- BPMN — процессные диаграммы

## FAQ
**Q: Можно ли совместно редактировать?** A: Да, через WebSocket  
**Q: Сохраняется ли история изменений?** A: Да, полная история

---
**Документация:** [BA Sessions API](../api/BA_SESSIONS_API.md)
