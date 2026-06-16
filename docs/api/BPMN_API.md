# BPMN API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/bpmn`

## Endpoints

### Generate BPMN
```http
POST /api/v1/bpmn/generate
{
  "description": "Order processing: receive -> validate -> fulfill -> ship"
}

Response:
{
  "xml": "<?xml version='1.0'?>...",
  "svg": "<svg>...</svg>"
}
```

### Export BPMN
```http
GET /api/v1/bpmn/{id}/export?format=xml
GET /api/v1/bpmn/{id}/export?format=svg
GET /api/v1/bpmn/{id}/export?format=png
```

**See:** [BPMN API Guide](../06-features/BPMN_API_GUIDE.md)
