# Admin Dashboard API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/admin_dashboard`

## Endpoints

### Get Dashboard Data
```http
GET /api/v1/admin_dashboard
Authorization: Bearer {token}

Response: 200 OK
{
  "users": {"total": 1523, "active_today": 342},
  "tenants": {"total": 25, "active": 23},
  "system": {"health": "healthy", "cpu_usage": 45}
}
```

### Manage Users
```http
GET /api/v1/admin_dashboard/users?page=1&limit=50
POST /api/v1/admin_dashboard/users/{id}/block
PUT /api/v1/admin_dashboard/users/{id}/role
```

### Manage Tenants
```http
GET /api/v1/admin_dashboard/tenants
POST /api/v1/admin_dashboard/tenants
POST /api/v1/admin_dashboard/tenants/{id}/suspend
```

### System Settings
```http
GET /api/v1/admin_dashboard/settings
PUT /api/v1/admin_dashboard/settings
```

### Audit Logs
```http
GET /api/v1/admin_dashboard/audit?user_id={id}&action={action}
```

**See:** [Admin Dashboard Guide](../06-features/ADMIN_DASHBOARD_GUIDE.md)
