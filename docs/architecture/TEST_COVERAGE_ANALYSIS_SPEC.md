# Test Coverage Analysis Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - анализ покрытия через граф уникален

---

## Обзор

**Test Coverage Analysis Standard** — формальная спецификация для анализа покрытия тестами через Unified Change Graph. Определяет метрики покрытия (code, branch, integration), визуализацию coverage gaps и алгоритмы анализа.

---

## 1. Метрики покрытия

### 1.1 Code Coverage

```python
async def calculate_code_coverage(
    node_id: str,
    backend: CodeGraphBackend,
) -> Dict[str, float]:
    """
    Расчет покрытия кода тестами.
    
    Returns:
        {
            "function_coverage": float,  # Покрытие функций
            "module_coverage": float,    # Покрытие модулей
            "overall_coverage": float,   # Общее покрытие
        }
    """
    node = await backend.get_node(node_id)
    
    # Найти все тесты, покрывающие узел
    tests = await backend.neighbors(
        node_id,
        kinds=[EdgeKind.TESTED_BY],
    )
    
    if node.kind == NodeKind.FUNCTION:
        # Для функции - просто проверить наличие тестов
        function_coverage = 1.0 if tests else 0.0
    elif node.kind == NodeKind.MODULE:
        # Для модуля - проверить покрытие всех функций
        functions = await backend.neighbors(
            node_id,
            kinds=[EdgeKind.OWNS],
        )
        
        covered_functions = 0
        for func in functions:
            func_tests = await backend.neighbors(
                func.id,
                kinds=[EdgeKind.TESTED_BY],
            )
            if func_tests:
                covered_functions += 1
        
        function_coverage = (
            covered_functions / len(functions) if functions else 0.0
        )
    else:
        function_coverage = 0.0
    
    module_coverage = 1.0 if tests else 0.0
    overall_coverage = (function_coverage + module_coverage) / 2.0
    
    return {
        "function_coverage": function_coverage,
        "module_coverage": module_coverage,
        "overall_coverage": overall_coverage,
    }
```

### 1.2 Branch Coverage

```python
async def calculate_branch_coverage(
    node_id: str,
    backend: CodeGraphBackend,
) -> float:
    """
    Расчет покрытия веток выполнения тестами.
    
    Returns:
        Покрытие веток (0-1)
    """
    node = await backend.get_node(node_id)
    
    # Получить сложность функции (количество веток)
    complexity = node.props.get("complexity", 0)
    
    # Найти все тесты
    tests = await backend.neighbors(
        node_id,
        kinds=[EdgeKind.TESTED_BY],
    )
    
    # Упрощенная оценка: каждая ветка должна быть покрыта хотя бы одним тестом
    # Более точно - анализ покрытия путей выполнения (требует расширенного парсинга)
    if complexity == 0:
        return 1.0 if tests else 0.0
    
    # Минимальное количество тестов для покрытия всех веток
    min_tests_needed = complexity // 2  # Эвристика
    
    branch_coverage = min(len(tests) / min_tests_needed, 1.0) if min_tests_needed > 0 else 0.0
    
    return branch_coverage
```

### 1.3 Integration Coverage

```python
async def calculate_integration_coverage(
    node_id: str,
    backend: CodeGraphBackend,
) -> float:
    """
    Расчет покрытия интеграционными тестами.
    
    Returns:
        Покрытие интеграционными тестами (0-1)
    """
    # Найти все интеграционные тесты (test_suite с типом integration)
    integration_tests = await backend.find_nodes(
        kind=NodeKind.TEST_SUITE,
        prop_equals={"test_type": "integration"},
    )
    
    # Проверить, покрывают ли они узел
    covered = False
    for test_suite in integration_tests:
        test_cases = await backend.neighbors(
            test_suite.id,
            kinds=[EdgeKind.OWNS],
        )
        
        for test_case in test_cases:
            # Проверить, покрывает ли тест узел
            covered_nodes = await backend.neighbors(
                test_case.id,
                kinds=[EdgeKind.TESTED_BY],  # Обратная связь
            )
            
            if any(n.id == node_id for n in covered_nodes):
                covered = True
                break
        
        if covered:
            break
    
    return 1.0 if covered else 0.0
```

---

## 2. Визуализация coverage gaps

### 2.1 Поиск пробелов в покрытии

```python
async def find_coverage_gaps(
    backend: CodeGraphBackend,
) -> List[Dict[str, Any]]:
    """
    Поиск пробелов в покрытии тестами.
    
    Returns:
        Список узлов без покрытия или с низким покрытием
    """
    gaps = []
    
    # Найти все функции
    functions = await backend.find_nodes(kind=NodeKind.FUNCTION)
    
    for func in functions:
        # Проверить покрытие функции
        tests = await backend.neighbors(
            func.id,
            kinds=[EdgeKind.TESTED_BY],
        )
        
        if not tests:
            gaps.append({
                "node_id": func.id,
                "node_name": func.display_name,
                "gap_type": "no_tests",
                "severity": "high",
                "message": "Функция не покрыта тестами",
            })
        else:
            # Проверить качество покрытия
            complexity = func.props.get("complexity", 0)
            if complexity > 10 and len(tests) < complexity / 5:
                gaps.append({
                    "node_id": func.id,
                    "node_name": func.display_name,
                    "gap_type": "insufficient_tests",
                    "severity": "medium",
                    "message": f"Функция высокой сложности ({complexity}) недостаточно покрыта тестами ({len(tests)} тестов)",
                })
    
    return gaps
```

---

## 3. JSON Schema для coverage-анализа

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/test-coverage-analysis/v1",
  "title": "TestCoverageAnalysisResult",
  "type": "object",
  "required": ["node_id", "coverage"],
  "properties": {
    "node_id": {"type": "string"},
    "coverage": {
      "type": "object",
      "properties": {
        "code_coverage": {"type": "number"},
        "branch_coverage": {"type": "number"},
        "integration_coverage": {"type": "number"},
        "overall_coverage": {"type": "number"}
      }
    },
    "gaps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "gap_type": {"type": "string"},
          "severity": {"type": "string"},
          "message": {"type": "string"}
        }
      }
    }
  }
}
```

---

**Примечание:** Этот стандарт обеспечивает анализ покрытия тестами через граф с метриками и визуализацией пробелов.

