# Knowledge Base API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/knowledge_base`

## Endpoints

### Add Document
```http
POST /api/v1/knowledge_base/documents
{
  "title": "BSL Best Practices",
  "content": "...",
  "tags": ["bsl", "best-practices"]
}
```

### Search
```http
GET /api/v1/knowledge_base/search?q=запросы
```

### Get Recommendations
```http
GET /api/v1/knowledge_base/recommendations?context=writing_bsl_code
```

### Import
```http
POST /api/v1/knowledge_base/import/confluence
POST /api/v1/knowledge_base/import/markdown
```

**See:** [Knowledge Base Guide](../06-features/KNOWLEDGE_BASE_GUIDE.md)
