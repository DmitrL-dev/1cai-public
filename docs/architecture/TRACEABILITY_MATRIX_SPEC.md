# Traceability Matrix Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - построение traceability через граф уникально

---

## Обзор

**Traceability Matrix Standard** — формальная спецификация для построения traceability матрицы через Unified Change Graph. Определяет алгоритмы построения Requirements → Code → Tests → Incidents, Risk Register и Risk Heatmap.

---

## 1. Построение traceability через граф

### 1.1 Requirements → Code → Tests

```python
async def build_traceability_matrix(
    requirement_ids: List[str],
    backend: CodeGraphBackend,
) -> Dict[str, Any]:
    """
    Построение traceability матрицы через граф.
    
    Returns:
        {
            "matrix": Dict,              # Traceability матрица
            "coverage": Dict,            # Покрытие требований
            "gaps": List[Dict],          # Пробелы в traceability
        }
    """
    matrix = {}
    
    for req_id in requirement_ids:
        # Найти узел требования
        req_node = await backend.find_nodes(
            kind=NodeKind.BA_REQUIREMENT,
            prop_equals={"id": req_id},
        )
        
        if not req_node:
            continue
        
        # Найти код (IMPLEMENTS)
        code_nodes = await backend.neighbors(
            req_node[0].id,
            kinds=[EdgeKind.IMPLEMENTS],
        )
        
        # Найти тесты (TESTED_BY)
        test_nodes = []
        for code_node in code_nodes:
            tests = await backend.neighbors(
                code_node.id,
                kinds=[EdgeKind.TESTED_BY],
            )
            test_nodes.extend(tests)
        
        # Найти инциденты (TRIGGERS_INCIDENT)
        incident_nodes = []
        for code_node in code_nodes:
            incidents = await backend.neighbors(
                code_node.id,
                kinds=[EdgeKind.TRIGGERS_INCIDENT],
            )
            incident_nodes.extend(incidents)
        
        matrix[req_id] = {
            "requirement": req_node[0],
            "code": code_nodes,
            "tests": test_nodes,
            "incidents": incident_nodes,
        }
    
    return {
        "matrix": matrix,
        "coverage": calculate_coverage(matrix),
        "gaps": find_traceability_gaps(matrix),
    }
```

---

## 2. Risk Register и Risk Heatmap

### 2.1 Построение Risk Register

```python
async def build_risk_register(
    matrix: Dict[str, Any],
    backend: CodeGraphBackend,
) -> List[Dict[str, Any]]:
    """
    Построение регистра рисков на основе traceability матрицы.
    
    Returns:
        Список рисков с оценками
    """
    risks = []
    
    for req_id, trace_data in matrix.items():
        req_node = trace_data["requirement"]
        code_nodes = trace_data["code"]
        test_nodes = trace_data["tests"]
        incident_nodes = trace_data["incidents"]
        
        # Риски на основе покрытия
        if not code_nodes:
            risks.append({
                "requirement_id": req_id,
                "risk_type": "implementation_gap",
                "severity": "high",
                "message": "Требование не реализовано в коде",
            })
        
        if not test_nodes:
            risks.append({
                "requirement_id": req_id,
                "risk_type": "test_coverage_gap",
                "severity": "medium",
                "message": "Требование не покрыто тестами",
            })
        
        # Риски на основе инцидентов
        if incident_nodes:
            risks.append({
                "requirement_id": req_id,
                "risk_type": "known_incidents",
                "severity": "high",
                "message": f"Связано с {len(incident_nodes)} инцидентами",
                "incidents": [inc.id for inc in incident_nodes],
            })
    
    return risks
```

---

## 3. JSON Schema для traceability

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/traceability-matrix/v1",
  "title": "TraceabilityMatrix",
  "type": "object",
  "required": ["matrix", "coverage"],
  "properties": {
    "matrix": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "requirement": {"type": "string"},
          "code": {"type": "array", "items": {"type": "string"}},
          "tests": {"type": "array", "items": {"type": "string"}},
          "incidents": {"type": "array", "items": {"type": "string"}}
        }
      }
    },
    "coverage": {
      "type": "object",
      "properties": {
        "requirements_with_code": {"type": "number"},
        "requirements_with_tests": {"type": "number"},
        "overall_coverage": {"type": "number"}
      }
    }
  }
}
```

---

**Примечание:** Этот стандарт обеспечивает автоматическое построение traceability матрицы через граф.

