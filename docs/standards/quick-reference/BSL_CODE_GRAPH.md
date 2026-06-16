# BSL Code Graph — Quick Reference Card

> **Одностраничный справочник** для быстрого доступа к ключевым концепциям BSL Code Graph Standard

---

## 🎯 Основные концепции

### Что это?

**BSL Code Graph** — автоматически построенный граф, представляющий структуру BSL кода 1C, включая модули, функции, процедуры, запросы и связи между ними.

---

## 📊 Типы узлов (24 типа)

### Базовые типы:
- `BSL_MODULE` — модуль BSL
- `BSL_FUNCTION` — функция
- `BSL_PROCEDURE` — процедура
- `BSL_QUERY` — SQL запрос

### 1C объекты:
- `BSL_DOCUMENT` — документ
- `BSL_CATALOG` — справочник
- `BSL_REGISTER_*` — регистры (сведения, накопления, бухгалтерия)

---

## 🔗 Типы связей (12 типов)

### Основные связи:
- `BSL_CALLS` — вызов функции/процедуры
- `BSL_EXECUTES_QUERY` — выполнение запроса
- `BSL_READS_TABLE` — чтение таблицы
- `BSL_WRITES_TABLE` — запись в таблицу

### Метаданные:
- `BSL_USES_METADATA` — использование метаданных
- `BSL_HAS_MODULE` — модуль объекта

---

## 💻 Быстрый пример

```python
from src.ai.code_graph_1c_builder import OneCCodeGraphBuilder

# Построить граф из BSL модуля
builder = OneCCodeGraphBuilder()
graph = builder.build_from_1c_module(
    module_path="path/to/module.bsl",
    module_name="ОбщийМодуль.МойМодуль"
)

# Получить зависимости
dependencies = graph.get_dependencies("function_id")
```

---

## 🔍 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "kind": {"type": "string", "enum": ["BSL_MODULE", "BSL_FUNCTION", ...]},
          "display_name": {"type": "string"}
        }
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "source": {"type": "string"},
          "target": {"type": "string"},
          "kind": {"type": "string", "enum": ["BSL_CALLS", "BSL_EXECUTES_QUERY", ...]}
        }
      }
    }
  }
}
```

---

## 📚 Полная документация

- **Спецификация:** [`../architecture/BSL_CODE_GRAPH_SPEC.md`](../../architecture/BSL_CODE_GRAPH_SPEC.md)
- **JSON Schema:** [`../architecture/BSL_CODE_GRAPH_SCHEMA.json`](../../architecture/BSL_CODE_GRAPH_SCHEMA.json)
- **Примеры:** [`../examples/bsl-code-graph/`](../examples/bsl-code-graph/)

---

**Версия:** 1.0.0 | **Дата:** 2025-11-17

