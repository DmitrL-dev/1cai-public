# Test Generation Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - генерация тестов из кода/требований уникальна

---

## Обзор

**Test Generation Standard** — формальная спецификация для генерации тестов из кода/требований. Определяет использование графа для определения тест-кейсов, приоритизацию тестов и форматы генерации.

---

## 1. Генерация тестов из кода/требований

### 1.1 Из кода

```python
async def generate_tests_from_code(
    code_node_id: str,
    backend: CodeGraphBackend,
    ai_agent: AIAgentInterface,
) -> List[Dict[str, Any]]:
    """
    Генерация тестов из кода через граф.
    
    Returns:
        Список сгенерированных тестов
    """
    # Получить узел кода
    code_node = await backend.get_node(code_node_id)
    
    # Анализ зависимостей для тестов
    dependencies = await analyze_dependencies_for_tests(code_node_id, backend)
    
    # Генерация тестов через AI
    tests = await ai_agent.generate_code(
        f"Создай BDD тесты для {code_node.display_name}",
        context={
            "code": code_node.props.get("code"),
            "dependencies": dependencies,
        },
    )
    
    return parse_generated_tests(tests["code"])
```

### 1.2 Из требований

```python
async def generate_tests_from_requirement(
    requirement_id: str,
    backend: CodeGraphBackend,
    ai_agent: AIAgentInterface,
) -> List[Dict[str, Any]]:
    """
    Генерация тестов из требования через граф.
    
    Returns:
        Список сгенерированных тестов
    """
    # Найти узел требования
    req_node = await backend.find_nodes(
        kind=NodeKind.BA_REQUIREMENT,
        prop_equals={"id": requirement_id},
    )
    
    if not req_node:
        return []
    
    # Найти код, реализующий требование
    code_nodes = await backend.neighbors(
        req_node[0].id,
        kinds=[EdgeKind.IMPLEMENTS],
    )
    
    # Генерация тестов для каждого узла кода
    all_tests = []
    for code_node in code_nodes:
        tests = await generate_tests_from_code(code_node.id, backend, ai_agent)
        all_tests.extend(tests)
    
    return all_tests
```

---

## 2. JSON Schema для тест-генерации

См. `TEST_RECOMMENDATION_SCHEMA.json` и `BSL_AI_AGENT_RESULT_SCHEMA.json`.

---

**Примечание:** Этот стандарт обеспечивает автоматическую генерацию тестов из кода и требований через граф.

