# Automated Test Recommendation Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - автоматические рекомендации тестов через граф

---

## Обзор

**Automated Test Recommendation Standard** — формальная спецификация для автоматических рекомендаций тестов на основе Unified Change Graph. Определяет алгоритмы рекомендаций тестов, использование графа для определения coverage gaps, автоматическую генерацию тест-кейсов и приоритизацию тестов на основе риска.

---

## 1. Алгоритмы рекомендаций тестов

### 1.1 Определение coverage gaps

```python
async def find_coverage_gaps(
    node_id: str,
    backend: CodeGraphBackend,
) -> List[Dict[str, Any]]:
    """
    Поиск пробелов в покрытии тестами.
    
    Args:
        node_id: ID узла (функция, модуль, объект)
        backend: Backend графа
    
    Returns:
        Список пробелов в покрытии
    """
    gaps = []
    
    # Найти все тесты, которые покрывают узел
    tests = await backend.find_nodes(
        kind=NodeKind.TEST_CASE,
    )
    
    covered_tests = []
    for test in tests:
        # Проверить, покрывает ли тест узел
        test_edges = await backend.neighbors(
            test.id,
            kinds=[EdgeKind.TESTED_BY, EdgeKind.OWNS],
        )
        
        if any(node.id == node_id for node in test_edges):
            covered_tests.append(test)
    
    # Определить пробелы
    node = await backend.get_node(node_id)
    if not node:
        return gaps
    
    # Если узел - функция, проверяем покрытие всех путей выполнения
    if node.kind == NodeKind.FUNCTION:
        complexity = node.props.get("complexity", 0)
        # Если сложность высокая, но тестов мало - это пробел
        if complexity > 10 and len(covered_tests) < complexity / 5:
            gaps.append({
                "node_id": node_id,
                "gap_type": "complexity_coverage",
                "severity": "high",
                "message": f"Функция высокой сложности ({complexity}) недостаточно покрыта тестами",
                "recommended_tests": complexity // 5 - len(covered_tests),
            })
    
    # Проверка покрытия критических путей
    critical_paths = await find_critical_paths(node_id, backend)
    for path in critical_paths:
        if not is_path_covered(path, covered_tests):
            gaps.append({
                "node_id": node_id,
                "gap_type": "critical_path",
                "severity": "critical",
                "message": f"Критический путь выполнения не покрыт тестами",
                "path": path,
            })
    
    return gaps
```

### 1.2 Автоматическая генерация тест-кейсов

```python
async def generate_test_cases(
    node_id: str,
    backend: CodeGraphBackend,
    ai_agent: AIAgentInterface,
) -> List[Dict[str, Any]]:
    """
    Автоматическая генерация тест-кейсов на основе узла.
    
    Args:
        node_id: ID узла (функция, модуль)
        backend: Backend графа
        ai_agent: AI агент для генерации тестов
    
    Returns:
        Список сгенерированных тест-кейсов
    """
    node = await backend.get_node(node_id)
    if not node:
        return []
    
    # Извлечение контекста для генерации
    context = await extract_test_generation_context(node, backend)
    
    # Генерация тест-кейсов через AI
    test_cases = []
    
    if node.kind == NodeKind.FUNCTION:
        # Генерация тестов для функции
        prompt = f"Создай BDD тесты для функции {node.props.get('function_name')}"
        
        generated_tests = await ai_agent.generate_code(
            prompt,
            context=context,
        )
        
        # Парсинг сгенерированных тестов
        parsed_tests = parse_generated_tests(generated_tests["code"])
        
        for test in parsed_tests:
            test_cases.append({
                "name": test["name"],
                "description": test["description"],
                "scenario": test["scenario"],
                "code": test["code"],
                "priority": determine_test_priority(node, test),
            })
    
    return test_cases
```

### 1.3 Приоритизация тестов на основе риска

```python
def prioritize_tests(
    test_cases: List[Dict[str, Any]],
    node: Node,
    backend: CodeGraphBackend,
) -> List[Dict[str, Any]]:
    """
    Приоритизация тестов на основе риска узла.
    
    Returns:
        Отсортированный список тестов по приоритету
    """
    for test in test_cases:
        # Расчет приоритета теста
        priority_score = calculate_test_priority(test, node, backend)
        test["priority_score"] = priority_score
    
    # Сортировка по приоритету
    test_cases.sort(key=lambda t: t["priority_score"], reverse=True)
    
    return test_cases

def calculate_test_priority(
    test: Dict[str, Any],
    node: Node,
    backend: CodeGraphBackend,
) -> float:
    """
    Расчет приоритета теста.
    
    Returns:
        Приоритет (0-1, где 1 - самый высокий)
    """
    priority = 0.0
    
    # Риск узла
    node_risk = calculate_node_risk(node, backend)
    priority += node_risk * 0.4
    
    # Критичность пути
    if test.get("critical_path", False):
        priority += 0.3
    
    # Покрытие edge cases
    if test.get("edge_case", False):
        priority += 0.2
    
    # Интеграционные тесты
    if test.get("integration", False):
        priority += 0.1
    
    return min(priority, 1.0)
```

---

## 2. Использование графа для определения тест-кейсов

### 2.1 Анализ зависимостей для тестов

```python
async def analyze_dependencies_for_tests(
    node_id: str,
    backend: CodeGraphBackend,
) -> Dict[str, Any]:
    """
    Анализ зависимостей узла для определения тест-кейсов.
    
    Returns:
        {
            "dependencies": List,            # Зависимости узла
            "test_scenarios": List,          # Сценарии для тестирования
            "edge_cases": List,              # Граничные случаи
        }
    """
    node = await backend.get_node(node_id)
    if not node:
        return {}
    
    # Найти все зависимости узла
    dependencies = await backend.neighbors(
        node_id,
        kinds=[EdgeKind.DEPENDS_ON, EdgeKind.BSL_CALLS],
    )
    
    # Определить сценарии для тестирования
    test_scenarios = []
    
    # Базовые сценарии
    test_scenarios.append({
        "name": "normal_execution",
        "description": "Нормальное выполнение функции",
        "priority": "high",
    })
    
    # Сценарии для каждой зависимости
    for dep in dependencies:
        test_scenarios.append({
            "name": f"dependency_{dep.id}",
            "description": f"Тест с зависимостью {dep.display_name}",
            "priority": "medium",
        })
    
    # Граничные случаи
    edge_cases = identify_edge_cases(node, dependencies)
    
    return {
        "dependencies": [d.id for d in dependencies],
        "test_scenarios": test_scenarios,
        "edge_cases": edge_cases,
    }
```

---

## 3. JSON Schema для тест-рекомендаций

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/test-recommendation/v1",
  "title": "TestRecommendation",
  "type": "object",
  "required": ["node_id", "recommendations"],
  "properties": {
    "node_id": {"type": "string"},
    "coverage_gaps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "gap_type": {"type": "string"},
          "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
          "message": {"type": "string"},
          "recommended_tests": {"type": "integer"}
        }
      }
    },
    "generated_test_cases": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "description": {"type": "string"},
          "scenario": {"type": "string"},
          "code": {"type": "string"},
          "priority": {"type": "string", "enum": ["high", "medium", "low"]},
          "priority_score": {"type": "number"}
        }
      }
    }
  }
}
```

---

## 4. Примеры использования

### 4.1 Рекомендация тестов для функции

```python
from src.ai.test_recommender import TestRecommender
from src.ai.code_graph import InMemoryCodeGraphBackend

backend = InMemoryCodeGraphBackend()
recommender = TestRecommender(backend)

recommendations = await recommender.recommend_tests(
    "function:ОбщийМодуль.Заказы:СоздатьЗаказ",
)

print(f"Пробелы в покрытии: {len(recommendations['coverage_gaps'])}")
print(f"Сгенерировано тестов: {len(recommendations['generated_test_cases'])}")
```

---

## 5. Следующие шаги

1. **Реализация рекомендательной системы** — создание `TestRecommender`
2. **Интеграция с графом** — использование графа для определения пробелов
3. **Интеграция с AI** — генерация тестов через AI агентов

---

**Примечание:** Этот стандарт обеспечивает автоматические рекомендации тестов на основе графа с приоритизацией и генерацией тест-кейсов.

