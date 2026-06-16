# QA Agent Extended Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - QA агент с Unified Change Graph уникален

---

## Обзор

**QA Agent Extended Standard** — формальная спецификация для расширенного QA агента с Unified Change Graph. Определяет функции QA агента, автоматическую генерацию тестов на основе графа, анализ покрытия и рекомендации тестов на основе изменений.

---

## 1. Функции QA агента

### 1.1 Автоматическая генерация тестов

```python
async def generate_tests_for_function(
    function_id: str,
    backend: CodeGraphBackend,
    ai_agent: AIAgentInterface,
) -> Dict[str, Any]:
    """
    Генерация тестов для функции на основе графа.
    
    Returns:
        {
            "unit_tests": List[Dict],
            "integration_tests": List[Dict],
            "vanessa_bdd": List[Dict],
            "coverage_estimate": float,
        }
    """
```

### 1.2 Анализ покрытия через граф

```python
async def analyze_coverage(
    node_id: str,
    backend: CodeGraphBackend,
) -> Dict[str, Any]:
    """
    Анализ покрытия узла тестами через граф.
    
    Returns:
        {
            "coverage_percentage": float,
            "tests": List[Node],
            "gaps": List[Dict],
        }
    """
    # Найти все тесты, покрывающие узел
    tests = await backend.neighbors(
        node_id,
        kinds=[EdgeKind.TESTED_BY],
    )
    
    # Анализ покрытия
    coverage = calculate_coverage_from_graph(node_id, tests, backend)
    
    # Поиск пробелов
    gaps = await find_coverage_gaps(node_id, backend)
    
    return {
        "coverage_percentage": coverage,
        "tests": tests,
        "gaps": gaps,
    }
```

---

## 2. JSON Schema для QA результатов

См. `TEST_RECOMMENDATION_SCHEMA.json` и `BSL_AI_AGENT_RESULT_SCHEMA.json`.

---

**Примечание:** Этот стандарт обеспечивает автоматическую генерацию тестов и анализ покрытия через граф.

