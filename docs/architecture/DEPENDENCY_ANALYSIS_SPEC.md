# Dependency Analysis Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 90% - анализ зависимостей через граф уникален

---

## Обзор

**Dependency Analysis Standard** — формальная спецификация для анализа зависимостей через Unified Change Graph. Определяет алгоритмы поиска зависимостей (direct, transitive, circular), метрики сложности зависимостей и визуализацию.

---

## 1. Алгоритмы поиска зависимостей

### 1.1 Direct Dependencies

```python
async def find_direct_dependencies(
    node_id: str,
    backend: CodeGraphBackend,
) -> List[Node]:
    """
    Поиск прямых зависимостей узла.
    
    Returns:
        Список узлов, от которых зависит данный узел
    """
    return await backend.neighbors(
        node_id,
        kinds=[
            EdgeKind.DEPENDS_ON,
            EdgeKind.BSL_CALLS,
            EdgeKind.BSL_USES_METADATA,
        ],
    )
```

### 1.2 Transitive Dependencies

```python
async def find_transitive_dependencies(
    node_id: str,
    backend: CodeGraphBackend,
    max_depth: int = 10,
) -> List[Node]:
    """
    Поиск транзитивных зависимостей узла.
    
    Returns:
        Список всех зависимых узлов (включая транзитивные)
    """
    visited = set()
    queue = [(node_id, 0)]
    dependencies = []
    
    while queue:
        current_id, depth = queue.pop(0)
        
        if current_id in visited or depth > max_depth:
            continue
        
        visited.add(current_id)
        
        # Найти прямые зависимости
        direct_deps = await find_direct_dependencies(current_id, backend)
        
        for dep in direct_deps:
            if dep.id not in visited:
                dependencies.append(dep)
                queue.append((dep.id, depth + 1))
    
    return dependencies
```

### 1.3 Circular Dependencies

```python
async def find_circular_dependencies(
    node_id: str,
    backend: CodeGraphBackend,
) -> List[List[str]]:
    """
    Поиск циклических зависимостей, включающих узел.
    
    Returns:
        Список циклов (каждый цикл - список ID узлов)
    """
    cycles = []
    visited = set()
    path = []
    
    async def dfs(current_id: str):
        """DFS для поиска циклов."""
        if current_id in visited:
            if current_id in path:
                # Найден цикл
                cycle_start = path.index(current_id)
                cycle = path[cycle_start:] + [current_id]
                cycles.append(cycle)
            return
        
        visited.add(current_id)
        path.append(current_id)
        
        # Рекурсивный поиск в зависимостях
        dependencies = await find_direct_dependencies(current_id, backend)
        for dep in dependencies:
            await dfs(dep.id)
        
        path.pop()
    
    await dfs(node_id)
    
    return cycles
```

---

## 2. Метрики сложности зависимостей

### 2.1 Coupling Metric

```python
def calculate_coupling(
    node: Node,
    dependencies: List[Node],
) -> float:
    """
    Расчет метрики coupling (связанности).
    
    Returns:
        Значение coupling (0-1, где 1 - максимальная связанность)
    """
    # Количество прямых зависимостей
    direct_count = len(dependencies)
    
    # Типы зависимостей (разные типы весят по-разному)
    dependency_types = {}
    for dep in dependencies:
        # Определить тип зависимости (упрощенно)
        dep_type = dep.kind.value
        dependency_types[dep_type] = dependency_types.get(dep_type, 0) + 1
    
    # Расчет coupling
    coupling = min(direct_count / 50.0, 1.0)  # Нормализация
    
    return coupling
```

### 2.2 Complexity Metric

```python
def calculate_dependency_complexity(
    node_id: str,
    backend: CodeGraphBackend,
) -> Dict[str, Any]:
    """
    Расчет сложности зависимостей узла.
    
    Returns:
        {
            "direct_count": int,
            "transitive_count": int,
            "circular_count": int,
            "coupling": float,
            "complexity_score": float,
        }
    """
    direct_deps = await find_direct_dependencies(node_id, backend)
    transitive_deps = await find_transitive_dependencies(node_id, backend)
    circular_deps = await find_circular_dependencies(node_id, backend)
    
    coupling = calculate_coupling(node, direct_deps)
    
    # Расчет общей сложности
    complexity_score = (
        len(direct_deps) * 0.3 +
        len(transitive_deps) * 0.2 +
        len(circular_deps) * 10.0 +  # Циклические зависимости сильно увеличивают сложность
        coupling * 0.5
    )
    
    return {
        "direct_count": len(direct_deps),
        "transitive_count": len(transitive_deps),
        "circular_count": len(circular_deps),
        "coupling": coupling,
        "complexity_score": complexity_score,
    }
```

---

## 3. JSON Schema для dependency-анализа

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/dependency-analysis/v1",
  "title": "DependencyAnalysisResult",
  "type": "object",
  "required": ["node_id", "dependencies"],
  "properties": {
    "node_id": {"type": "string"},
    "direct_dependencies": {
      "type": "array",
      "items": {"type": "string"}
    },
    "transitive_dependencies": {
      "type": "array",
      "items": {"type": "string"}
    },
    "circular_dependencies": {
      "type": "array",
      "items": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "metrics": {
      "type": "object",
      "properties": {
        "direct_count": {"type": "integer"},
        "transitive_count": {"type": "integer"},
        "circular_count": {"type": "integer"},
        "coupling": {"type": "number"},
        "complexity_score": {"type": "number"}
      }
    }
  }
}
```

---

**Примечание:** Этот стандарт обеспечивает анализ зависимостей через граф с метриками сложности.

