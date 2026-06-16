# Auth API Reference

**Version:** 1.0  
**Base URL:** `/api/v1/auth`, `/api/v1/oauth`

## Endpoints

### Register
```http
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "Ivan Petrov"
}
```

### Login
```http
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

### Refresh Token
```http
POST /api/v1/auth/refresh
{"refresh_token": "eyJ..."}
```

### OAuth 2.0
```http
GET /api/v1/oauth/authorize?provider=google&redirect_uri=...
GET /api/v1/oauth/callback?code=...&state=...
```

### 2FA
```http
POST /api/v1/auth/2fa/enable
POST /api/v1/auth/2fa/verify
```

**See:** [Auth Guide](../06-features/AUTH_GUIDE.md)
