# Performance Benchmarks для новых компонентов

**Версия:** 1.0.0  
**Дата:** 2025-01-XX  
**Статус:** ✅ Реализовано

---

## Обзор

Данный документ описывает performance benchmarks для новых компонентов платформы:
- **Scenario Recommender** - рекомендация сценариев на основе Unified Change Graph
- **Impact Analyzer** - анализ влияния изменений через граф
- **LLM Provider Abstraction** - выбор LLM провайдера
- **Intelligent Cache** - интеллектуальное кэширование

Все benchmarks находятся в `tests/performance/test_new_components_performance.py`.

---

## Методология

### Инструменты
- **pytest** - фреймворк для тестирования
- **statistics** - вычисление перцентилей (p50, p95, p99)
- **time** - измерение времени выполнения

### Метрики
- **p50** (медиана) - 50% запросов быстрее этого времени
- **p95** - 95% запросов быстрее этого времени
- **p99** - 99% запросов быстрее этого времени

### Целевые показатели
Все benchmarks имеют целевые показатели производительности, которые должны быть достигнуты для production-ready компонентов.

---

## Scenario Recommender

### Тест 1: Малый граф (100 узлов)

**Цель:** Проверить производительность рекомендаций на небольшом графе.

**Параметры:**
- Размер графа: 100 узлов
- Количество итераций: 50
- Максимальное количество рекомендаций: 5

**Целевые показатели:**
- p95 < 50ms

**Результаты:**
```python
@pytest.mark.asyncio
async def test_performance_scenario_recommender_small_graph()
```

**Использование:**
```bash
pytest tests/performance/test_new_components_performance.py::test_performance_scenario_recommender_small_graph -v
```

---

### Тест 2: Большой граф (1000 узлов)

**Цель:** Проверить производительность рекомендаций на большом графе.

**Параметры:**
- Размер графа: 1000 узлов
- Количество итераций: 20
- Максимальное количество рекомендаций: 5

**Целевые показатели:**
- p95 < 200ms

**Результаты:**
```python
@pytest.mark.asyncio
async def test_performance_scenario_recommender_large_graph()
```

**Использование:**
```bash
pytest tests/performance/test_new_components_performance.py::test_performance_scenario_recommender_large_graph -v
```

---

## Impact Analyzer

### Тест: Анализ влияния изменений

**Цель:** Проверить производительность анализа влияния изменений.

**Параметры:**
- Размер графа: 500 узлов
- Количество итераций: 30
- Максимальная глубина поиска: 3
- Включение тестов: True

**Целевые показатели:**
- p95 < 100ms

**Результаты:**
```python
@pytest.mark.asyncio
async def test_performance_impact_analyzer()
```

**Использование:**
```bash
pytest tests/performance/test_new_components_performance.py::test_performance_impact_analyzer -v
```

---

## LLM Provider Abstraction

### Тест: Выбор провайдера

**Цель:** Проверить производительность выбора LLM провайдера.

**Параметры:**
- Количество типов запросов: 4 (CODE_GENERATION, RUSSIAN_TEXT, REASONING, GENERAL)
- Количество итераций на тип: 100
- Всего итераций: 400

**Целевые показатели:**
- p95 < 1ms

**Результаты:**
```python
@pytest.mark.asyncio
async def test_performance_llm_provider_selection()
```

**Использование:**
```bash
pytest tests/performance/test_new_components_performance.py::test_performance_llm_provider_selection -v
```

**Примечание:** Выбор провайдера - очень быстрая операция, так как она выполняется в памяти без внешних вызовов.

---

## Intelligent Cache

### Тест 1: GET операции (cache hit)

**Цель:** Проверить производительность GET операций при cache hit.

**Параметры:**
- Размер кэша: 100 записей
- Количество итераций: 1000

**Целевые показатели:**
- p95 < 1ms

**Результаты:**
```python
@pytest.mark.asyncio
async def test_performance_intelligent_cache_get()
```

**Использование:**
```bash
pytest tests/performance/test_new_components_performance.py::test_performance_intelligent_cache_get -v
```

---

### Тест 2: SET операции

**Цель:** Проверить производительность SET операций.

**Параметры:**
- Количество итераций: 1000

**Целевые показатели:**
- p95 < 2ms

**Результаты:**
```python
@pytest.mark.asyncio
async def test_performance_intelligent_cache_set()
```

**Использование:**
```bash
pytest tests/performance/test_new_components_performance.py::test_performance_intelligent_cache_set -v
```

---

### Тест 3: Инвалидация по тегам

**Цель:** Проверить производительность инвалидации по тегам.

**Параметры:**
- Размер кэша: 100 записей
- Количество итераций: 50

**Целевые показатели:**
- p95 < 10ms для инвалидации 100 записей

**Результаты:**
```python
@pytest.mark.asyncio
async def test_performance_intelligent_cache_invalidation()
```

**Использование:**
```bash
pytest tests/performance/test_new_components_performance.py::test_performance_intelligent_cache_invalidation -v
```

---

### Тест 4: LRU eviction

**Цель:** Проверить производительность LRU eviction при переполнении кэша.

**Параметры:**
- Максимальный размер кэша: 3
- Количество операций: 100 (переполнение)

**Целевые показатели:**
- p95 < 5ms для eviction

**Результаты:**
```python
@pytest.mark.asyncio
async def test_performance_intelligent_cache_lru_eviction()
```

**Использование:**
```bash
pytest tests/performance/test_new_components_performance.py::test_performance_intelligent_cache_lru_eviction -v
```

---

### Тест 5: Конкурентный доступ

**Цель:** Проверить производительность при конкурентном доступе.

**Параметры:**
- Размер кэша: 100 записей
- Количество конкурентных операций: 200 (100 GET, 100 SET)

**Целевые показатели:**
- p95 < 5ms для конкурентных операций

**Результаты:**
```python
@pytest.mark.asyncio
async def test_performance_intelligent_cache_concurrent_access()
```

**Использование:**
```bash
pytest tests/performance/test_new_components_performance.py::test_performance_intelligent_cache_concurrent_access -v
```

---

## Запуск всех benchmarks

### Быстрый запуск
```bash
pytest tests/performance/test_new_components_performance.py -v
```

### С подробным выводом
```bash
pytest tests/performance/test_new_components_performance.py -v -s
```

### С выводом метрик
```bash
pytest tests/performance/test_new_components_performance.py -v -s --tb=short
```

---

## Интерпретация результатов

### Успешный результат
Если все тесты проходят, это означает, что компоненты соответствуют целевым показателям производительности и готовы к использованию в production.

### Неуспешный результат
Если тест не проходит (p95 превышает целевой показатель), это может указывать на:
1. **Проблемы с производительностью** - необходимо оптимизировать код
2. **Недостаточные ресурсы** - необходимо увеличить ресурсы системы
3. **Неправильные целевые показатели** - возможно, целевые показатели слишком строгие

### Рекомендации
- Запускайте benchmarks регулярно (например, в CI/CD)
- Сравнивайте результаты между версиями
- Отслеживайте деградацию производительности

---

## Prometheus метрики

Все компоненты автоматически отправляют метрики в Prometheus при выполнении операций. Метрики доступны через endpoint `/metrics`.

### Доступные метрики

#### Scenario Recommender
- `scenario_recommender_requests_total` - общее количество запросов
- `scenario_recommender_duration_seconds` - время выполнения
- `scenario_recommender_recommendations_count` - количество рекомендаций

#### Impact Analyzer
- `impact_analyzer_requests_total` - общее количество запросов
- `impact_analyzer_duration_seconds` - время выполнения
- `impact_analyzer_affected_nodes_count` - количество затронутых узлов

#### LLM Provider Abstraction
- `llm_provider_selections_total` - общее количество выборов провайдера
- `llm_provider_selection_duration_seconds` - время выбора
- `llm_provider_cost_estimate` - оценка стоимости

#### Intelligent Cache
- `intelligent_cache_operations_total` - общее количество операций
- `intelligent_cache_duration_seconds` - время выполнения операций
- `intelligent_cache_size` - текущий размер кэша
- `intelligent_cache_max_size` - максимальный размер кэша
- `intelligent_cache_hits_total` - количество cache hits
- `intelligent_cache_misses_total` - количество cache misses
- `intelligent_cache_evictions_total` - количество evictions
- `intelligent_cache_invalidations_total` - количество инвалидаций

### Пример запроса метрик
```bash
curl http://localhost:8000/metrics | grep intelligent_cache
```

---

## Связанные документы

- [CLI Guide](../01-getting-started/CLI_GUIDE.md) - использование CLI для работы с компонентами
- [Scenario Hub Guide](../06-features/SCENARIO_HUB_GUIDE.md) - документация по Scenario Hub
- [Unified Change Graph Guide](../06-features/UNIFIED_CHANGE_GRAPH_GUIDE.md) - документация по Unified Change Graph

---

## История изменений

### 1.0.0 (2025-01-XX)
- Первая версия документации по performance benchmarks
- Добавлены benchmarks для всех новых компонентов
- Добавлена информация о Prometheus метриках

