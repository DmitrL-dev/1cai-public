# BSL Code Quality Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - стандарты качества для BSL уникальны

---

## Обзор

**BSL Code Quality Standard** — формальная спецификация для стандартов качества BSL кода для AI генерации. Определяет метрики качества (complexity, maintainability, performance), best practices для BSL и автоматическую проверку качества.

---

## 1. Метрики качества

### 1.1 Complexity (Сложность)

```python
def calculate_complexity(code: str) -> int:
    """
    Расчет цикломатической сложности BSL кода.
    
    Returns:
        Значение сложности
    """
    complexity = 1  # Базовая сложность
    
    # Увеличиваем сложность за каждое условие
    complexity += len(re.findall(r'\b(?:Если|ЕслиТогда|ЕслиИначе)\b', code, re.IGNORECASE))
    
    # Увеличиваем за циклы
    complexity += len(re.findall(r'\b(?:Для|Пока|ДляКаждого)\b', code, re.IGNORECASE))
    
    # Увеличиваем за обработку исключений
    complexity += len(re.findall(r'\b(?:Попытка|Исключение)\b', code, re.IGNORECASE))
    
    return complexity
```

### 1.2 Maintainability (Поддерживаемость)

```python
def calculate_maintainability(code: str) -> float:
    """
    Расчет метрики поддерживаемости (0-1).
    
    Returns:
        Оценка поддерживаемости
    """
    maintainability_score = 1.0
    
    # Уменьшаем за отсутствие документации
    if not has_documentation(code):
        maintainability_score -= 0.2
    
    # Уменьшаем за сложность
    complexity = calculate_complexity(code)
    if complexity > 20:
        maintainability_score -= 0.3
    elif complexity > 10:
        maintainability_score -= 0.1
    
    # Уменьшаем за длинные функции
    loc = len(code.split('\n'))
    if loc > 200:
        maintainability_score -= 0.2
    elif loc > 100:
        maintainability_score -= 0.1
    
    return max(maintainability_score, 0.0)
```

### 1.3 Performance (Производительность)

```python
def calculate_performance_score(code: str) -> float:
    """
    Расчет метрики производительности (0-1).
    
    Returns:
        Оценка производительности
    """
    performance_score = 1.0
    
    # Уменьшаем за запросы в циклах
    if has_queries_in_loops(code):
        performance_score -= 0.5
    
    # Уменьшаем за N+1 проблемы
    if has_n_plus_one_pattern(code):
        performance_score -= 0.3
    
    # Уменьшаем за отсутствие кэширования метаданных
    if has_repeated_metadata_access(code):
        performance_score -= 0.2
    
    return max(performance_score, 0.0)
```

---

## 2. Best Practices для BSL

### 2.1 Паттерны (Patterns)

```python
BSL_PATTERNS = {
    "use_query_parameters": {
        "description": "Использование параметров запросов вместо конкатенации строк",
        "pattern": r'Запрос\.Текст\s*=\s*["\'][^"\']*["\']\s*\+',
        "anti_pattern": True,
    },
    "cache_metadata": {
        "description": "Кэширование метаданных объектов",
        "pattern": r'Метаданные\.\w+\.\w+\s*=\s*\w+',  # Упрощенный паттерн
        "good_pattern": True,
    },
    "error_handling": {
        "description": "Обработка исключений для внешних вызовов",
        "pattern": r'Попытка\s+.*?Исключение\s+.*?КонецПопытки',
        "required": True,
    },
}
```

---

## 3. JSON Schema для quality reports

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/bsl-code-quality-report/v1",
  "title": "BSLCodeQualityReport",
  "type": "object",
  "required": ["metrics", "quality_score"],
  "properties": {
    "metrics": {
      "type": "object",
      "properties": {
        "complexity": {"type": "integer"},
        "maintainability": {"type": "number"},
        "performance": {"type": "number"}
      }
    },
    "quality_score": {"type": "number", "minimum": 0, "maximum": 1},
    "best_practices": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "pattern": {"type": "string"},
          "compliant": {"type": "boolean"},
          "message": {"type": "string"}
        }
      }
    }
  }
}
```

---

**Примечание:** Этот стандарт обеспечивает единообразные стандарты качества BSL кода для AI генерации.

