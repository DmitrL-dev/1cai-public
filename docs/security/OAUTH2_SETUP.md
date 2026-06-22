# Руководство по настройке OAuth2

## 🔐 Интеграция OAuth2 для 1C AI Stack

Это руководство описывает настройку OAuth2 аутентификации для внешних интеграций (Jira, Confluence, GitHub, GitLab и др.).

---

## 📋 Обзор

**OAuth2 Flow:** Authorization Code Grant with PKCE  
**Хранение токенов:** Зашифровано в БД  
**Обновление:** Автоматическое обновление токенов до истечения  
**Безопасность:** State параметр для CSRF защиты

---

## 🎯 Поддерживаемые провайдеры

| Провайдер      | Статус           | Требуемые Scopes                    |
| -------------- | ---------------- | ----------------------------------- |
| **GitHub**     | ✅ Реализовано   | `repo`, `read:user`                 |
| **GitLab**     | ✅ Реализовано   | `api`, `read_user`                  |
| **Jira**       | 🚧 В разработке  | `read:jira-work`, `write:jira-work` |
| **Confluence** | 🚧 В разработке  | `read:confluence-content.all`       |
| **Google**     | 📝 Запланировано | `openid`, `email`, `profile`        |
| **Microsoft**  | 📝 Запланировано | `User.Read`, `Files.Read`           |

---

## 🔧 Инструкции по настройке

### Шаг 1: Регистрация OAuth приложения

#### GitHub

1. Перейти на https://github.com/settings/developers
2. Нажать "New OAuth App"
3. Заполнить:
   - **Application name:** `1C AI Stack`
   - **Homepage URL:** `https://ваш-домен.com`
   - **Authorization callback URL:** `https://ваш-домен.com/api/oauth/github/callback`
4. Сохранить **Client ID** и **Client Secret**

#### GitLab

1. Перейти на https://gitlab.com/-/profile/applications
2. Нажать "Add new application"
3. Заполнить:
   - **Name:** `1C AI Stack`
   - **Redirect URI:** `https://ваш-домен.com/api/oauth/gitlab/callback`
   - **Scopes:** `api`, `read_user`
4. Сохранить **Application ID** и **Secret**

#### Jira (Atlassian)

1. Перейти на https://developer.atlassian.com/console/myapps/
2. Нажать "Create" → "OAuth 2.0 integration"
3. Заполнить:
   - **App name:** `1C AI Stack`
   - **Callback URL:** `https://ваш-домен.com/api/oauth/jira/callback`
   - **Scopes:** `read:jira-work`, `write:jira-work`
4. Сохранить **Client ID** и **Client Secret**

---

### Шаг 2: Настройка переменных окружения

Добавить в `.env` или Kubernetes secrets:

```bash
# GitHub OAuth
GITHUB_CLIENT_ID=ваш_github_client_id
GITHUB_CLIENT_SECRET=ваш_github_client_secret
GITHUB_REDIRECT_URI=https://ваш-домен.com/api/oauth/github/callback

# GitLab OAuth
GITLAB_CLIENT_ID=ваш_gitlab_client_id
GITLAB_CLIENT_SECRET=ваш_gitlab_client_secret
GITLAB_REDIRECT_URI=https://ваш-домен.com/api/oauth/gitlab/callback

# Jira OAuth
JIRA_CLIENT_ID=ваш_jira_client_id
JIRA_CLIENT_SECRET=ваш_jira_client_secret
JIRA_REDIRECT_URI=https://ваш-домен.com/api/oauth/jira/callback

# Ключ шифрования токенов (32 байта, base64 encoded)
OAUTH_ENCRYPTION_KEY=ваш_случайный_32_байтный_ключ_base64
```

**Сгенерировать ключ шифрования:**

```bash
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

---

### Шаг 3: Миграция БД

Запустить миграцию для создания OAuth таблиц:

```bash
alembic upgrade head
```

**Созданные таблицы:**

- `oauth_tokens` — хранит зашифрованные access/refresh токены
- `oauth_states` — CSRF защита states
- `oauth_providers` — конфигурации провайдеров

---

### Шаг 4: Обновление API Client

#### Frontend (TypeScript)

```typescript
// portal/src/services/api-integration-service.ts

async function initiateOAuth(
  provider: "github" | "gitlab" | "jira"
): Promise<string> {
  const response = await apiClient.post(`/api/oauth/${provider}/authorize`);
  const { authorization_url } = response.data;

  // Перенаправить пользователя на authorization URL
  window.location.href = authorization_url;

  return authorization_url;
}

async function handleOAuthCallback(
  provider: string,
  code: string,
  state: string
): Promise<void> {
  await apiClient.post(`/api/oauth/${provider}/callback`, { code, state });
  // Токен сохранён, можно делать аутентифицированные запросы
}
```

#### Backend (Python)

```python
# src/api/oauth_routes.py

from fastapi import APIRouter, HTTPException
from src.services.oauth_service import OAuthService

router = APIRouter(prefix="/api/oauth")
oauth_service = OAuthService()

@router.post("/{provider}/authorize")
async def authorize(provider: str):
    """Инициировать OAuth flow"""
    auth_url = await oauth_service.get_authorization_url(provider)
    return {"authorization_url": auth_url}

@router.post("/{provider}/callback")
async def callback(provider: str, code: str, state: str):
    """Обработать OAuth callback"""
    await oauth_service.exchange_code_for_token(provider, code, state)
    return {"status": "success"}
```

---

### Шаг 5: Реализация OAuth Service

```python
# src/services/oauth_service.py

import secrets
import base64
from cryptography.fernet import Fernet
from typing import Dict, Optional
import httpx

class OAuthService:
    def __init__(self):
        self.encryption_key = os.getenv("OAUTH_ENCRYPTION_KEY")
        self.fernet = Fernet(self.encryption_key.encode())

        self.providers = {
            "github": {
                "auth_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "client_id": os.getenv("GITHUB_CLIENT_ID"),
                "client_secret": os.getenv("GITHUB_CLIENT_SECRET"),
                "redirect_uri": os.getenv("GITHUB_REDIRECT_URI"),
                "scope": "repo read:user",
            },
            # ... другие провайдеры
        }

    async def get_authorization_url(self, provider: str) -> str:
        """Сгенерировать OAuth authorization URL"""
        config = self.providers[provider]

        # Сгенерировать CSRF state
        state = secrets.token_urlsafe(32)
        await self._store_state(state, provider)

        # Построить authorization URL
        params = {
            "client_id": config["client_id"],
            "redirect_uri": config["redirect_uri"],
            "scope": config["scope"],
            "state": state,
            "response_type": "code",
        }

        url = f"{config['auth_url']}?{urlencode(params)}"
        return url

    async def exchange_code_for_token(
        self, provider: str, code: str, state: str
    ) -> Dict:
        """Обменять authorization code на access token"""
        # Проверить state (CSRF защита)
        if not await self._verify_state(state, provider):
            raise HTTPException(status_code=400, detail="Invalid state")

        config = self.providers[provider]

        # Обменять code на token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_url"],
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "code": code,
                    "redirect_uri": config["redirect_uri"],
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            token_data = response.json()

        # Зашифровать и сохранить токены
        await self._store_tokens(provider, token_data)

        return token_data

    async def refresh_token(self, provider: str) -> Dict:
        """Обновить access token"""
        config = self.providers[provider]
        refresh_token = await self._get_refresh_token(provider)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_url"],
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            token_data = response.json()

        await self._store_tokens(provider, token_data)
        return token_data

    def _encrypt_token(self, token: str) -> str:
        """Зашифровать токен"""
        return self.fernet.encrypt(token.encode()).decode()

    def _decrypt_token(self, encrypted_token: str) -> str:
        """Расшифровать токен"""
        return self.fernet.decrypt(encrypted_token.encode()).decode()
```

---

### Шаг 6: Автоматическое обновление токенов

```python
# src/services/oauth_service.py

from datetime import datetime, timedelta

async def get_valid_access_token(self, provider: str) -> str:
    """Получить валидный access token, обновить если нужно"""
    token_data = await self._get_token_data(provider)

    # Проверить истёк ли токен
    expires_at = token_data["expires_at"]
    if datetime.utcnow() >= expires_at - timedelta(minutes=5):
        # Токен истёк или скоро истечёт, обновить
        token_data = await self.refresh_token(provider)

    return self._decrypt_token(token_data["access_token"])
```

---

### Шаг 7: Использование OAuth токенов

```python
# Пример: Сделать аутентифицированный запрос к GitHub API

from src.services.oauth_service import OAuthService

oauth_service = OAuthService()

async def get_github_repos(user_id: int):
    """Получить GitHub репозитории пользователя"""
    access_token = await oauth_service.get_valid_access_token("github")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user/repos",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        response.raise_for_status()
        return response.json()
```

---

## 🔒 Лучшие практики безопасности

### 1. Хранение токенов

✅ **ДЕЛАТЬ:**

- Шифровать токены в БД
- Использовать сильное шифрование (AES-256)
- Хранить ключ шифрования в Vault/KeyVault
- Периодически ротировать ключи шифрования

❌ **НЕ ДЕЛАТЬ:**

- Хранить токены в открытом виде
- Хранить токены в localStorage (frontend)
- Логировать токены
- Коммитить токены в git

### 2. CSRF защита

✅ **ДЕЛАТЬ:**

- Использовать state параметр
- Проверять state при callback
- Генерировать криптографически случайный state
- Истекать state после использования

### 3. Обновление токенов

✅ **ДЕЛАТЬ:**

- Обновлять токены до истечения (буфер 5 мин)
- Обрабатывать ошибки обновления gracefully
- Реализовать retry logic с exponential backoff

### 4. Scopes

✅ **ДЕЛАТЬ:**

- Запрашивать минимально необходимые scopes
- Документировать зачем нужен каждый scope
- Позволять пользователям просматривать scopes

---

## 🧪 Тестирование

### Unit тесты

```python
# tests/unit/test_oauth_service.py

import pytest
from src.services.oauth_service import OAuthService

@pytest.mark.asyncio
async def test_get_authorization_url():
    service = OAuthService()
    url = await service.get_authorization_url("github")

    assert "github.com/login/oauth/authorize" in url
    assert "client_id=" in url
    assert "state=" in url

@pytest.mark.asyncio
async def test_token_encryption():
    service = OAuthService()
    token = "test_access_token"

    encrypted = service._encrypt_token(token)
    decrypted = service._decrypt_token(encrypted)

    assert decrypted == token
    assert encrypted != token
```

### Integration тесты

```python
# tests/integration/test_oauth_flow.py

@pytest.mark.asyncio
async def test_oauth_flow_github(test_client):
    # Шаг 1: Получить authorization URL
    response = await test_client.post("/api/oauth/github/authorize")
    assert response.status_code == 200
    auth_url = response.json()["authorization_url"]

    # Шаг 2: Симулировать callback (с mock)
    # ... (требует мокирования GitHub OAuth)
```

---

## 📊 Мониторинг

### Метрики для отслеживания

```python
# Prometheus метрики

oauth_authorization_requests_total = Counter(
    "oauth_authorization_requests_total",
    "Всего OAuth authorization запросов",
    ["provider"]
)

oauth_token_refresh_total = Counter(
    "oauth_token_refresh_total",
    "Всего OAuth token обновлений",
    ["provider", "status"]
)

oauth_token_expiry_seconds = Histogram(
    "oauth_token_expiry_seconds",
    "Время до истечения OAuth токена",
    ["provider"]
)
```

### Алерты

```yaml
# config/prometheus/alerts/oauth.yml

groups:
  - name: oauth
    rules:
      - alert: HighOAuthFailureRate
        expr: rate(oauth_token_refresh_total{status="error"}[5m]) > 0.1
        for: 5m
        annotations:
          summary: "Высокий процент ошибок обновления OAuth токенов"
```

---

## 🐛 Устранение неполадок

### Проблема: Ошибка "Invalid state"

**Причина:** Несоответствие state (CSRF защита)

**Решение:**

- Проверить что state корректно сохранён в БД
- Убедиться что state параметр в callback совпадает
- Проверить что state не истёк

### Проблема: Ошибка "Token expired"

**Причина:** Access token истёк и обновление не удалось

**Решение:**

- Проверить что refresh token валиден
- Убедиться что refresh token endpoint корректен
- Переаутентифицировать пользователя если refresh token истёк

### Проблема: Ошибка "Insufficient scopes"

**Причина:** Отсутствуют необходимые OAuth scopes

**Решение:**

- Обновить конфигурацию scope
- Переавторизовать пользователя с новыми scopes

---

## 📚 Ссылки

- [OAuth 2.0 RFC](https://datatracker.ietf.org/doc/html/rfc6749)
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [GitHub OAuth Documentation](https://docs.github.com/en/developers/apps/building-oauth-apps)
- [GitLab OAuth Documentation](https://docs.gitlab.com/ee/api/oauth2.html)
- [Atlassian OAuth Documentation](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/)

---

**Последнее обновление:** 2025-11-22  
**Версия:** 1.0  
**Статус:** ✅ Готово к реализации
