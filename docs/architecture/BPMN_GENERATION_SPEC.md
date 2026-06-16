# BPMN Generation Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - генерация BPMN из требований с графом уникальна

---

## Обзор

**BPMN Generation Standard** — формальная спецификация для генерации BPMN из требований с связью с кодом через Unified Change Graph. Определяет алгоритмы генерации, валидацию процессов и форматы экспорта.

---

## 1. Генерация BPMN из требований

### 1.1 Алгоритм генерации

```python
async def generate_bpmn_from_requirements(
    requirements: List[Dict[str, Any]],
    backend: CodeGraphBackend,
) -> Dict[str, Any]:
    """
    Генерация BPMN модели из требований с использованием графа.
    
    Args:
        requirements: Список требований
        backend: Backend графа
    
    Returns:
        {
            "bpmn_model": Dict,         # BPMN модель (JSON)
            "diagrams": List[Dict],      # Диаграммы (Mermaid/PlantUML)
            "graph_refs": List[str],     # Ссылки на код/тесты
            "validation": Dict,          # Результаты валидации
        }
    """
```

### 1.2 Связь с кодом через граф

```python
async def link_bpmn_to_code(
    bpmn_step: Dict[str, Any],
    backend: CodeGraphBackend,
) -> List[str]:
    """
    Связь шага BPMN процесса с кодом через граф.
    
    Returns:
        Список ID узлов кода, связанных со шагом
    """
    # Поиск узлов кода по описанию шага
    step_description = bpmn_step.get("description", "")
    
    code_nodes = await backend.find_nodes(
        kind=NodeKind.FUNCTION,
        prop_equals={"description": step_description},  # Упрощенный поиск
    )
    
    # Поиск через семантический поиск
    from src.ai.code_graph_query_helper import GraphQueryHelper
    
    helper = GraphQueryHelper(backend)
    semantic_nodes = await helper.find_nodes_by_query(step_description, max_results=5)
    
    # Объединение результатов
    all_nodes = list(code_nodes) + semantic_nodes
    
    return [node.id for node in all_nodes]
```

---

## 2. JSON Schema для BPMN

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/bpmn/v1",
  "title": "BPMNModel",
  "type": "object",
  "required": ["process_id", "name", "steps"],
  "properties": {
    "process_id": {"type": "string"},
    "name": {"type": "string"},
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "step_id": {"type": "string"},
          "name": {"type": "string"},
          "type": {"type": "string", "enum": ["task", "gateway", "event"]},
          "actor": {"type": "string"},
          "graph_refs": {
            "type": "array",
            "items": {"type": "string"}
          }
        }
      }
    }
  }
}
```

---

**Примечание:** Этот стандарт обеспечивает генерацию BPMN с автоматической связью с кодом через граф.

