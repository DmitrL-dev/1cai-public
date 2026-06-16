# Scenario Hub — Руководство пользователя

**Версия:** 1.0 | **Статус:** ⚠️ Stub | **API:** `/api/v1/scenario_hub` (planned)

## Обзор
**Scenario Hub** — центр управления сценариями автоматизации. Создание, выполнение, мониторинг сценариев.

**Возможности (planned):**
- 📝 Scenario Creation
- ▶️ Scenario Execution
- 📊 Monitoring
- 🎯 Recommendations

## Status
⚠️ **В разработке** - модуль находится в стадии stub implementation.

## Planned Features
```python
# Создание сценария (planned)
scenario = await client.post("/api/v1/scenario_hub/create", json={
    "name": "Daily backup",
    "steps": [
        {"action": "backup_database"},
        {"action": "upload_to_s3"},
        {"action": "send_notification"}
    ],
    "schedule": "0 2 * * *"  # Каждый день в 2:00
})

# Выполнение (planned)
await client.post(f"/api/v1/scenario_hub/{scenario['id']}/execute")
```

## FAQ
**Q: Когда будет готов?** A: Планируется в Q1 2026  
**Q: Можно ли использовать сейчас?** A: Нет, только stub

---
**Документация:** [Scenario Hub Roadmap](../roadmap/SCENARIO_HUB.md)
