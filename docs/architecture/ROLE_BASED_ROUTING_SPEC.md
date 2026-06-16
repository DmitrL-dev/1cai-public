# Role-Based Routing Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - алгоритмы роутинга по ролям уникальны

---

## Обзор

**Role-Based Routing Standard** — формальная спецификация для алгоритмов роутинга запросов к нужному AI агенту на основе роли пользователя. Определяет определение роли на основе запроса, приоритизацию агентов и метрики роутинга.

---

## 1. Определение роли на основе запроса

### 1.1 Алгоритм определения роли

```python
class RoleDetector:
    """Определение роли пользователя по запросу."""
    
    ROLE_KEYWORDS = {
        UserRole.DEVELOPER: [
            "сгенерируй код", "напиши функцию", "создай процедуру",
            "оптимизируй", "рефактор", "исправь код",
        ],
        UserRole.BUSINESS_ANALYST: [
            "требования", "ТЗ", "техническое задание", "бизнес-процесс",
            "user story", "use case", "сценарий",
        ],
        UserRole.QA_ENGINEER: [
            "тест", "тестирование", "покрытие", "баг",
            "vanessa", "bdd", "smoke", "regression",
        ],
        # ... и т.д.
    }
    
    def detect_role(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> UserRole:
        """
        Определение роли на основе запроса и контекста.
        
        Returns:
            Определенная роль
        """
        # Подсчет совпадений для каждой роли
        role_scores = {role: 0 for role in UserRole}
        
        query_lower = query.lower()
        for role, keywords in self.ROLE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    role_scores[role] += 1
        
        # Учет контекста
        if context:
            current_file = context.get("current_file", "")
            if current_file.endswith(".bsl"):
                role_scores[UserRole.DEVELOPER] += 2
        
        # Выбор роли с максимальным счетом
        return max(role_scores, key=role_scores.get)
```

---

## 2. Приоритизация агентов

### 2.1 Алгоритм приоритизации

```python
def prioritize_agents(
    role: UserRole,
    query_type: QueryType,
    context: Dict[str, Any],
) -> List[AIAgentInterface]:
    """
    Приоритизация агентов для роли и типа запроса.
    
    Returns:
        Отсортированный список агентов по приоритету
    """
    # Получить всех агентов для роли
    agents = get_agents_by_role(role)
    
    # Приоритизация на основе типа запроса
    for agent in agents:
        priority_score = 0.0
        
        # Проверка возможностей агента
        if query_type in agent.capabilities:
            priority_score += 1.0
        
        # Проверка доступности
        if agent.is_available():
            priority_score += 0.5
        
        # Проверка загрузки
        if agent.get_load() < 0.8:
            priority_score += 0.3
        
        agent.priority_score = priority_score
    
    # Сортировка по приоритету
    agents.sort(key=lambda a: a.priority_score, reverse=True)
    
    return agents
```

---

## 3. JSON Schema для роутинга

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/role-based-routing/v1",
  "title": "RoleRoutingResult",
  "type": "object",
  "required": ["role", "selected_agent"],
  "properties": {
    "role": {
      "type": "string",
      "enum": ["developer", "business_analyst", "qa_engineer", "architect", "devops"]
    },
    "selected_agent": {"type": "string"},
    "priority_score": {"type": "number"},
    "alternative_agents": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent_id": {"type": "string"},
          "priority_score": {"type": "number"}
        }
      }
    }
  }
}
```

---

**Примечание:** Этот стандарт обеспечивает интеллектуальный роутинг запросов к нужному агенту.

