# Tenant Management API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/tenants`

## Endpoints

### Register Tenant
```http
POST /api/v1/tenants/register
{
  "name": "Acme Corp",
  "plan": "enterprise",
  "max_users": 100
}
```

### Add User to Tenant
```http
POST /api/v1/tenants/{id}/users
{
  "email": "user@acme.com",
  "role": "developer"
}
```

### Get Usage
```http
GET /api/v1/tenants/{id}/usage
```

### Update Plan
```http
PUT /api/v1/tenants/{id}/plan
{"plan": "enterprise"}
```

**See:** [Tenant Management Guide](../06-features/TENANT_MANAGEMENT_GUIDE.md)
