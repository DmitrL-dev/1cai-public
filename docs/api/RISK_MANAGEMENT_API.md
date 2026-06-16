# Risk Management API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/risk`

## Endpoints

### Create Risk
```http
POST /api/v1/risk/create
{
  "title": "Database migration delay",
  "probability": 0.7,
  "impact": "high"
}
```

### Add Mitigation Plan
```http
POST /api/v1/risk/{id}/mitigation
{
  "action": "Start migration 2 weeks earlier",
  "owner": "DBA Team"
}
```

### List Risks
```http
GET /api/v1/risk
```

**See:** [Risk Management Guide](../06-features/RISK_MANAGEMENT_GUIDE.md)
