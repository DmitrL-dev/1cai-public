# Graph & Hybrid Search Guide

API `src/api/graph_api.py` и сервис `src/services/hybrid_search.py` предоставляют MATCH-запросы к Neo4j, семантический поиск по Qdrant/Elasticsearch и комбинированные результаты. Это руководство описывает пользовательские сценарии и технические детали.

---

## 1. Пользовательские сценарии

| Сценарий | Эндпоинт | Пример |
| --- | --- | --- |
| **Проверить доступность графа** | `GET /api/v1/graph/health` | Возвращает состояние Neo4j, Qdrant, Embeddings. |
| **Выполнить MATCH-запрос** | `POST /api/v1/graph/query` | `{"query":"MATCH (n:Module)-[:DEPENDS_ON]->(m) RETURN n,m LIMIT 10"}` |
| **Получить зависимости функции** | `POST /api/v1/graph/function-dependencies` | `{"function":"UpdateSales","limit":5}` |
| **Семантический поиск** | `POST /api/v1/graph/semantic-search` | `{"text":"как обновить остатки","limit":5}` |
| **Гибридный поиск (текст + вектор)** | `POST /api/v1/search/hybrid` | `{"query":"оптимизация SQL","limit":10}` |

Ответы содержат поля `execution_time_ms`, `source` и список узлов/документов.

---

## 2. Ограничения и безопасность

- MATCH запросы проходят через `dangerous_patterns` — запрещены `DELETE`, `MERGE`, `CALL` вне whitelist.
- Семантический поиск обрезает `text` до `MAX_SEMANTIC_QUERY_LENGTH` (см. `src/api/graph_api.py`).
- Hybrid search автоматически деградирует, если недоступен EmbeddingService/Qdrant (`src/services/hybrid_search.py`).
- В офлайн-режиме можно загрузить предварительно рассчитанные embeddings (`scripts/knowledge/build_vector_store.py`).

---

## 3. Техническая конфигурация

1. **Neo4j** — `config/production/neo4j.conf` или ENV `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`. Клиент: `src/db/neo4j_client.py`.
2. **Qdrant** — `config/production/qdrant.yaml`, клиент `src/db/qdrant_client.py`.
3. **Elasticsearch** — используется гибридным поиском для полнотекстовой части (`ES_HOST`, `ES_USER`, `ES_PASSWORD`).
4. **EmbeddingService** — `src/services/embedding_service.py` (поддерживает OpenAI/Qwen/Kimi). Настраивается через `config/llm_providers.yaml`.

---

## 4. Тесты и мониторинг

- **Unit**: `tests/unit/test_graph_api.py`, `tests/unit/test_hybrid_search.py`, `tests/unit/test_embedding_service.py`.
- **Integration**: `tests/integration/test_graph_api_integration.py`, `tests/integration/test_hybrid_search_integration.py`.
- **Метрики**:
  - `graph_query_duration_seconds`
  - `hybrid_search_fallback_total`
  - `semantic_search_truncated_total`

Grafana дашборд: `monitoring/grafana/dashboards/ai_services.json` (панель “Graph/Hybrid Search”).

---

## 5. Примеры CLI

```bash
# Семантический поиск
curl -X POST http://localhost:6001/api/v1/graph/semantic-search \
     -H "Content-Type: application/json" \
     -d '{"text":"как рассчитать KPI","limit":3}'

# Hybrid поиск
curl -X POST http://localhost:6001/api/v1/search/hybrid \
     -H "Content-Type: application/json" \
     -d '{"query":"обновление документов","limit":5}'
```

---

## 6. Типичные проблемы

| Симптом | Причина | Решение |
| --- | --- | --- |
| 503 при `/graph/query` | Neo4j недоступен | проверить `docker-compose logs neo4j` или `kubectl logs neo4j`. |
| Пустой ответ на semantic-search | EmbeddingService вернул ошибку или текст > лимита | проверить `logs/embedding_service.log`, сократить запрос. |
| Гибридный поиск возвращает только текстовые результаты | Нет embeddings или Qdrant недоступен | запустить `scripts/knowledge/build_vector_store.py`, проверить Qdrant. |

---

**Доп. материалы:**  
- `analysis/integration_tests_plan.md` — матрица тестов Graph/Hybrid.  
- `docs/06-features/EDT_PARSER_GUIDE.md` — откуда берутся исходные связи.  
- `Src/services/hybrid_search.py` — подробный код деградации и RRF-смешивания.

