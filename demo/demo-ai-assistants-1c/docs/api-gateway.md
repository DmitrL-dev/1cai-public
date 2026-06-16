# API Gateway Documentation

## Обзор

API Gateway представляет собой центральную точку входа для всех микросервисов, обеспечивая маршрутизацию запросов, балансировку нагрузки, аутентификацию, rate limiting, кэширование и мониторинг.

## Основные функции

### 🚦 Маршрутизация запросов
- Автоматическое направление запросов к соответствующим сервисам
- Поддержка API versioning (`/v1/service-name/...`)
- Правила маршрутизации на основе путей и методов

### ⚖️ Балансировка нагрузки
- Weighted Round-Robin алгоритм
- Health checking сервисов
- Автоматическое переключение на healthy инстансы

### 🔐 Аутентификация и авторизация
- Поддержка Bearer токенов (JWT)
- API Key аутентификация
- Service-to-service аутентификация
- Role-based access control (RBAC)

### 🚫 Rate Limiting
- Настраиваемые лимиты для каждого сервиса
- Sliding window алгоритм
- Burst handling для кратковременных всплесков

### 💾 Кэширование
- In-memory кэширование ответов
- LRU (Least Recently Used) стратегия вытеснения
- Настраиваемое время жизни кэша (TTL)

### 🛡️ Безопасность
- CORS обработка
- Security headers
- Request validation
- Request filtering

### 📊 Мониторинг и логирование
- Детальное логирование всех запросов
- Метрики производительности
- Health checks
- Error tracking

### 🔄 Circuit Breaker
- Защита от каскадных сбоев
- Автоматическое восстановление
- Fallback mechanisms

## Архитектура

```
┌─────────────────┐
│   Client App    │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐    ┌──────────────────┐
│  API Gateway    │───▶│  Load Balancer   │
└─────────┬───────┘    └────────┬─────────┘
          │                     │
          ▼                     ▼
┌─────────────────┐    ┌──────────────────┐
│   Middlewares   │    │   Microservices  │
├─────────────────┤    ├──────────────────┤
│ • CORS          │    │ • Architect      │
│ • Auth          │    │ • BA             │
│ • Rate Limit    │    │ • Developer      │
│ • Validation    │    │ • PM             │
│ • Security      │    │ • Tester         │
│ • Logging       │    └──────────────────┘
│ • Circuit Break │
└─────────────────┘
```

## Установка и настройка

### 1. Развертывание Edge Function

```bash
# Развертывание API Gateway функции
supabase functions deploy api-gateway
```

### 2. Конфигурация сервисов

Отредактируйте файл `config.ts` для настройки сервисов:

```typescript
export const serviceConfigs: Record<string, ServiceConfig> = {
  'v1/my-service': {
    name: 'my-service',
    version: 'v1',
    instances: [
      {
        url: 'https://service-url-1.supabase.co/functions/v1/my-service',
        weight: 2,
        healthy: true,
        lastCheck: Date.now()
      }
    ],
    timeout: 5000,
    retryCount: 3,
    rateLimit: {
      requestsPerMinute: 100,
      burstSize: 20
    }
  }
};
```

### 3. Настройка переменных окружения

```bash
# В Supabase Dashboard -> Settings -> Edge Functions
JWT_SECRET=your-jwt-secret
API_KEYS=key1,key2,key3
```

## Использование

### Базовые запросы

```bash
# GET запрос через API Gateway
curl -X GET "https://your-project.supabase.co/functions/v1/api-gateway/v1/architect/endpoint" \
  -H "Authorization: Bearer your-jwt-token"

# POST запрос с API ключом
curl -X POST "https://your-project.supabase.co/functions/v1/api-gateway/v1/developer/endpoint" \
  -H "x-api-key: sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"data": "example"}'
```

### Аутентификация

#### Bearer Token (JWT)
```bash
curl -H "Authorization: Bearer your-jwt-token" \
  https://your-project.supabase.co/functions/v1/api-gateway/v1/service/endpoint
```

#### API Key
```bash
curl -H "x-api-key: sk-your-api-key" \
  https://your-project.supabase.co/functions/v1/api-gateway/v1/service/endpoint
```

#### Service Key
```bash
curl -H "x-service-key: your-service-key" \
  https://your-project.supabase.co/functions/v1/api-gateway/v1/service/endpoint
```

### Параметры запросов

```bash
# С версионированием API
curl "https://your-project.supabase.co/functions/v1/api-gateway/v1/architect/data?v=1"

# С query параметрами
curl "https://your-project.supabase.co/functions/v1/api-gateway/v1/developer/data?limit=10&offset=0"
```

## Доступные сервисы

### Architect Service
- **Путь**: `/v1/architect/`
- **Методы**: GET, POST, PUT, DELETE, PATCH
- **Лимит**: 100 запросов/минута
- **Cache TTL**: 5 минут

### Business Analyst Service
- **Путь**: `/v1/ba/`
- **Методы**: GET, POST
- **Лимит**: 50 запросов/минута
- **Cache TTL**: 10 минут

### Developer Service
- **Путь**: `/v1/developer/`
- **Методы**: GET, POST, PUT, DELETE, PATCH
- **Лимит**: 200 запросов/минута
- **Cache TTL**: 3 минуты

### Project Manager Service
- **Путь**: `/v1/pm/`
- **Методы**: GET, POST, PUT
- **Лимит**: 150 запросов/минута
- **Cache TTL**: 4 минуты

### Tester Service
- **Путь**: `/v1/tester/`
- **Методы**: GET, POST, PUT
- **Лимит**: 75 запросов/минута
- **Cache TTL**: 3 минуты

## Публичные endpoints

Следующие endpoints не требуют аутентификации:

```bash
# Health check
GET /health

# Статус сервиса
GET /status

# Метрики
GET /metrics

# Документация
GET /docs

# OpenAPI спецификация
GET /openapi.json
```

## Мониторинг

### Получение метрик

```bash
curl https://your-project.supabase.co/functions/v1/api-gateway/metrics
```

Ответ содержит:
- Общее количество запросов
- Среднее время ответа
- Статистику по сервисам
- Hit rate кэша
- Использование памяти

### Получение логов

```bash
curl https://your-project.supabase.co/functions/v1/api-gateway/logs
```

### Статус circuit breaker

```bash
curl https://your-project.supabase.co/functions/v1/api-gateway/circuit-breaker/status
```

## Обработка ошибок

### Стандартные коды ошибок

| Код | Описание |
|-----|----------|
| 400 | Bad Request - неверный запрос |
| 401 | Unauthorized - требуется аутентификация |
| 403 | Forbidden - недостаточно прав |
| 404 | Not Found - ресурс не найден |
| 429 | Too Many Requests - превышен лимит запросов |
| 500 | Internal Error - внутренняя ошибка сервера |
| 502 | Bad Gateway - ошибка upstream сервиса |
| 503 | Service Unavailable - сервис недоступен |

### Примеры ошибок

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Too many requests.",
    "requestId": "uuid-here",
    "details": {
      "limit": 100,
      "remaining": 0,
      "resetTime": "2025-01-01T12:00:00Z"
    }
  }
}
```

## Конфигурация

### Rate Limiting

Настройка лимитов в `config.ts`:

```typescript
rateLimit: {
  requestsPerMinute: 100,
  burstSize: 20
}
```

### Кэширование

```typescript
cache: {
  enabled: true,
  ttl: 300000, // 5 минут в миллисекундах
  varyBy: ['authorization', 'accept-language']
}
```

### Circuit Breaker

```typescript
circuitBreaker: {
  failureThreshold: 5,
  timeout: 60000,
  resetTimeout: 30000
}
```

### Security Headers

```typescript
security: {
  headers: {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block'
  }
}
```

## Расширение функциональности

### Добавление нового сервиса

1. Добавьте конфигурацию в `config.ts`:

```typescript
export const serviceConfigs = {
  'v1/my-service': {
    name: 'my-service',
    version: 'v1',
    instances: [
      {
        url: 'https://my-service.supabase.co/functions/v1/my-service',
        weight: 1,
        healthy: true,
        lastCheck: Date.now()
      }
    ],
    timeout: 5000,
    retryCount: 3
  }
};
```

2. Добавьте правило маршрутизации:

```typescript
export const routingRules = [
  {
    pattern: '/v1/my-service/*',
    service: 'my-service',
    version: 'v1',
    methods: ['GET', 'POST']
  }
];
```

### Создание кастомного middleware

```typescript
// utils/customMiddleware.ts
export function customMiddleware(req: Request, res: Response) {
  // Ваша логика
  return response;
}
```

### Добавление кастомного validator

```typescript
// middleware/customValidation.ts
export function customValidation(req: Request): ValidationResult {
  // Ваша логика валидации
  return { valid: true, errors: [] };
}
```

## Лучшие практики

### 1. Мониторинг производительности
- Регулярно проверяйте метрики
- Настройте алерты для высоких error rate
- Отслеживайте время ответа

### 2. Управление кэшем
- Устанавливайте appropriate TTL для разных типов данных
- Используйте cache invalidation при изменении данных
- Мониторьте hit rate кэша

### 3. Rate Limiting
- Устанавливайте разумные лимиты для каждого сервиса
- Учитывайте burst capacity
- Мониторьте rate limit violations

### 4. Безопасность
- Регулярно ротируйте API ключи
- Используйте HTTPS для всех запросов
- Валидируйте все входящие данные
- Логируйте подозрительную активность

### 5. Circuit Breaker
- Настройте appropriate thresholds
- Используйте fallback strategies
- Тестируйте восстановление после сбоев

## Troubleshooting

### Частые проблемы

#### 1. Высокая latency
```bash
# Проверьте метрики
curl /metrics | grep "averageResponseTime"

# Проверьте health check сервисов
curl /status
```

#### 2. Circuit Breaker часто открывается
```bash
# Проверьте статистику circuit breaker
curl /circuit-breaker/status

# Проверьте логи ошибок
curl /logs | grep "ERROR"
```

#### 3. Низкий cache hit rate
```bash
# Проверьте статистику кэша
curl /metrics | grep "cacheHitRate"

# Проверьте настройки TTL
```

### Диагностические команды

```bash
# Полный health check
curl https://your-project.supabase.co/functions/v1/api-gateway/health

# Проверка конкретного сервиса
curl https://your-project.supabase.co/functions/v1/api-gateway/v1/architect/health

# Тест load balancing
for i in {1..10}; do
  curl -I https://your-project.supabase.co/functions/v1/api-gateway/v1/developer/data
done
```

## API Reference

### Headers

| Header | Description | Required |
|--------|-------------|----------|
| `Authorization` | Bearer JWT token | No* |
| `x-api-key` | API ключ | No* |
| `x-service-key` | Service ключ | No* |
| `Content-Type` | Тип контента | For POST/PUT |
| `X-Request-ID` | Идентификатор запроса | No |
| `X-Client-Info` | Информация о клиенте | No |

*Требуется для защищенных endpoints

### Query Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `v` | Версия API | `v1` |
| `limit` | Лимит результатов | `10` |
| `offset` | Смещение | `0` |
| `sort` | Сортировка | - |
| `filter` | Фильтрация | - |

### Response Headers

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Идентификатор запроса |
| `X-Response-Time` | Время обработки |
| `X-Cache` | HIT/MISS |
| `X-RateLimit-Remaining` | Оставшиеся запросы |
| `X-Circuit-Breaker-State` | Состояние circuit breaker |

## Поддержка

Для получения помощи и сообщения об ошибках:

1. Проверьте логи: `/logs`
2. Изучите метрики: `/metrics`
3. Проверьте health status: `/health`
4. Создайте issue с детальным описанием проблемы

---

**Версия документации**: 1.0  
**Последнее обновление**: 2025-01-01  
**API Gateway Version**: 1.0.0