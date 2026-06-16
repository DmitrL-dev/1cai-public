# Impact Analysis Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 90% - автоматический impact-анализ через граф

---

## Обзор

**Impact Analysis Standard** — формальная спецификация для анализа влияния изменений через Unified Change Graph. Определяет алгоритмы impact-анализа, использование графа для анализа, метрики влияния и визуализацию влияния изменений.

---

## 1. Алгоритмы impact-анализа

### 1.1 Базовый алгоритм

```python
async def analyze_impact(
    node_id: str,
    backend: CodeGraphBackend,
    max_depth: int = 3,
) -> Dict[str, Any]:
    """
    Анализ влияния изменения узла.
    
    Args:
        node_id: ID узла, который изменяется
        backend: Backend графа
        max_depth: Максимальная глубина поиска зависимостей
    
    Returns:
        Результат impact-анализа
    """
    affected_nodes = []
    affected_tests = []
    affected_alerts = []
    
    # Поиск всех узлов, которые зависят от изменяемого узла
    visited = set()
    queue = [(node_id, 0)]
    
    while queue:
        current_id, depth = queue.pop(0)
        
        if current_id in visited or depth > max_depth:
            continue
        
        visited.add(current_id)
        
        # Найти узлы, которые зависят от текущего узла (обратные связи)
        dependents = await find_dependent_nodes(current_id, backend)
        
        for dependent in dependents:
            if dependent.id not in visited:
                affected_nodes.append(dependent)
                queue.append((dependent.id, depth + 1))
                
                # Если это тест или алерт, добавить в специальные списки
                if dependent.kind == NodeKind.TEST_CASE:
                    affected_tests.append(dependent)
                elif dependent.kind == NodeKind.ALERT:
                    affected_alerts.append(dependent)
    
    return {
        "affected_nodes": affected_nodes,
        "affected_tests": affected_tests,
        "affected_alerts": affected_alerts,
        "total_affected": len(affected_nodes),
        "depth_reached": max(depth for _, depth in queue if queue) if queue else 0,
    }
```

### 1.2 Поиск зависимых узлов

```python
async def find_dependent_nodes(
    node_id: str,
    backend: CodeGraphBackend,
) -> List[Node]:
    """
    Поиск узлов, которые зависят от указанного узла.
    
    Returns:
        Список зависимых узлов
    """
    dependents = []
    
    # Поиск по всем типам связей зависимости
    dependency_kinds = [
        EdgeKind.DEPENDS_ON,
        EdgeKind.BSL_CALLS,
        EdgeKind.BSL_USES_METADATA,
        EdgeKind.BSL_EXECUTES_QUERY,
    ]
    
    # Для каждого типа связи ищем обратные связи
    for kind in dependency_kinds:
        # Найти все рёбра, где target == node_id и kind == kind
        edges = await backend.find_edges(target=node_id, kind=kind)
        
        for edge in edges:
            source_node = await backend.get_node(edge.source)
            if source_node and source_node not in dependents:
                dependents.append(source_node)
    
    return dependents
```

---

## 2. Метрики влияния

### 2.1 Coverage метрика

```python
def calculate_coverage_impact(
    affected_nodes: List[Node],
    total_nodes: int,
) -> Dict[str, float]:
    """
    Расчет метрики покрытия влиянием.
    
    Returns:
        {
            "coverage_percentage": float,  # Процент затронутых узлов
            "affected_by_kind": Dict,      # Разбивка по типам узлов
        }
    """
    coverage_percentage = (len(affected_nodes) / total_nodes) * 100 if total_nodes > 0 else 0
    
    affected_by_kind = {}
    for node in affected_nodes:
        kind = node.kind.value
        affected_by_kind[kind] = affected_by_kind.get(kind, 0) + 1
    
    return {
        "coverage_percentage": coverage_percentage,
        "affected_by_kind": affected_by_kind,
    }
```

### 2.2 Risk метрика

```python
def calculate_risk_impact(
    affected_nodes: List[Node],
    node_id: str,
    backend: CodeGraphBackend,
) -> Dict[str, Any]:
    """
    Расчет метрики риска влияния.
    
    Returns:
        {
            "overall_risk": float,          # Общий риск (0-1)
            "high_risk_nodes": List,        # Узлы с высоким риском
            "risk_by_category": Dict,       # Риск по категориям
        }
    """
    overall_risk = 0.0
    high_risk_nodes = []
    risk_by_category = {
        "production": 0.0,
        "critical_path": 0.0,
        "external_dependencies": 0.0,
    }
    
    for node in affected_nodes:
        # Расчет риска узла
        node_risk = calculate_node_risk(node, backend)
        
        overall_risk += node_risk
        
        # Определение категории риска
        if node.props.get("environment") == "prod":
            risk_by_category["production"] += node_risk
        
        if node_risk > 0.7:
            high_risk_nodes.append(node)
    
    # Нормализация общего риска
    if affected_nodes:
        overall_risk = overall_risk / len(affected_nodes)
    
    return {
        "overall_risk": overall_risk,
        "high_risk_nodes": high_risk_nodes,
        "risk_by_category": risk_by_category,
    }
```

### 2.3 Complexity метрика

```python
def calculate_complexity_impact(
    affected_nodes: List[Node],
) -> Dict[str, Any]:
    """
    Расчет метрики сложности влияния.
    
    Returns:
        {
            "total_complexity": int,        # Общая сложность затронутых узлов
            "average_complexity": float,    # Средняя сложность
            "complexity_distribution": Dict, # Распределение сложности
        }
    """
    total_complexity = 0
    complexity_values = []
    
    for node in affected_nodes:
        complexity = node.props.get("complexity", 0)
        total_complexity += complexity
        complexity_values.append(complexity)
    
    average_complexity = total_complexity / len(affected_nodes) if affected_nodes else 0
    
    # Распределение сложности
    complexity_distribution = {
        "low": len([c for c in complexity_values if c < 10]),
        "medium": len([c for c in complexity_values if 10 <= c < 30]),
        "high": len([c for c in complexity_values if c >= 30]),
    }
    
    return {
        "total_complexity": total_complexity,
        "average_complexity": average_complexity,
        "complexity_distribution": complexity_distribution,
    }
```

---

## 3. Визуализация влияния изменений

### 3.1 Формат визуализации

```python
@dataclass
class ImpactVisualization:
    """Визуализация влияния изменений."""
    
    root_node: Node                        # Корневой узел (изменяемый)
    affected_nodes: List[Node]             # Затронутые узлы
    edges: List[Edge]                      # Связи между узлами
    metrics: Dict[str, Any]                # Метрики влияния
    visualization_data: Dict[str, Any]     # Данные для визуализации
    
    def to_graph_json(self) -> Dict[str, Any]:
        """Преобразование в формат для визуализации графа."""
        return {
            "nodes": [
                {
                    "id": node.id,
                    "label": node.display_name,
                    "kind": node.kind.value,
                    "risk": calculate_node_risk(node),
                    "props": node.props,
                }
                for node in [self.root_node] + self.affected_nodes
            ],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "kind": edge.kind.value,
                    "props": edge.props,
                }
                for edge in self.edges
            ],
            "metrics": self.metrics,
        }
```

---

## 4. JSON Schema для impact-отчетов

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/impact-analysis-result/v1",
  "title": "ImpactAnalysisResult",
  "type": "object",
  "required": ["node_id", "affected_nodes", "metrics"],
  "properties": {
    "node_id": {"type": "string"},
    "affected_nodes": {
      "type": "array",
      "items": {"type": "string"}
    },
    "affected_tests": {
      "type": "array",
      "items": {"type": "string"}
    },
    "affected_alerts": {
      "type": "array",
      "items": {"type": "string"}
    },
    "total_affected": {"type": "integer"},
    "depth_reached": {"type": "integer"},
    "metrics": {
      "type": "object",
      "properties": {
        "coverage": {
          "type": "object",
          "properties": {
            "coverage_percentage": {"type": "number"},
            "affected_by_kind": {"type": "object"}
          }
        },
        "risk": {
          "type": "object",
          "properties": {
            "overall_risk": {"type": "number"},
            "high_risk_nodes": {"type": "array", "items": {"type": "string"}},
            "risk_by_category": {"type": "object"}
          }
        },
        "complexity": {
          "type": "object",
          "properties": {
            "total_complexity": {"type": "integer"},
            "average_complexity": {"type": "number"},
            "complexity_distribution": {"type": "object"}
          }
        }
      }
    }
  }
}
```

---

## 5. Примеры использования

### 5.1 Анализ влияния изменения функции

```python
from src.ai.impact_analyzer import ImpactAnalyzer
from src.ai.code_graph import InMemoryCodeGraphBackend

backend = InMemoryCodeGraphBackend()
analyzer = ImpactAnalyzer(backend)

result = await analyzer.analyze_impact(
    "function:ОбщийМодуль.Заказы:СоздатьЗаказ",
    max_depth=3,
)

print(f"Затронуто узлов: {result['total_affected']}")
print(f"Затронуто тестов: {len(result['affected_tests'])}")
print(f"Общий риск: {result['metrics']['risk']['overall_risk']:.2f}")
```

---

## 6. Следующие шаги

1. **Реализация анализатора** — создание `ImpactAnalyzer`
2. **Интеграция с графом** — использование Unified Change Graph для анализа
3. **Визуализация** — создание инструментов для визуализации влияния

---

**Примечание:** Этот стандарт обеспечивает автоматический анализ влияния изменений через граф с метриками и визуализацией.

