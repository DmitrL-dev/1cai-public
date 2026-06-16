# Agent Collaboration Standard (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 100% - стандарты коллаборации агентов уникальны

---

## Обзор

**Agent Collaboration Standard** — формальная спецификация для коллаборации между AI агентами. Определяет workflow для совместной работы агентов, обмен контекстом и форматы сообщений.

---

## 1. Workflow для совместной работы агентов

### 1.1 Последовательная коллаборация

```python
class SequentialCollaborationWorkflow:
    """Workflow для последовательной коллаборации агентов."""
    
    async def execute(
        self,
        task: Dict[str, Any],
        agents: List[AIAgentInterface],
    ) -> Dict[str, Any]:
        """
        Выполнение задачи несколькими агентами последовательно.
        
        Returns:
            Результат выполнения задачи
        """
        context = AgentContext()
        results = []
        
        for agent in agents:
            # Выполнение задачи агентом
            result = await agent.process(
                task.get("query"),
                context=context.get_shared_data(),
            )
            
            results.append({
                "agent": agent.role.value,
                "result": result,
            })
            
            # Обмен контекстом
            context.share(f"result_{agent.role.value}", result, agent.role.value)
        
        return {
            "results": results,
            "final_result": self.merge_results(results),
        }
```

### 1.2 Параллельная коллаборация

```python
class ParallelCollaborationWorkflow:
    """Workflow для параллельной коллаборации агентов."""
    
    async def execute(
        self,
        task: Dict[str, Any],
        agents: List[AIAgentInterface],
    ) -> Dict[str, Any]:
        """
        Выполнение задачи несколькими агентами параллельно.
        
        Returns:
            Результат выполнения задачи
        """
        # Параллельное выполнение
        tasks = [
            agent.process(task.get("query"), context=task.get("context"))
            for agent in agents
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Объединение результатов
        return {
            "results": results,
            "final_result": self.merge_results(results),
        }
```

---

## 2. Обмен контекстом между агентами

См. `MULTI_ROLE_AI_AGENT_SPEC.md` для деталей `AgentContext`.

---

## 3. JSON Schema для коллаборации

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://1c-ai-stack.example.com/schemas/agent-collaboration/v1",
  "title": "AgentCollaboration",
  "type": "object",
  "required": ["agents", "workflow", "results"],
  "properties": {
    "agents": {
      "type": "array",
      "items": {"type": "string"}
    },
    "workflow": {
      "type": "string",
      "enum": ["sequential", "parallel", "hybrid"]
    },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "agent": {"type": "string"},
          "result": {"type": "object"},
          "timestamp": {"type": "string"}
        }
      }
    }
  }
}
```

---

**Примечание:** Этот стандарт обеспечивает эффективную коллаборацию между AI агентами.

