# AI Assistants — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/assistants`

## Обзор
**AI Assistants Module** — управление AI-ассистентами. Создание, настройка, использование AI помощников для различных задач.

**Возможности:** 🤖 Assistant Management | 💬 Chat Interface | 🎯 Task Automation | 📚 Knowledge Base | 🔧 Custom Tools | 🎨 Personalities

## Quick Start

```python
# Создать ассистента
assistant = await client.post("/api/v1/assistants", json={
    "name": "BSL Expert",
    "description": "Эксперт по 1C:BSL",
    "model": "gpt-4-turbo-preview",
    "instructions": "Ты эксперт по языку BSL...",
    "tools": ["code_interpreter", "knowledge_base"]
})

# Чат с ассистентом
response = await client.post(f"/api/v1/assistants/{assistant['id']}/chat", json={
    "message": "Как правильно написать запрос к регистру накопления?"
})

print(response.json()["reply"])
```

## API Reference

### Create Assistant
```http
POST /api/v1/assistants
{
  "name": "DevOps Helper",
  "model": "gpt-4",
  "instructions": "You are a DevOps expert...",
  "tools": ["code_interpreter", "file_search"],
  "temperature": 0.7
}
```

### Chat
```http
POST /api/v1/assistants/{id}/chat
{
  "message": "How to optimize Docker image?",
  "context": {...}
}

Response:
{
  "reply": "To optimize Docker image, you should...",
  "sources": ["doc_123", "doc_456"]
}
```

### Add Tool
```http
POST /api/v1/assistants/{id}/tools
{
  "type": "function",
  "function": {
    "name": "get_1c_version",
    "description": "Get 1C platform version",
    "parameters": {...}
  }
}
```

## Custom Tools

```python
# Регистрация custom tool
@assistant.tool
async def analyze_bsl_code(code: str) -> dict:
    """Analyze BSL code quality"""
    result = await code_analyzer.analyze(code)
    return {
        "quality_score": result.score,
        "issues": result.issues
    }

# Ассистент может вызывать этот tool
```

## Personalities

```python
# Разные личности для разных задач
personalities = {
    "expert": "Ты опытный эксперт, отвечай технически точно",
    "teacher": "Ты учитель, объясняй простым языком с примерами",
    "reviewer": "Ты code reviewer, будь критичным но конструктивным"
}

assistant = await client.post("/api/v1/assistants", json={
    "name": "Code Teacher",
    "instructions": personalities["teacher"]
})
```

## Multi-turn Conversations

```python
# Сохранение контекста беседы
conversation_id = "conv_123"

# Первое сообщение
await client.post(f"/api/v1/assistants/{assistant_id}/chat", json={
    "message": "Объясни что такое регистры накопления",
    "conversation_id": conversation_id
})

# Следующее сообщение (с контекстом)
await client.post(f"/api/v1/assistants/{assistant_id}/chat", json={
    "message": "А как их правильно использовать?",
    "conversation_id": conversation_id  # Контекст сохранен
})
```

## FAQ
**Q: Сколько ассистентов можно создать?** A: Без ограничений  
**Q: Поддерживается ли fine-tuning?** A: Да, см. [BSL Finetuning Guide](BSL_FINETUNING_GUIDE.md)

---

**Документация:** [AI Assistants API](../api/AI_ASSISTANTS_API.md)
