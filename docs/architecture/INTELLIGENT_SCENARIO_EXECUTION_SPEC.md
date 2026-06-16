# Intelligent Scenario Execution Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 95% - комплексная автоматизация сценариев уникальна

---

## Обзор

**Intelligent Scenario Execution Standard** — формальная спецификация для интеллектуального выполнения сценариев с AI. Определяет автоматические рекомендации на основе графа, динамическую адаптацию сценариев к контексту, trust score и confidence metrics.

---

## 1. Интеллектуальное выполнение сценариев

### 1.1 Автоматические рекомендации

**На основе Unified Change Graph:**

```python
async def recommend_scenarios(
    query: str,
    graph_nodes: List[str],
    backend: CodeGraphBackend,
) -> List[Dict[str, Any]]:
    """
    Рекомендация сценариев на основе запроса и узлов графа.
    
    Args:
        query: Запрос пользователя
        graph_nodes: Список ID узлов графа
        backend: Backend графа
    
    Returns:
        Список рекомендованных сценариев
    """
    from src.ai.scenario_recommender import ScenarioRecommender
    
    recommender = ScenarioRecommender(backend)
    recommendations = await recommender.recommend_scenarios(
        query,
        graph_nodes=graph_nodes,
        max_recommendations=5,
    )
    
    return recommendations
```

### 1.2 Динамическая адаптация сценариев

```python
async def adapt_scenario_to_context(
    scenario: ScenarioPlan,
    context: Dict[str, Any],
    backend: CodeGraphBackend,
) -> ScenarioPlan:
    """
    Адаптация сценария к контексту на основе графа.
    
    Args:
        scenario: Исходный сценарий
        context: Контекст (узлы графа, метаданные и т.п.)
        backend: Backend графа
    
    Returns:
        Адаптированный сценарий
    """
    adapted_scenario = scenario.copy()
    
    # Анализ узлов графа для адаптации шагов
    graph_nodes = context.get("graph_nodes", [])
    
    for step in adapted_scenario.steps:
        # Адаптация шага на основе узлов графа
        adapted_step = await adapt_step_to_graph_nodes(
            step,
            graph_nodes,
            backend,
        )
        
        # Обновление метаданных шага
        step.metadata["graph_refs"] = adapted_step.graph_refs
        step.metadata["adaptation_applied"] = True
    
    return adapted_scenario
```

### 1.3 Trust Score и Confidence Metrics

```python
@dataclass
class TrustScore:
    """Оценка доверия к выполнению сценария."""
    
    overall_score: float              # Общая оценка (0-1)
    scenario_completeness: float     # Полнота сценария (0-1)
    graph_coverage: float            # Покрытие графом (0-1)
    risk_assessment: float           # Оценка риска (0-1)
    confidence: float                # Уверенность в результате (0-1)
    
    def calculate_trust(self) -> float:
        """Расчет общей оценки доверия."""
        return (
            self.scenario_completeness * 0.3 +
            self.graph_coverage * 0.3 +
            (1 - self.risk_assessment) * 0.2 +
            self.confidence * 0.2
        )
```

---

## 2. Использование Unified Change Graph для рекомендаций

### 2.1 Анализ узлов графа

```python
async def analyze_graph_nodes_for_scenarios(
    graph_nodes: List[str],
    backend: CodeGraphBackend,
) -> Dict[str, Any]:
    """
    Анализ узлов графа для определения типа задачи и рекомендации сценариев.
    
    Returns:
        {
            "task_type": str,           # Тип задачи
            "relevant_scenarios": List,  # Релевантные сценарии
            "graph_analysis": Dict,      # Результаты анализа графа
        }
    """
    # Анализ типов узлов
    node_kinds = {}
    for node_id in graph_nodes:
        node = await backend.get_node(node_id)
        if node:
            kind = node.kind.value
            node_kinds[kind] = node_kinds.get(kind, 0) + 1
    
    # Определение типа задачи на основе узлов
    task_type = infer_task_type_from_nodes(node_kinds)
    
    # Рекомендация сценариев
    relevant_scenarios = get_scenarios_by_task_type(task_type)
    
    return {
        "task_type": task_type,
        "relevant_scenarios": relevant_scenarios,
        "graph_analysis": {
            "node_kinds": node_kinds,
            "total_nodes": len(graph_nodes),
        },
    }
```

### 2.2 Поиск связанных узлов

```python
async def find_related_nodes_for_scenario(
    scenario: ScenarioPlan,
    backend: CodeGraphBackend,
) -> List[str]:
    """
    Поиск связанных узлов графа для сценария.
    
    Returns:
        Список ID связанных узлов
    """
    related_nodes = []
    
    # Использовать graph_refs из шагов сценария
    for step in scenario.steps:
        graph_refs = step.metadata.get("graph_refs", [])
        
        for ref in graph_refs:
            # Добавить узел, на который ссылается шаг
            if ref not in related_nodes:
                related_nodes.append(ref)
            
            # Найти связанные узлы (зависимости)
            neighbors = await backend.neighbors(ref)
            for neighbor in neighbors:
                if neighbor.id not in related_nodes:
                    related_nodes.append(neighbor.id)
    
    return related_nodes
```

---

## 3. ML модели для предсказания релевантных сценариев

### 3.1 Модель рекомендаций

```python
class ScenarioRecommendationModel:
    """ML модель для предсказания релевантных сценариев."""
    
    def predict(
        self,
        query: str,
        graph_features: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Предсказание релевантных сценариев.
        
        Args:
            query: Запрос пользователя
            graph_features: Признаки из графа
        
        Returns:
            Список сценариев с оценками релевантности
        """
        # Извлечение признаков
        features = self.extract_features(query, graph_features)
        
        # Предсказание модели
        predictions = self.model.predict(features)
        
        # Формирование результатов
        scenarios = []
        for scenario_id, score in predictions:
            scenarios.append({
                "scenario_id": scenario_id,
                "relevance_score": score,
                "confidence": self.calculate_confidence(features, score),
            })
        
        return sorted(scenarios, key=lambda x: x["relevance_score"], reverse=True)
```

### 3.2 Признаки для модели

```python
def extract_features(
    query: str,
    graph_features: Dict[str, Any],
) -> List[float]:
    """
    Извлечение признаков для ML модели.
    
    Returns:
        Список числовых признаков
    """
    features = []
    
    # Признаки из запроса
    features.append(len(query))              # Длина запроса
    features.append(query.count(" "))        # Количество слов
    features.extend(extract_keyword_features(query))  # Признаки ключевых слов
    
    # Признаки из графа
    features.append(graph_features.get("total_nodes", 0))      # Количество узлов
    features.append(graph_features.get("functions_count", 0))  # Количество функций
    features.append(graph_features.get("modules_count", 0))    # Количество модулей
    
    # Признаки типов узлов
    node_kinds = graph_features.get("node_kinds", {})
    for kind in ["function", "module", "test_case", "alert"]:
        features.append(node_kinds.get(kind, 0))
    
    return features
```

---

## 4. JSON Schema для рекомендаций

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/scenario-recommendation/v1",
  "title": "ScenarioRecommendation",
  "type": "object",
  "required": ["scenario_id", "relevance_score"],
  "properties": {
    "scenario_id": {"type": "string"},
    "scenario_name": {"type": "string"},
    "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "reason": {"type": "string"},
    "graph_nodes_matched": {
      "type": "array",
      "items": {"type": "string"}
    },
    "trust_score": {
      "type": "object",
      "properties": {
        "overall_score": {"type": "number"},
        "scenario_completeness": {"type": "number"},
        "graph_coverage": {"type": "number"},
        "risk_assessment": {"type": "number"},
        "confidence": {"type": "number"}
      }
    }
  }
}
```

---

## 5. Примеры использования

### 5.1 Рекомендация сценариев

```python
from src.ai.scenario_recommender import ScenarioRecommender
from src.ai.code_graph import InMemoryCodeGraphBackend

backend = InMemoryCodeGraphBackend()
recommender = ScenarioRecommender(backend)

recommendations = await recommender.recommend_scenarios(
    "Нужно реализовать новую фичу",
    graph_nodes=["function:module1:Func1", "module:module2"],
)

for rec in recommendations:
    print(f"{rec['scenario_name']}: {rec['relevance_score']:.2f}")
```

### 5.2 Адаптация сценария

```python
from src.ai.scenario_hub import ScenarioPlan
from src.ai.intelligent_scenario_executor import IntelligentScenarioExecutor

executor = IntelligentScenarioExecutor(backend)

scenario = ScenarioPlan(...)
adapted = await executor.adapt_scenario_to_context(
    scenario,
    context={"graph_nodes": ["module:module1"]},
    backend=backend,
)
```

---

## 6. Следующие шаги

1. **Реализация рекомендательной системы** — создание ML модели для рекомендаций
2. **Интеграция с графом** — автоматические рекомендации на основе графа
3. **Метрики и мониторинг** — отслеживание эффективности рекомендаций

---

**Примечание:** Этот стандарт обеспечивает интеллектуальное выполнение сценариев с автоматическими рекомендациями и адаптацией к контексту.

