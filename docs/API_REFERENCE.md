# 📡 API Reference

**1C AI Stack REST API Documentation**

---

## 🌐 Base Information

**Base URL:** `http://localhost:8000`  
**API Version:** v1  
**Format:** JSON  
**Authentication:** Bearer JWT (рекомендуется) | X-Service-Token (internal)

**Swagger UI:** http://localhost:8000/docs  
**ReDoc:** http://localhost:8000/redoc

---

## 🔐 Auth API

### POST /auth/token

Получить access token. Использует `OAuth2PasswordRequestForm` (username/password).

**Request (form-data):**

```
POST /auth/token
Content-Type: application/x-www-form-urlencoded

grant_type=&username=<your_username>&password=<your_password>&scope=&client_id=&client_secret=
```

**Response:**

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### GET /auth/me

Вернуть информацию о текущем пользователе.

**Headers:** `Authorization: Bearer <token>`

**Response:**

```json
{
  "user_id": "user-123",
  "username": "your_username",
  "roles": ["developer"],
  "permissions": ["marketplace:submit", "marketplace:review"],
  "full_name": "Your Name",
  "email": "you@example.com"
}
```

---

## 🔍 Search API

### POST /api/search

Semantic code search across 1C configurations.

**Request:**
```json
{
  "query": "расчет НДС",
  "limit": 10,
  "filters": {
    "module_type": "CommonModule",
    "config_name": "ERP"
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "module_name": "НалоговыеРасчеты",
      "function_name": "РассчитатьНДС",
      "code_snippet": "Функция РассчитатьНДС(...)",
      "relevance_score": 0.95,
      "config": "ERP"
    }
  ],
  "total": 1,
  "took_ms": 234
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid query
- `500` - Server error

---

## 🤖 AI Generation API

### POST /api/generate

Generate BSL code using AI.

**Request:**
```json
{
  "description": "функция для отправки email",
  "parameters": [
    {"name": "Адрес", "type": "Строка"},
    {"name": "Тема", "type": "Строка"}
  ],
  "context": {
    "module_type": "CommonModule"
  }
}
```

**Response:**
```json
{
  "code": "Функция ОтправитьEmail(Адрес, Тема) Экспорт\n  // ...",
  "explanation": "Функция отправляет email используя...",
  "confidence": 0.89
}
```

---

## 🔗 Dependencies API

### GET /api/dependencies/{module}/{function}

Get function dependencies (call graph).

**Example:**
```bash
GET /api/dependencies/CommonModule.Utilities/FormatString
```

**Response:**
```json
{
  "function": "FormatString",
  "module": "CommonModule.Utilities",
  "calls": ["СтрЗаменить", "СтрДлина"],
  "called_by": ["ФорматироватьОтчет", "ПодготовитьТекст"],
  "depth": 2
}
```

---

## 📝 Code Review API

### POST /api/code-review

AI-powered code review.

**Request:**
```json
{
  "code": "Функция РассчитатьСумму(Сумма)\n  Возврат Сумма * 1.2;\nКонецФункции",
  "language": "bsl",
  "checks": ["security", "performance", "style"]
}
```

**Response:**
```json
{
  "issues": [
    {
      "severity": "warning",
      "type": "style",
      "line": 1,
      "message": "Отсутствует комментарий функции",
      "suggestion": "Добавьте описание что делает функция"
    }
  ],
  "score": 7.5,
  "summary": "Code is mostly good, minor improvements suggested"
}
```

---

## 🧪 Test Generation API

### POST /api/generate-tests

Generate unit tests for code.

**Request:**
```json
{
  "code": "Функция СложитьЧисла(А, Б)\n  Возврат А + Б;\nКонецФункции",
  "framework": "xUnit"
}
```

**Response:**
```json
{
  "tests": [
    {
      "name": "ТестСложитьЧисла_ПоложительныеЧисла",
      "code": "Процедура ТестСложитьЧисла_ПоложительныеЧисла() Экспорт\n  ...",
      "assertions": 3
    }
  ],
  "coverage_estimate": "85%"
}
```

---

## 📊 Analytics API

### GET /api/stats

Get system statistics.

**Response:**
```json
{
  "modules_indexed": 6708,
  "functions_indexed": 117349,
  "configurations": 8,
  "total_loc": 580049,
  "last_updated": "2025-11-06T12:00:00Z"
}
```

---

### GET /api/stats/usage

Get usage statistics.

**Response:**
```json
{
  "total_requests": 1543,
  "search_requests": 892,
  "generation_requests": 234,
  "avg_response_time_ms": 456,
  "cache_hit_rate": 0.73
}
```

---

## 🔌 Marketplace API

### GET /api/marketplace/plugins

List available plugins. Cached в Redis на 5 минут для повышения производительности.

**Response:**
```json
{
  "plugins": [
    {
      "id": "sql-optimizer-v2",
      "name": "SQL Optimizer v2",
      "version": "2.1.0",
      "author": "community",
      "rating": 4.8,
      "downloads": 1234,
      "artifact_path": null
    }
  ]
}
```

### GET /api/marketplace/plugins/{plugin_id}/download

Возвращает полезную нагрузку с готовой ссылкой для скачивания. Если S3/MinIO настроены, `download_url` будет содержать подписанную ссылку (TTL 5 минут). В противном случае возвращается fallback-URL из базы.

**Response (S3 configured):**
```json
{
  "status": "ready",
  "plugin_id": "sql-optimizer-v2",
  "download_url": "https://s3.example.com/onecai/sql-optimizer-v2?X-Amz-Signature=...",
  "message": "Download link generated",
  "files": [
    "manifest.json",
    "README.md",
    "plugin.py"
  ]
}
```

**Errors:**
- `404` — плагин не найден.

### POST /api/marketplace/plugins/{plugin_id}/artifact

Загружает ZIP-артефакт плагина в S3/MinIO и привязывает его к записи marketplace. Доступно автору плагина и администраторам.

**Request:**
- `Content-Type: multipart/form-data`
- Form field `file` — архив, максимум `MARKETPLACE_MAX_ARTIFACT_SIZE_MB` мегабайт (по умолчанию 25 MB).

```bash
curl -X POST http://localhost:8000/marketplace/plugins/sql-optimizer-v2/artifact \
  -H "Authorization: Bearer <JWT>" \
  -F "file=@dist/sql-optimizer-v2.zip"
```

**Response:**
```json
{
  "id": "sql-optimizer-v2",
  "name": "SQL Optimizer v2",
  "artifact_path": "marketplace/sql-optimizer-v2/8b2c.../sql-optimizer-v2.zip",
  "download_url": "/marketplace/plugins/sql-optimizer-v2/download",
  "updated_at": "2025-11-08T21:10:33.512Z",
  "status": "pending"
}
```

**Errors:**
- `400` — файл пустой.
- `403` — нет прав на обновление плагина.
- `404` — плагин не найден.
- `413` — файл превышает допустимый размер.
- `503` — объектное хранилище не настроено.

### GET /api/marketplace/trending

Возвращает трендовые плагины. Данные кэшируются в Redis и пересчитываются планировщиком раз в 5 минут (настраивается переменной `MARKETPLACE_CACHE_REFRESH_MINUTES`).

---

## 🔄 WebSocket API

### ws://localhost:8000/ws

Real-time updates.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update:', data);
};
```

**Message Types:**
```json
{
  "type": "indexing_progress",
  "data": {
    "current": 1000,
    "total": 6708,
    "percent": 15
  }
}
```

---

## 🔐 Authentication

### API Key (optional)

**Get API Key:**
```bash
POST /api/auth/register
{
  "email": "user@example.com",
  "password": "secure_password"
}

# Response
{
  "api_key": "1c-ai_xxxxxxxxxxxxxxxx"
}
```

**Use API Key:**
```bash
curl -H "X-API-Key: 1c-ai_xxxxxxxx" \
     http://localhost:8000/api/search
```

### Service-to-Service Token

Используйте для внутренних интеграций без участия пользователя.

**Headers:**
```http
X-Service-Token: <token из SERVICE_API_TOKENS>
Content-Type: application/json
```

**Пример:**
```bash
curl -H "X-Service-Token: change_me" \
     http://localhost:8000/marketplace/plugins
```

Права сервиса определяются в ENV (`roles`, `permissions`).

---

## 🛡️ Admin Role Management

### POST /admin/users/{user_id}/roles

Назначить роль пользователю.

```json
{
  "role": "moderator",
  "reason": "On-call rotation"
}
```

- Требуется роль `admin`
- Запись аудит-лога создаётся автоматически

### DELETE /admin/users/{user_id}/roles/{role}

Отозвать роль.

### POST /admin/users/{user_id}/permissions

Назначить разрешение (fine-grained).

### DELETE /admin/users/{user_id}/permissions/{permission}

Отозвать разрешение.

Response: `204 No Content`

---

## 📜 Security Audit API

### GET /admin/audit

Возвращает список записей аудита (только для `admin`):

```bash
curl "http://localhost:8000/admin/audit?limit=20&actor=admin" \
  -H "Authorization: Bearer <admin_token>"
```

Query-параметры:
- `limit` (1..200), `offset`
- `actor`, `action` — фильтры

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "timestamp": "2025-11-07T12:00:00+00:00",
      "actor": "admin",
      "action": "admin.role.grant",
      "target": "user-123",
      "metadata": {"role": "moderator"}
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

## 📊 Executive Dashboard API

### GET /api/dashboard/metrics

Получить ключевые бизнес-метрики (ROI, Health Score).

**Response:**
```json
{
  "roi_percentage": 450,
  "system_health": 0.98,
  "active_users": 1250
}
```

---

## 📚 Knowledge Base API

### POST /api/knowledge/search

Семантический поиск по базе знаний.

**Request:**
```json
{
  "query": "как настроить резервное копирование",
  "limit": 5
}
```

---

## 🎭 Scenario Hub API

### GET /api/scenarios

Получить список доступных сценариев.

### POST /api/scenarios/{id}/execute

Запустить выполнение сценария.

---

## 📖 Wiki API

### GET /api/wiki/pages/{slug}

Получить содержимое Wiki-страницы.

---

## 📈 Rate Limits

### Default Limits

```yaml
Anonymous: 10 requests/minute
Authenticated: 60 requests/minute
Premium: Unlimited
```

> Все аутентифицированные запросы учитываются по `user_id` (JWT). Для гостей — по IP. При превышении вернётся `429` с сообщением `"Too many requests"`.

**Headers:**
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1699300000
```

---

## 🐛 Error Responses

### Standard Error Format

```json
{
  "error": {
    "code": "INVALID_QUERY",
    "message": "Query cannot be empty",
    "details": {
      "field": "query",
      "constraint": "min_length"
    }
  },
  "timestamp": "2025-11-06T12:00:00Z",
  "request_id": "req_abc123"
}
```

### Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `INVALID_QUERY` | 400 | Query validation failed |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |

---

## 📝 SDK Examples

### Python

```python
import requests

# Search
response = requests.post('http://localhost:8000/api/search', json={
    'query': 'расчет налога',
    'limit': 5
})
results = response.json()

# Generate code
response = requests.post('http://localhost:8000/api/generate', json={
    'description': 'функция для сохранения файла'
})
code = response.json()['code']
```

### JavaScript

```javascript
// Search
const response = await fetch('http://localhost:8000/api/search', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({query: 'расчет НДС', limit: 10})
});
const results = await response.json();
```

### cURL

```bash
# Search
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query":"расчет скидки","limit":10}'

# Generate
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"description":"функция для проверки email"}'
```

---

## 🔗 Дополнительно

- **Interactive API Docs:** http://localhost:8000/docs
- **OpenAPI Spec:** http://localhost:8000/openapi.json
- **Health Check:** http://localhost:8000/health

---

**Обновлено:** 7 ноября 2025  
**API Version:** 2.2.0

