# Unified Change Graph для кода 1С

> **Статус:** ✅ Реализовано  
> **Версия:** 1.0.0  
> **Дата:** Январь 2025

## Обзор

**Unified Change Graph для кода 1С** — это автоматический построитель графа изменений из реального BSL кода. Это ключевая фича платформы: автоматическое построение графа изменений из кода 1С без ручной настройки.

### Что делает

1. **Парсит BSL модули** — использует существующие BSL парсеры (AST или regex-based) для извлечения структуры
2. **Создаёт узлы графа** — модули, функции, процедуры, переменные, таблицы БД
3. **Строит зависимости** — вызовы функций, использование переменных, SQL-запросы к таблицам
4. **Экспортирует в JSON** — совместимый с `CODE_GRAPH_SCHEMA.json`

### Зачем это нужно

- **Impact-анализ**: "что затронет изменение функции X?"
- **Coverage-анализ**: "какие тесты/алерты покрывают этот модуль?"
- **Traceability**: "какие требования/тикеты связаны с этим кодом?"
- **Автоматизация**: не нужно вручную описывать структуру кода

---

## Быстрый старт

### CLI

```bash
# Построить граф из одного файла
python scripts/cli/build_1c_code_graph.py \
    --input module.bsl \
    --module-path "ОбщийМодуль.УправлениеЗаказами" \
    --output graph.json

# Построить граф из директории
python scripts/cli/build_1c_code_graph.py \
    --input /path/to/bsl/files \
    --output graph.json \
    --pattern "*.bsl" \
    --recursive
```

### API

```bash
curl -X POST http://localhost:8000/api/code-graph/1c/build \
    -H "Content-Type: application/json" \
    -d '{
        "module_code": "Функция Тест() Экспорт\n    Возврат Истина;\nКонецФункции",
        "module_path": "ОбщийМодуль.Тест",
        "export_json": true
    }'
```

### Python API

```python
from src.ai.code_graph import InMemoryCodeGraphBackend
from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder

backend = InMemoryCodeGraphBackend()
builder = OneCCodeGraphBuilder(backend, use_ast_parser=True)

module_code = """
Функция СоздатьЗаказ(ПараметрыЗаказа) Экспорт
    Возврат НовыйЗаказ;
КонецФункции
"""

stats = await builder.build_from_module(
    "ОбщийМодуль.УправлениеЗаказами",
    module_code,
    module_metadata={"owner": "my-team"},
)

# Экспортировать граф
graph_export = await builder.export_graph("graph.json")
```

---

## Архитектура

### Компоненты

1. **`OneCCodeGraphBuilder`** (`src/ai/code_graph_1c_builder.py`)
   - Главный класс для построения графа
   - Использует BSL парсеры для извлечения структуры
   - Создаёт узлы и рёбра в Unified Change Graph

2. **BSL Парсеры**
   - `BSLASTParser` (продвинутый, через bsl-language-server)
   - `BSLParser` (упрощённый, regex-based)
   - Автоматический fallback при недоступности AST парсера

3. **Backend**
   - `InMemoryCodeGraphBackend` (для тестов и локальных экспериментов)
   - В будущем: Neo4j, PostgreSQL и др.

### Типы узлов

- `module` — BSL модуль
- `function` — функция BSL
- `procedure` — процедура BSL
- `db_table` — таблица БД (из SQL-запросов)

### Типы рёбер

- `OWNS` — функция/процедура принадлежит модулю
- `DEPENDS_ON` — функция вызывает другую функцию
- `DEPENDS_ON` (queries_table) — модуль использует таблицу БД

---

## Примеры использования

### Пример 1: Простой модуль

```bsl
// ОбщийМодуль.УправлениеЗаказами

Функция СоздатьЗаказ(ПараметрыЗаказа) Экспорт
    Возврат НовыйЗаказ;
КонецФункции

Процедура ОбновитьЗаказ(Заказ, НовыеДанные) Экспорт
    Заказ.Обновить(НовыеДанные);
КонецПроцедуры
```

**Результат:**
- Узел модуля: `module:ОбщийМодуль.УправлениеЗаказами`
- Узел функции: `function:ОбщийМодуль.УправлениеЗаказами:СоздатьЗаказ`
- Узел процедуры: `procedure:ОбщийМодуль.УправлениеЗаказами:ОбновитьЗаказ`
- Рёбра: `OWNS` (функция → модуль, процедура → модуль)

### Пример 2: Модуль с зависимостями

```bsl
Функция ФункцияА() Экспорт
    Результат = ФункцияБ();
    Возврат Результат;
КонецФункции

Функция ФункцияБ()
    Результат = ФункцияВ();
    Возврат Результат;
КонецФункции

Функция ФункцияВ()
    Возврат Истина;
КонецФункции
```

**Результат:**
- Узлы функций: `ФункцияА`, `ФункцияБ`, `ФункцияВ`
- Рёбра: `DEPENDS_ON` (ФункцияА → ФункцияБ, ФункцияБ → ФункцияВ)

### Пример 3: Модуль с SQL-запросами

```bsl
Функция ПолучитьНоменклатуру() Экспорт
    Запрос = Новый Запрос;
    Запрос.Текст = "
        ВЫБРАТЬ
            Номенклатура.Ссылка,
            Номенклатура.Наименование
        ИЗ
            Справочник.Номенклатура КАК Номенклатура";
    Возврат Запрос.Выполнить();
КонецФункции
```

**Результат:**
- Узел таблицы: `db_table:1c:Справочник.Номенклатура`
- Рёбро: `DEPENDS_ON` (модуль → таблица, relationship: "queries_table")

---

## Интеграция с Unified Change Graph

Построенный граф совместим с форматом Unified Change Graph (`CODE_GRAPH_SCHEMA.json`):

```json
{
  "nodes": [
    {
      "id": "module:ОбщийМодуль.УправлениеЗаказами",
      "kind": "module",
      "display_name": "Module: ОбщийМодуль.УправлениеЗаказами",
      "labels": ["bsl", "1c", "module"],
      "props": {
        "path": "ОбщийМодуль.УправлениеЗаказами",
        "loc": 10,
        "complexity": 5
      }
    }
  ],
  "edges": [
    {
      "source": "function:ОбщийМодуль.УправлениеЗаказами:СоздатьЗаказ",
      "target": "module:ОбщийМодуль.УправлениеЗаказами",
      "kind": "OWNS",
      "props": {
        "relationship": "function_in_module"
      }
    }
  ]
}
```

Этот граф можно:
- Валидировать через `scripts/validation/validate_code_graph_against_schema.py`
- Использовать в Scenario Hub через `graph_refs`
- Интегрировать с другими системами через JSON Schema

---

## Ограничения и будущие улучшения

### Текущие ограничения

1. **Упрощённое извлечение вызовов** — regex-based, может пропускать сложные случаи
2. **Внешние вызовы** — создаются узлы-заглушки, но не резолвятся автоматически
3. **InMemoryBackend** — не подходит для больших проектов (нужен Neo4j)

### Планируемые улучшения

1. **Резолв внешних вызовов** — автоматический поиск функций в других модулях
2. **Neo4j интеграция** — персистентное хранение для больших проектов
3. **Инкрементальное обновление** — обновление графа только для изменённых модулей
4. **Визуализация** — автоматическая генерация диаграмм зависимостей
5. **Интеграция с Scenario Hub** — автоматическое связывание сценариев с узлами графа

---

## Тестирование

```bash
# Запустить unit-тесты
pytest tests/unit/test_code_graph_1c_builder.py -v

# Запустить с покрытием
pytest tests/unit/test_code_graph_1c_builder.py --cov=src.ai.code_graph_1c_builder
```

---

## Интеграция с Orchestrator

Unified Change Graph автоматически интегрирован с AI Orchestrator:

1. **Автоматический поиск узлов** — при обработке запроса Orchestrator использует `GraphQueryHelper` для поиска релевантных узлов графа
2. **graph_nodes_touched** — в ответе `process_query` автоматически добавляется поле `_meta.graph_nodes_touched` со списком найденных узлов
3. **Подсказки по сценариям** — на основе найденных узлов автоматически предлагаются релевантные сценарии (BA→Dev→QA, Code Review, DR Rehearsal)

Пример ответа Orchestrator:

```json
{
  "type": "multi_service",
  "response": "...",
  "_meta": {
    "intent": {...},
    "graph_nodes_touched": [
      "module:ОбщийМодуль.УправлениеЗаказами",
      "function:ОбщийМодуль.УправлениеЗаказами:СоздатьЗаказ"
    ],
    "suggested_scenarios": [
      {
        "id": "ba-dev-qa",
        "name": "BA→Dev→QA Flow",
        "relevance": "high",
        "reason": "Запрос касается 1 модулей и 1 функций"
      }
    ]
  }
}
```

## См. также

- [`CODE_GRAPH_REFERENCE.md`](../architecture/CODE_GRAPH_REFERENCE.md) — спецификация Unified Change Graph
- [`CODE_GRAPH_SCHEMA.json`](../architecture/CODE_GRAPH_SCHEMA.json) — JSON Schema для валидации
- [`AI_SCENARIO_HUB_REFERENCE.md`](../architecture/AI_SCENARIO_HUB_REFERENCE.md) — интеграция с Scenario Hub
- [`AI_PERFORMANCE_GUIDE.md`](AI_PERFORMANCE_GUIDE.md) — производительность и observability

