# 📦 Installation Guide

**Полная инструкция по установке 1C AI Stack**

---

## 📋 Требования

### Минимальные требования:

```yaml
OS: Windows 10+, Ubuntu 20.04+, macOS 11+
Python: 3.11.x (рекомендуем 3.11.9)
RAM: 4 GB (MVP) или 8-12 GB (full stack)
Disk: 10 GB свободного места
```

### Опционально:

```yaml
Docker: 20.10+ (рекомендуется)
Docker Compose: 2.0+
Node.js: 18+ (для frontend)
Java: 17+ (для EDT plugin)
```

---

## 🚀 Установка (3 варианта)

### Вариант 1: Минимальный (только Telegram Bot)

**Время:** 5-10 минут  
**Требования:** Python 3.11.x

```bash
# Проверьте, что используется правильная версия Python
python --version  # ожидаем Python 3.11.x

# Шаг 1: Клонировать проект
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public

# Шаг 2: Создать virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac  
source venv/bin/activate

# Шаг 3: Установить зависимости
pip install -r requirements-telegram.txt

# Шаг 4: Создать .env
cp env.example .env

# Шаг 5: Получить Telegram Bot Token
# 1. Открыть https://t.me/BotFather
# 2. /newbot
# 3. Скопировать токен

# Шаг 6: Настроить .env
nano .env
# Добавить: TELEGRAM_BOT_TOKEN=your_token_here
# Также задайте: JWT_SECRET (случайная строка), JWT_ACCESS_TOKEN_EXPIRE_MINUTES, AUTH_DEMO_USERS (JSON со списком аккаунтов)

### Marketplace и хранилище

```bash
# Лимиты и кэш API (по умолчанию включено)
USER_RATE_LIMIT_PER_MINUTE=60
USER_RATE_LIMIT_WINDOW_SECONDS=60
MARKETPLACE_CACHE_REFRESH_MINUTES=15

# S3/MinIO для артефактов плагинов (опционально)
AWS_S3_BUCKET=onecai-marketplace
AWS_S3_REGION=ru-1
AWS_S3_ENDPOINT=https://s3.selectel.ru  # если используете Selectel/MinIO
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

> После изменения переменных перезапустите backend (`docker-compose restart api` или `systemctl restart onecai`).

# Шаг 7: Запустить PostgreSQL + Redis (через Docker)
docker-compose up -d postgres redis

# Шаг 8: Запустить бота
python src/telegram/bot_minimal.py

# Готово! Бот работает в Telegram
```

---

### Вариант 2: MVP Stack (Docker)

**Время:** 10-15 минут  
**Требования:** Docker, Docker Compose

```bash
# Шаг 1: Клонировать
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public

# Шаг 2: Создать .env
cp env.example .env
nano .env  # Настроить токены

# Шаг 3: Запустить минимальный стек
docker-compose -f docker-compose.mvp.yml up -d

# Шаг 4: Проверить
docker-compose ps
# Должны быть: postgres (Up), redis (Up)

# Шаг 5: Подготовить backend
pip install -r requirements.txt
python scripts/run_migrations.py
uvicorn src.main:app --reload

# Шаг 6: Запустить Telegram Bot
python src/telegram/bot_minimal.py

# Доступно:
# - Telegram Bot
# - REST API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

---

### Вариант 3: Full Stack (все компоненты)

**Время:** 20-30 минут  
**Требования:** Docker, Docker Compose, 12 GB RAM

```bash
# Шаг 1: Клонировать
git clone https://github.com/DmitrL-dev/1cai-public.git
cd 1cai-public

# Шаг 2: Настроить .env
cp env.example .env
# Заполнить ВСЕ необходимые переменные:
# - TELEGRAM_BOT_TOKEN
# - POSTGRES_PASSWORD
# - NEO4J_PASSWORD
# - OPENAI_API_KEY (опционально)

# Шаг 3: Запустить все сервисы
docker-compose -f docker-compose.yml \
               -f docker-compose.stage1.yml up -d

# Шаг 3.1: Применить миграции (один раз)
docker-compose run --rm migrations

# Шаг 4: Дождаться инициализации (~2-3 минуты)
docker-compose logs -f

# Шаг 5: Проверить все сервисы
docker-compose ps

# Должны быть UP:
# - postgres
# - redis
# - neo4j
# - qdrant
# - ollama (опционально)

# Шаг 6: Загрузить Ollama модель (опционально)
docker exec -it 1c-ai-ollama ollama pull qwen2.5-coder:7b

# Шаг 7: Запустить приложения
uvicorn src.main:app --reload  # FastAPI
python src/ai/mcp_server.py    # MCP Server  
python src/telegram/bot_minimal.py  # Telegram Bot

### Опционально: S3/MinIO для артефактов

```bash
# Запустить MinIO (локальное s3-хранилище)
docker-compose -f docker-compose.yml -f docker-compose.stage1.yml up -d minio

# Создать бакет по умолчанию (onecai-artifacts)
docker-compose -f docker-compose.yml -f docker-compose.stage1.yml run --rm minio-setup

# Консоль: http://localhost:9001 (логин/пароль в .env)
# API endpoint: http://localhost:9000
```

После запуска задайте `AWS_S3_ENDPOINT=http://localhost:9000` и креды `MINIO_ROOT_USER/MINIO_ROOT_PASSWORD` в `.env`.

# Доступно:
# - Telegram Bot
# - MCP Server: http://localhost:6001
# - REST API: http://localhost:8000
# - Neo4j Browser: http://localhost:7474
# - Qdrant Dashboard: http://localhost:6333/dashboard
```

---

## 🔧 Установка по компонентам

### PostgreSQL (обязательно)

```bash
# Вариант A: Docker (рекомендуется)
docker-compose up -d postgres

# Вариант B: Локальная установка
# Windows: https://www.postgresql.org/download/windows/
# Linux: sudo apt install postgresql-15
# Mac: brew install postgresql@15

# Создание БД
psql -U postgres
CREATE DATABASE knowledge_base;
CREATE USER admin WITH PASSWORD 'changeme';
GRANT ALL PRIVILEGES ON DATABASE knowledge_base TO admin;
```

---

### Redis (обязательно)

```bash
# Вариант A: Docker (рекомендуется)
docker-compose up -d redis

# Вариант B: Локальная установка
# Windows: https://github.com/tporadowski/redis/releases
# Linux: sudo apt install redis-server
# Mac: brew install redis

# Запуск
redis-server
```

---

### Neo4j (опционально)

```bash
# Только через Docker
docker-compose -f docker-compose.stage1.yml up -d neo4j

# Доступ к браузеру
open http://localhost:7474
# Логин: neo4j
# Пароль: из .env (NEO4J_PASSWORD)
```

---

### Qdrant (опционально)

```bash
# Только через Docker  
docker-compose -f docker-compose.stage1.yml up -d qdrant

# Проверка
curl http://localhost:6333/health
```

---

### Ollama (опционально)

```bash
# Docker с GPU
docker-compose -f docker-compose.stage1.yml up -d ollama

# Загрузка модели
docker exec -it 1c-ai-ollama ollama pull qwen2.5-coder:7b

# Проверка
curl http://localhost:11434/api/tags
```

---

## 🐍 Python Dependencies

### Основные зависимости:

```bash
# Все зависимости
pip install -r requirements.txt

# Только Telegram
pip install -r requirements-telegram.txt

# Development
pip install -r requirements-dev.txt

# Проверка
pip list | grep -E "fastapi|aiogram|asyncpg"
```

---

## 🔍 Проверка установки

### Health Checks:

```bash
# 1. PostgreSQL
docker exec -it 1c-ai-postgres pg_isready
# Ожидается: accepting connections

# 2. Redis
docker exec -it 1c-ai-redis redis-cli PING
# Ожидается: PONG

# 3. FastAPI
curl http://localhost:8000/health
# Ожидается: {"status": "ok"}

# 4. MCP Server
curl http://localhost:6001/health
# Ожидается: {"status": "healthy"}

# 5. Telegram Bot
# Отправьте /start боту в Telegram
# Должен ответить приветствием
```

---

## 🐛 Проблемы при установке?

См. [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md)

Или создайте issue: https://github.com/DmitrL-dev/1cai-public/issues

---

## 📚 Следующие шаги

После установки:
1. [Quick Start Guide](quickstart.md) - первые шаги
2. [Telegram Setup](telegram-setup.md) - настройка бота
3. [Configuration](../../CONFIGURATION.md) - детальная настройка

---

**Обновлено:** 6 ноября 2025  
**Уровень:** Beginner-friendly

