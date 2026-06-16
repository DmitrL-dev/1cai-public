# Knowledge Base — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/knowledge_base`

## Обзор
**Knowledge Base Module** — база знаний для хранения и поиска информации. Документация, примеры кода, best practices.

**Возможности:** 📚 Document Storage | 🔍 Semantic Search | 🏷️ Tagging | 📊 Analytics | 🔄 Versioning | 📤 Import/Export

## Quick Start

```python
# Добавить документ
await client.post("/api/v1/knowledge_base/documents", json={
    "title": "Как работать с запросами в 1C",
    "content": "Для создания запроса используйте...",
    "tags": ["1c", "sql", "queries"],
    "category": "tutorials"
})

# Поиск
results = await client.get("/api/v1/knowledge_base/search?q=запросы")
for doc in results.json()["results"]:
    print(f"{doc['title']} (relevance: {doc['score']})")
```

## API Reference

### Add Document
```http
POST /api/v1/knowledge_base/documents
{
  "title": "BSL Best Practices",
  "content": "1. Используйте параметризованные запросы...",
  "tags": ["bsl", "best-practices"],
  "category": "guides"
}
```

### Semantic Search
```http
GET /api/v1/knowledge_base/search?q=как оптимизировать запросы

Response:
{
  "results": [
    {
      "id": "doc_123",
      "title": "Оптимизация SQL запросов",
      "snippet": "...используйте индексы для <mark>оптимизации</mark>...",
      "score": 0.95,
      "tags": ["sql", "performance"]
    }
  ]
}
```

### Get Recommendations
```http
GET /api/v1/knowledge_base/recommendations?context=writing_bsl_code

Response:
{
  "recommendations": [
    {"title": "BSL Best Practices", "relevance": 0.92},
    {"title": "Common BSL Mistakes", "relevance": 0.88}
  ]
}
```

## RAG Integration

```python
# Использование KB для RAG
async def answer_question(question: str):
    # Поиск релевантных документов
    docs = await client.get(f"/api/v1/knowledge_base/search?q={question}")
    
    # Формирование контекста
    context = "\n\n".join([doc["content"] for doc in docs.json()["results"][:3]])
    
    # Генерация ответа с LLM
    answer = await llm.generate(
        prompt=f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
    )
    
    return answer
```

## Import from External Sources

```python
# Импорт из Confluence
await client.post("/api/v1/knowledge_base/import/confluence", json={
    "space_key": "DEV",
    "url": "https://confluence.company.com"
})

# Импорт из Markdown files
await client.post("/api/v1/knowledge_base/import/markdown", files={
    "files": open("docs.zip", "rb")
})
```

## FAQ
**Q: Поддерживается ли полнотекстовый поиск?** A: Да, через PostgreSQL FTS + semantic search  
**Q: Можно ли прикреплять файлы?** A: Да, PDF, DOCX, TXT

---

**Документация:** [Knowledge Base API](../api/KNOWLEDGE_BASE_API.md)
