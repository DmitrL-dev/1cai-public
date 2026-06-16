# Unified Change Graph — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/graph`

## Обзор
**Unified Change Graph** — построение графа зависимостей кода. Анализ влияния изменений, поиск связей.

**Возможности:** 🔗 Dependency Graph | 📊 Impact Analysis | 🔍 Code Search | 🎯 Change Tracking | 📈 Visualization

## Quick Start
```python
# Построить граф из кода
graph = await client.post("/api/v1/graph/build", json={
    "source_path": "/path/to/1c/project",
    "language": "bsl"
})

# Анализ влияния изменений
impact = await client.post("/api/v1/graph/impact", json={
    "changed_files": ["CommonModules/Работа.bsl"],
    "graph_id": graph["id"]
})

print(f"Affected modules: {len(impact.json()['affected_modules'])}")
```

## API Reference
```http
POST /api/v1/graph/build
{
  "source_path": "/project",
  "language": "bsl",
  "include_tests": true
}

Response:
{
  "id": "graph_123",
  "nodes": 1523,
  "edges": 4567,
  "build_time_ms": 3456
}
```

## Impact Analysis
```http
POST /api/v1/graph/impact
{
  "graph_id": "graph_123",
  "changed_files": ["Module1.bsl", "Module2.bsl"]
}

Response:
{
  "affected_modules": ["Module3", "Module4", "Module5"],
  "affected_tests": ["Test1", "Test2"],
  "risk_score": 0.75,
  "recommendations": [
    "Run integration tests",
    "Review Module3 carefully"
  ]
}
```

## Visualization
```python
# Экспорт графа для визуализации
viz = await client.get(f"/api/v1/graph/{graph_id}/export?format=dot")

# Или JSON для D3.js
json_graph = await client.get(f"/api/v1/graph/{graph_id}/export?format=json")
```

## Use Cases
1. **Pre-merge analysis:** Оценка влияния PR
2. **Refactoring planning:** Понимание зависимостей
3. **Test selection:** Какие тесты запустить
4. **Architecture review:** Визуализация структуры

## FAQ
**Q: Поддерживаются ли другие языки?** A: Да, JavaScript, Python, SQL  
**Q: Как часто обновлять граф?** A: После каждого merge в main

---
**Документация:** [Unified Change Graph API](../api/UNIFIED_CHANGE_GRAPH_API.md)
