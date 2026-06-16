# ⚙️ Configuration Guide

**Полное руководство по настройке 1C AI Stack**

---

## 📋 Содержание

1. [Environment Variables](#environment-variables)
2. [Database Configuration](#database-configuration)
3. [Telegram Bot Configuration](#telegram-bot-configuration)
4. [AI Services Configuration](#ai-services-configuration)
5. [Security Configuration](#security-configuration)
6. [Performance Tuning](#performance-tuning)

---

## 🌐 Environment Variables

### Создание .env файла

```bash
# 1. Скопируйте example
cp env.example .env

# 2. Отредактируйте
nano .env  # Linux/Mac
notepad .env  # Windows
```

### Критичные переменные (MVP):

```bash
# Telegram Bot (обязательно)
TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>

# PostgreSQL (обязательно)
POSTGRES_PASSWORD=your_secure_password_here
DATABASE_URL=postgresql://admin:your_secure_password_here@localhost:5432/knowledge_base

# Redis (по умолчанию без пароля)
REDIS_HOST=localhost
REDIS_PORT=6379
```

---

## 🗄️ Database Configuration

### PostgreSQL

```bash
# Базовая конфигурация
POSTGRES_DB=knowledge_base
POSTGRES_USER=admin
POSTGRES_PASSWORD=changeme  # ИЗМЕНИТЕ в production!
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Connection pool (для приложения)
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20
DB_TIMEOUT=30
```

**Production настройки:**
```ini
# postgresql.conf (для высокой нагрузки)
max_connections = 200
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
```

---

### Redis

```bash
# Базовая конфигурация
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Опционально: пароль
REDIS_PASSWORD=your_redis_password

# Memory limit
REDIS_MAXMEMORY=256mb
REDIS_MAXMEMORY_POLICY=allkeys-lru
```

---

### Neo4j (опционально)

```bash
# Connection
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Memory (docker-compose.yml)
NEO4J_dbms_memory_pagecache_size=2G
NEO4J_dbms_memory_heap_max__size=4G
```

---

### Qdrant (опционально)

```bash
# Connection
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Опционально: API key
QDRANT_API_KEY=your_qdrant_api_key
```

---

## 🤖 Telegram Bot Configuration

### Базовые настройки

```bash
# Токен от @BotFather
TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>

# Администраторы (через запятую)
# Получить свой ID: https://t.me/userinfobot
TELEGRAM_ADMIN_IDS=123456789,987654321

# Premium пользователи (расширенные лимиты)
TELEGRAM_PREMIUM_IDS=111222333
```

### Rate Limiting

```bash
# Стандартные пользователи
TELEGRAM_RATE_LIMIT_MIN=10   # 10 запросов в минуту
TELEGRAM_RATE_LIMIT_DAY=100  # 100 запросов в день

# Premium пользователи (в коде)
# x2 лимиты автоматически
```

### Webhook vs Polling

**Polling (по умолчанию):**
```python
# src/telegram/bot_minimal.py
# Автоматически использует polling
```

**Webhook (для production):**
```bash
# .env
TELEGRAM_WEBHOOK_URL=https://your-domain.com/webhook
TELEGRAM_WEBHOOK_SECRET=your_secret_key

# Настройка в коде
# См. src/telegram/bot.py
```

---

## 🤖 AI Services Configuration

### OpenAI

```bash
# API Key
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxx

# Model settings
OPENAI_MODEL=gpt-4
OPENAI_TEMPERATURE=0.7
OPENAI_MAX_TOKENS=2000
```

### Ollama (локальные модели)

```bash
# Connection
OLLAMA_HOST=localhost
OLLAMA_PORT=11434

# Модель
OLLAMA_MODEL=qwen2.5-coder:7b

# Загрузка модели
docker exec -it 1c-ai-ollama ollama pull qwen2.5-coder:7b
```

### GigaChat (опционально)

```bash
GIGACHAT_API_KEY=your_gigachat_token
GIGACHAT_SCOPE=GIGACHAT_API_PERS
```

---

## 🔐 Security Configuration

### JWT Secrets

```bash
# Генерация случайного секрета
python -c "import secrets; print(secrets.token_urlsafe(32))"

# .env
JWT_SECRET=vFgT8yHnMkLp3qRsUwXyZ1aBcDeFgHiJ
SESSION_SECRET=another_random_secret_32_chars_min
```

### CORS Settings

```bash
# Development (разрешить все)
CORS_ORIGINS=["*"]

# Production (только доверенные домены)
CORS_ORIGINS=["https://your-app.com","https://admin.your-app.com"]
```

### API Keys

```bash
# Salt для генерации API ключей
API_KEY_SALT=random_salt_for_api_keys_generation
```

### API Rate Limiting

```bash
# Количество запросов на пользователя в минуту (глобально)
USER_RATE_LIMIT_PER_MINUTE=60

# Шаг окна в секундах (по умолчанию 60 = 1 минута)
USER_RATE_LIMIT_WINDOW_SECONDS=60

# Период обновления кэша витрин Marketplace (минуты)
MARKETPLACE_CACHE_REFRESH_MINUTES=15
```

> ⚠️  В production уменьшайте лимиты для публичных API и повышайте для доверенных ролей/интеграций.

### Service-to-Service Tokens

```bash
# JSON с описанием внутренних сервисов
SERVICE_API_TOKENS=[{"name":"internal-automation","token":"change_me","roles":["service"],"permissions":["marketplace:submit"]}]
```

- `name` — произвольный идентификатор сервиса
- `token` — секрет, передаваемый в заголовке `X-Service-Token`
- `roles` / `permissions` — какие права у сервиса (используется в RBAC)

### Audit Logging

```bash
# Файл с JSON-логами аудита
AUDIT_LOG_PATH=logs/security_audit.log
```

- Логи пишутся в формате JSONL (одна запись на строку)
- При активном подключении к БД дополнительно записываются в таблицу `security_audit_log`
- Содержат `timestamp`, `actor`, `action`, `target`, `metadata`
- Раздел `logs/` добавлен в `.gitignore`, но при развёртывании убедитесь, что каталог существует или прописан volume
- Для локального S3 используйте сервис MinIO из `docker-compose.stage1.yml`

### Object Storage (S3 / MinIO)

```bash
# Имя бакета для хранения артефактов marketplace
AWS_S3_BUCKET=onecai-marketplace

# Регион (обязательно для AWS, необязательно для MinIO)
AWS_S3_REGION=ru-1

# Кастомный endpoint (используйте для MinIO/Selectel/околоклонов)
AWS_S3_ENDPOINT=https://s3.selectel.ru

# Доступы сервисного пользователя
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_CREATE_BUCKET=true
MINIO_ENDPOINT=http://localhost:9000

# Максимальный размер загружаемого артефакта (в мегабайтах)
MARKETPLACE_MAX_ARTIFACT_SIZE_MB=25
```

> ℹ️  Если `AWS_S3_BUCKET` не задан, сервис отдаёт fallback-URL из базы. При использовании MinIO/Selectel настройте `AWS_S3_ENDPOINT` (или `MINIO_ENDPOINT`) и включите HTTPS.<br/>
> ✅ При первом обращении бакет создаётся автоматически (если переменная `AWS_S3_CREATE_BUCKET` не равна `false`).

---

## 📊 Monitoring Configuration

### Prometheus

```bash
# Prometheus metrics endpoint
PROMETHEUS_PORT=9090
METRICS_ENABLED=true

# Scrape interval (в prometheus.yml)
scrape_interval: 15s
```

### Grafana

```bash
# Admin credentials
GRAFANA_ADMIN_PASSWORD=admin  # ИЗМЕНИТЕ в production!

# Datasource (автоматически из prometheus.yml)
```

### Sentry (опционально)

```bash
# Error tracking
SENTRY_DSN=https://your-key@sentry.io/project-id
SENTRY_ENVIRONMENT=production
```

---

## ⚡ Performance Tuning

### Application Settings

```bash
# FastAPI workers
API_WORKERS=4  # = CPU cores

# Database pool
DB_POOL_MIN_SIZE=10
DB_POOL_MAX_SIZE=50

# Cache TTL
CACHE_TTL=3600  # 1 час
```

### Docker Resource Limits

```yaml
# docker-compose.yml
services:
  postgres:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          memory: 1G
```

---

## 🚀 Environment-specific Configuration

### Development

```bash
# .env.development
APP_ENV=development
APP_DEBUG=true
LOG_LEVEL=DEBUG
```

### Staging

```bash
# .env.staging
APP_ENV=staging
APP_DEBUG=true
LOG_LEVEL=INFO
```

### Production

```bash
# .env.production  
APP_ENV=production
APP_DEBUG=false
LOG_LEVEL=WARNING

# Security
HTTPS_ONLY=true
SECURE_COOKIES=true
```

---

## 📁 Configuration Files

### config/architecture.yaml

Главный конфигурационный файл с архитектурными настройками.

```yaml
version: "4.1"
components:
  postgresql:
    status: "active"
  redis:
    status: "active"
  neo4j:
    status: "planned"
```

### config/ci-cd.yaml

CI/CD pipeline конфигурация.

---

## 🔍 Валидация конфигурации

### Проверка .env

```bash
# Проверка что все обязательные переменные заданы
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

required = ['TELEGRAM_BOT_TOKEN', 'POSTGRES_PASSWORD', 'DATABASE_URL']
for var in required:
    if not os.getenv(var):
        print(f'MISSING: {var}')
"
```

### Проверка Docker Compose

```bash
# Валидация файла
docker-compose config

# Проверка что сервисы поднимутся
docker-compose up --dry-run
```

---

## 📖 Примеры конфигураций

### Минимальная (MVP):

```bash
# .env
TELEGRAM_BOT_TOKEN=your_token
POSTGRES_PASSWORD=changeme
DATABASE_URL=postgresql://admin:changeme@localhost:5432/knowledge_base
```

### Рекомендуемая (Development):

```bash
# .env
# Telegram
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_ADMIN_IDS=your_id

# Databases
POSTGRES_PASSWORD=dev_password
DATABASE_URL=postgresql://admin:dev_password@localhost:5432/knowledge_base
NEO4J_PASSWORD=dev_password

# AI (опционально)
OPENAI_API_KEY=sk-your-key

# Logging
LOG_LEVEL=INFO
```

### Production:

```bash
# ИСПОЛЬЗУЙТЕ SECRETS MANAGER!
# Не храните секреты в .env в production

# Kubernetes secrets
kubectl create secret generic 1c-ai-secrets \
  --from-literal=postgres-password=xxx \
  --from-literal=telegram-token=xxx \
  --from-literal=openai-key=xxx
```

---

## 🔗 См. также

- [Installation Guide](docs/01-getting-started/installation.md)
- [env.example](env.example) - все доступные переменные
- [SECURITY.md](SECURITY.md) - безопасность
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - решение проблем

---

**Обновлено:** 6 ноября 2025  
**Следующее обновление:** По мере добавления новых опций



## Environment Variables

TODO: Добавить содержание раздела.


## Database Configuration

TODO: Добавить содержание раздела.


## Telegram Bot Configuration

TODO: Добавить содержание раздела.


## Ai Services Configuration

TODO: Добавить содержание раздела.


## Security Configuration

TODO: Добавить содержание раздела.


## Performance Tuning

TODO: Добавить содержание раздела.
