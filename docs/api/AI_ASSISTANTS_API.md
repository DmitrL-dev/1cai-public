# AI Assistants API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/assistants`

## Endpoints

### Create Assistant
```http
POST /api/v1/assistants
{
  "name": "BSL Expert",
  "model": "gpt-4-turbo-preview",
  "instructions": "You are a BSL expert...",
  "tools": ["code_interpreter", "knowledge_base"]
}
```

### Chat with Assistant
```http
POST /api/v1/assistants/{id}/chat
{
  "message": "How to optimize this query?",
  "context": {...}
}
```

### List Assistants
```http
GET /api/v1/assistants
```

### Update Assistant
```http
PUT /api/v1/assistants/{id}
```

### Delete Assistant
```http
DELETE /api/v1/assistants/{id}
```

### Add Tool
```http
POST /api/v1/assistants/{id}/tools
```

**See:** [AI Assistants Guide](../06-features/AI_ASSISTANTS_GUIDE.md)
