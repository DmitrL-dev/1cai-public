# BA Agent Extended Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - BA агент с Unified Change Graph уникален

---

## Обзор

**BA Agent Extended Standard** — формальная спецификация для расширенного BA агента с Unified Change Graph. Определяет все функции BA агента (BA-02...BA-07), интеграцию с графом, генерацию BPMN, KPI, Traceability и синхронизацию с Jira/Confluence.

---

## 1. Функции BA агента

### 1.1 BA-02: Requirements Extraction

**Извлечение требований из документов:**

```python
async def extract_requirements(
    document_text: str,
    document_type: str = "tz",
    *,
    use_graph: bool = True,
) -> Dict[str, Any]:
    """
    Извлечение требований из документа с использованием графа.
    
    Returns:
        {
            "functional_requirements": List[Dict],
            "non_functional_requirements": List[Dict],
            "constraints": List[Dict],
            "stakeholders": List[str],
            "user_stories": List[Dict],
            "acceptance_criteria": List[str],
            "graph_refs": List[str],  # Ссылки на узлы графа
        }
    """
```

### 1.2 BA-03: Process Modelling

**Моделирование процессов:**

```python
async def model_process(
    process_description: str,
    notation: str = "BPMN",
    *,
    use_graph: bool = True,
) -> Dict[str, Any]:
    """
    Моделирование процесса с использованием графа.
    
    Returns:
        {
            "process_model": Dict,      # BPMN/CJM модель
            "diagrams": List[Dict],     # Диаграммы (Mermaid/PlantUML)
            "graph_refs": List[str],    # Ссылки на код/тесты в графе
            "validation": Dict,         # Результаты валидации
        }
    """
```

### 1.3 BA-04: Analytics & KPI

**Аналитика и KPI:**

```python
async def generate_kpi_analytics(
    feature_name: str,
    *,
    use_graph: bool = True,
) -> Dict[str, Any]:
    """
    Генерация KPI и аналитики через граф.
    
    Returns:
        {
            "kpis": List[Dict],         # Список KPI
            "metrics": Dict,            # Метрики из графа
            "sql_queries": List[str],   # SQL запросы для KPI
            "dashboards": List[Dict],   # Конфигурации дашбордов
        }
    """
```

### 1.4 BA-05: Traceability & Compliance

**Traceability и соответствие:**

```python
async def generate_traceability_matrix(
    requirement_ids: List[str],
    *,
    use_graph: bool = True,
) -> Dict[str, Any]:
    """
    Построение traceability матрицы через граф.
    
    Returns:
        {
            "traceability_matrix": Dict,  # Requirements → Code → Tests
            "risk_register": List[Dict],  # Регистр рисков
            "risk_heatmap": Dict,         # Heatmap рисков
            "compliance_status": Dict,    # Статус соответствия
        }
    """
```

### 1.5 BA-06: Integrations & Collaboration

**Интеграции и коллаборация:**

```python
async def sync_requirements_to_jira(
    requirement_ids: List[str],
    project_key: str,
    *,
    use_graph: bool = True,
) -> Dict[str, Any]:
    """
    Синхронизация требований в Jira через граф.
    
    Returns:
        {
            "jira_issues": List[Dict],   # Созданные задачи в Jira
            "graph_refs_added": int,     # Количество добавленных ссылок на граф
            "status": str,               # Статус синхронизации
        }
    """
```

### 1.6 BA-07: Enablement

**Enablement материалы:**

```python
async def build_enablement_plan(
    feature_name: str,
    audience: str = "BA+Dev+QA",
    *,
    use_graph: bool = True,
) -> Dict[str, Any]:
    """
    План enablement-материалов через граф.
    
    Returns:
        {
            "modules": List[Dict],       # Модули из графа
            "examples": List[Dict],      # Примеры кода из графа
            "documentation": Dict,       # Структура документации
            "presentations": List[Dict], # Презентации
        }
    """
```

---

## 2. Интеграция с Unified Change Graph

### 2.1 Связь требований с кодом

```python
async def link_requirements_to_code(
    requirement_id: str,
    backend: CodeGraphBackend,
) -> Dict[str, Any]:
    """
    Связь требования с кодом через граф.
    
    Returns:
        {
            "requirement_node": Node,    # Узел требования
            "code_nodes": List[Node],    # Узлы кода (IMPLEMENTS)
            "test_nodes": List[Node],    # Узлы тестов (TESTED_BY)
        }
    """
    # Найти узел требования
    req_node = await backend.find_nodes(
        kind=NodeKind.BA_REQUIREMENT,
        prop_equals={"id": requirement_id},
    )
    
    if not req_node:
        return {}
    
    # Найти код, реализующий требование
    code_nodes = await backend.neighbors(
        req_node[0].id,
        kinds=[EdgeKind.IMPLEMENTS],
    )
    
    # Найти тесты, покрывающие требование
    test_nodes = await backend.neighbors(
        req_node[0].id,
        kinds=[EdgeKind.TESTED_BY],
    )
    
    return {
        "requirement_node": req_node[0],
        "code_nodes": code_nodes,
        "test_nodes": test_nodes,
    }
```

---

## 3. JSON Schema для BA результатов

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/ba-agent-result/v1",
  "title": "BAAgentResult",
  "type": "object",
  "required": ["ba_function", "result"],
  "properties": {
    "ba_function": {
      "type": "string",
      "enum": ["BA-02", "BA-03", "BA-04", "BA-05", "BA-06", "BA-07"]
    },
    "result": {"type": "object"},
    "graph_refs": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

---

## 4. Примеры использования

### 4.1 Извлечение требований

```python
from src.ai.agents.business_analyst_agent_extended import BusinessAnalystAgentExtended

agent = BusinessAnalystAgentExtended()

result = await agent.extract_requirements(
    document_text,
    use_graph=True,
)
```

---

**Примечание:** Этот стандарт обеспечивает полный функционал BA агента с интеграцией графа.

