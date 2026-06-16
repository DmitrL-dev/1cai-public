# Multi-Role AI Agent Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - 8 AI агентов для разных ролей уникальны

---

## Обзор

**Multi-Role AI Agent Standard** — формальная спецификация для работы мультиролевой AI системы. Определяет интерфейсы для разных ролей (Developer, Architect, BA, QA, DevOps), стандарты коммуникации между агентами, роутинг запросов и коллаборацию между агентами.

---

## 1. Роли AI агентов

### 1.1 Типы ролей

```python
class UserRole(str, Enum):
    """Роли пользователей в системе."""
    
    DEVELOPER = "developer"                    # Разработчик
    BUSINESS_ANALYST = "business_analyst"     # Бизнес-аналитик
    QA_ENGINEER = "qa_engineer"               # QA инженер
    ARCHITECT = "architect"                   # Архитектор
    DEVOPS = "devops"                         # DevOps инженер
    TECHNICAL_WRITER = "technical_writer"     # Технический писатель
    PROJECT_MANAGER = "project_manager"       # Проект-менеджер
    SECURITY_OFFICER = "security_officer"     # Security офицер
```

### 1.2 Интерфейсы агентов

```python
class AIAgentInterface:
    """Базовый интерфейс для всех AI агентов."""
    
    role: UserRole                             # Роль агента
    capabilities: Set[str]                     # Возможности агента
    
    async def process(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Обработка запроса агентом.
        
        Returns:
            Результат обработки в стандартном формате
        """
        raise NotImplementedError
    
    async def collaborate(
        self,
        other_agent: AIAgentInterface,
        task: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Коллаборация с другим агентом.
        
        Returns:
            Результат коллаборации
        """
        raise NotImplementedError
```

---

## 2. Роутинг запросов к нужному агенту

### 2.1 Определение роли на основе запроса

```python
class RoleBasedRouter:
    """Роутер запросов по ролям."""
    
    def __init__(self):
        self.role_detector = RoleDetector()
        self.agent_registry = AgentRegistry()
    
    async def route(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AIAgentInterface:
        """
        Маршрутизация запроса к нужному агенту.
        
        Returns:
            Агент для обработки запроса
        """
        # Определение роли
        role = self.role_detector.detect_role(query, context)
        
        # Выбор агента
        agent = self.agent_registry.get_agent(role)
        
        # Приоритизация агентов
        if not agent or not agent.is_available():
            agent = self.agent_registry.get_fallback_agent(role)
        
        return agent
```

### 2.2 Приоритизация агентов

```python
class AgentRegistry:
    """Реестр AI агентов."""
    
    def __init__(self):
        self.agents: Dict[UserRole, List[AIAgentInterface]] = {}
        self.priorities: Dict[UserRole, List[str]] = {}
    
    def get_agent(
        self,
        role: UserRole,
        priority: int = 0,
    ) -> Optional[AIAgentInterface]:
        """
        Получение агента по роли и приоритету.
        
        Args:
            role: Роль агента
            priority: Приоритет (0 - самый высокий)
        
        Returns:
            Агент или None
        """
        agents = self.agents.get(role, [])
        
        if not agents:
            return None
        
        # Сортировка по приоритету
        sorted_agents = sorted(agents, key=lambda a: a.priority)
        
        if priority < len(sorted_agents):
            return sorted_agents[priority]
        
        return None
```

---

## 3. Коллаборация между агентами

### 3.1 Workflow для совместной работы

```python
class AgentCollaborationWorkflow:
    """Workflow для коллаборации агентов."""
    
    async def execute_collaborative_task(
        self,
        task: Dict[str, Any],
        agents: List[AIAgentInterface],
    ) -> Dict[str, Any]:
        """
        Выполнение задачи несколькими агентами.
        
        Args:
            task: Задача для выполнения
            agents: Список агентов для участия
        
        Returns:
            Результат выполнения задачи
        """
        results = []
        
        # Последовательное выполнение задачи агентами
        for agent in agents:
            result = await agent.process(
                task.get("query"),
                context=task.get("context", {}),
            )
            results.append(result)
            
            # Обновление контекста для следующего агента
            task["context"]["previous_results"] = results
        
        # Объединение результатов
        return self.merge_results(results)
```

### 3.2 Обмен контекстом между агентами

```python
class AgentContext:
    """Контекст для обмена между агентами."""
    
    def __init__(self):
        self.shared_data: Dict[str, Any] = {}
        self.history: List[Dict[str, Any]] = []
    
    def share(
        self,
        key: str,
        value: Any,
        agent: str,
    ) -> None:
        """Обмен данными между агентами."""
        self.shared_data[key] = {
            "value": value,
            "shared_by": agent,
            "timestamp": datetime.now(),
        }
        self.history.append({
            "action": "share",
            "key": key,
            "agent": agent,
            "timestamp": datetime.now(),
        })
    
    def get(self, key: str) -> Optional[Any]:
        """Получение общих данных."""
        data = self.shared_data.get(key)
        if data:
            return data["value"]
        return None
```

---

## 4. Стандарты коммуникации между агентами

### 4.1 Формат сообщений

```python
@dataclass
class AgentMessage:
    """Стандартное сообщение между агентами."""
    
    from_agent: str                            # Отправитель
    to_agent: str                              # Получатель
    message_type: str                          # Тип сообщения
    content: Dict[str, Any]                    # Содержимое сообщения
    context: Dict[str, Any]                    # Контекст сообщения
    timestamp: datetime                        # Время отправки
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }
```

### 4.2 Типы сообщений

```python
class MessageType(str, Enum):
    """Типы сообщений между агентами."""
    
    REQUEST = "request"                        # Запрос
    RESPONSE = "response"                      # Ответ
    NOTIFICATION = "notification"              # Уведомление
    COLLABORATION = "collaboration"            # Коллаборация
    ERROR = "error"                            # Ошибка
```

---

## 5. JSON Schema для мультиролевой системы

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/multi-role-agent/v1",
  "title": "MultiRoleAgentResult",
  "type": "object",
  "required": ["role", "result"],
  "properties": {
    "role": {
      "type": "string",
      "enum": ["developer", "business_analyst", "qa_engineer", "architect", "devops", "technical_writer"]
    },
    "result": {"type": "object"},
    "collaboration": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent": {"type": "string"},
          "contribution": {"type": "string"},
          "timestamp": {"type": "string"}
        }
      }
    }
  }
}
```

---

## 6. Примеры использования

### 6.1 Роутинг запроса

```python
from src.ai.role_based_router import RoleBasedRouter

router = RoleBasedRouter()
agent = await router.route("Создай функцию для расчета НДС")

result = await agent.process("Создай функцию для расчета НДС")
```

### 6.2 Коллаборация агентов

```python
from src.ai.agent_collaboration import AgentCollaborationWorkflow

workflow = AgentCollaborationWorkflow()

result = await workflow.execute_collaborative_task(
    {
        "query": "Реализовать новую фичу",
        "context": {},
    },
    agents=[ba_agent, dev_agent, qa_agent],
)
```

---

## 7. Следующие шаги

1. **Реализация роутера** — создание полного роутера с приоритизацией
2. **Интеграция агентов** — обновление существующих агентов для соответствия стандарту
3. **Тестирование** — создание тестовых случаев для различных сценариев роутинга

---

**Примечание:** Этот стандарт обеспечивает единообразную работу мультиролевой AI системы с автоматическим роутингом и коллаборацией между агентами.

