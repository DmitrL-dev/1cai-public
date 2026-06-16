# Documentation Generator — Руководство пользователя

**Версия:** 1.0 | **Статус:** ⚠️ In Development | **API:** `/api/v1/documentation` (planned)

## Обзор
**Documentation Generator** — автоматическая генерация документации из кода. API docs, user guides, architecture diagrams.

**Возможности (planned):**
- 📚 API Docs Generation
- 📖 User Guide Generation
- 🏗️ Diagram Generation
- 🔄 Doc Sync

## Status
⚠️ **В разработке** - базовая функциональность через Technical Writer Agent.

## Current Workaround
```python
# Используйте Technical Writer Agent
docs = await client.post("/api/v1/assistants/technical-writer/generate", json={
    "code": "Функция ПолучитьДанные()...",
    "type": "api_documentation"
})

print(docs.json()["documentation"])
```

## Planned Features
```python
# Автоматическая генерация (planned)
api_docs = await client.post("/api/v1/documentation/generate/api", json={
    "source_path": "/path/to/code",
    "format": "openapi"
})

user_guide = await client.post("/api/v1/documentation/generate/guide", json={
    "module": "dashboard",
    "audience": "end_users"
})

diagrams = await client.post("/api/v1/documentation/generate/diagrams", json={
    "source_path": "/path/to/code",
    "type": "c4"  # C4 model diagrams
})
```

## FAQ
**Q: Когда будет готов?** A: Q2 2026  
**Q: Что использовать сейчас?** A: Technical Writer Agent

---
**Документация:** [Technical Writer Guide](../03-ai-agents/TECHNICAL_WRITER_GUIDE.md)
