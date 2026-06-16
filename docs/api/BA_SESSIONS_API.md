# BA Sessions API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/ba_sessions`

## Endpoints

### Create Session
```http
POST /api/v1/ba_sessions/create
{
  "project": "1C Integration",
  "stakeholders": ["Product Owner", "Tech Lead"],
  "duration_minutes": 60
}
```

### Add Requirements
```http
POST /api/v1/ba_sessions/{id}/requirements
{
  "text": "System must support OAuth 2.0"
}
```

### Export Session
```http
GET /api/v1/ba_sessions/{id}/export?format=pdf
```

### List Sessions
```http
GET /api/v1/ba_sessions
```

**See:** [BA Sessions Guide](../06-features/BA_SESSIONS_GUIDE.md)
