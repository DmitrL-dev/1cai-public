# Auth — Руководство пользователя

**Версия:** 1.0 | **Статус:** ✅ Production Ready | **API:** `/api/v1/auth`, `/api/v1/oauth`

---

## Обзор

**Auth Module** — модуль аутентификации и авторизации с поддержкой JWT, OAuth 2.0, RBAC, 2FA.

**Для кого:** Все пользователи платформы, администраторы безопасности

**Возможности:**
- 🔐 JWT Authentication
- 🔑 OAuth 2.0 (Google, GitHub, Microsoft)
- 👥 RBAC (Role-Based Access Control)
- 🔒 2FA (Two-Factor Authentication)
- 📱 Session Management
- 🔄 Token Refresh

---

## Quick Start

```python
# Регистрация
response = await client.post("/api/v1/auth/register", json={
    "email": "user@example.com",
    "password": "SecurePass123!",
    "full_name": "Ivan Petrov"
})

# Вход
response = await client.post("/api/v1/auth/login", json={
    "email": "user@example.com",
    "password": "SecurePass123!"
})

tokens = response.json()
access_token = tokens["access_token"]
refresh_token = tokens["refresh_token"]

# Использование токена
headers = {"Authorization": f"Bearer {access_token}"}
response = await client.get("/api/v1/dashboard", headers=headers)
```

---

## API Reference

### Register
```http
POST /api/v1/auth/register
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "full_name": "Ivan Petrov"
}

Response:
{
  "user_id": "usr_123",
  "email": "user@example.com",
  "created_at": "2025-11-27T12:00:00Z"
}
```

### Login
```http
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}

Response:
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Refresh Token
```http
POST /api/v1/auth/refresh
{
  "refresh_token": "eyJ..."
}

Response:
{
  "access_token": "eyJ...",
  "expires_in": 3600
}
```

### OAuth 2.0
```http
GET /api/v1/oauth/authorize?provider=google&redirect_uri=...

# После авторизации
GET /api/v1/oauth/callback?code=...&state=...

Response:
{
  "access_token": "eyJ...",
  "user": {
    "id": "usr_123",
    "email": "user@gmail.com",
    "provider": "google"
  }
}
```

---

## RBAC (Role-Based Access Control)

### Роли по умолчанию:
- `admin` — полный доступ
- `developer` — разработка и тестирование
- `analyst` — аналитика и отчеты
- `viewer` — только чтение

### Проверка прав:
```python
from src.modules.auth.api.dependencies import require_role

@router.get("/admin/users")
async def get_users(user = Depends(require_role("admin"))):
    # Только для admin
    return {"users": [...]}
```

---

## 2FA (Two-Factor Authentication)

```python
# Включить 2FA
response = await client.post("/api/v1/auth/2fa/enable")
qr_code = response.json()["qr_code"]  # QR для Google Authenticator

# Подтвердить 2FA
await client.post("/api/v1/auth/2fa/verify", json={
    "code": "123456"
})

# Вход с 2FA
await client.post("/api/v1/auth/login", json={
    "email": "user@example.com",
    "password": "SecurePass123!",
    "totp_code": "123456"
})
```

---

## Best Practices

1. **Пароли:** Минимум 12 символов, буквы + цифры + спецсимволы
2. **Токены:** Храните refresh token в httpOnly cookie
3. **HTTPS:** Всегда используйте HTTPS в production
4. **2FA:** Включайте для admin аккаунтов
5. **Session Timeout:** Настройте автоматический logout

---

## Troubleshooting

**Проблема: Token expired**
```python
# Автоматический refresh
if response.status_code == 401:
    new_token = await refresh_access_token(refresh_token)
    # Повторить запрос с новым токеном
```

**Проблема: Invalid credentials**
```python
# Проверьте email и пароль
# Проверьте что аккаунт не заблокирован
await client.get("/api/v1/auth/account/status")
```

---

## FAQ

**Q: Как сбросить пароль?**  
A: `POST /api/v1/auth/password/reset` с email

**Q: Поддерживается ли SSO?**  
A: Да, через OAuth 2.0 (Google, GitHub, Microsoft, LDAP)

**Q: Как настроить session timeout?**  
A: В `.env`: `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60`

---

**Документация:** [Auth API](../api/AUTH_API.md)
