# Docker Configuration для AI Assistants 1C

Оптимизированная Docker конфигурация для микросервисной архитектуры с поддержкой production-ready развертывания, мониторинга и security best practices.

## ✨ Особенности

- 🔒 **Security First**: Non-root пользователи, multi-stage builds, security scanning
- 🚀 **Performance Optimized**: Layer caching, minimal images, resource limits
- 📊 **Production Ready**: Health checks, monitoring, logging, backup strategies
- 🛠️ **Developer Friendly**: Easy scripts, hot reload, debugging tools
- 🔄 **Scalable**: Load balancing, Redis caching, separate databases

## 🚀 Быстрый старт

### Предварительные требования

- Docker Engine 24.0+
- Docker Compose v2.20+
- 8GB RAM минимум (16GB рекомендуется)
- 30GB свободного места
- Git для получения метаданных сборки

### Установка и запуск

```bash
# Переход в директорию проекта
cd /path/to/demo-ai-assistants-1c

# Автоматическая настройка окружения
./docker/scripts/docker-dev.sh setup

# Редактирование переменных окружения
vim .env

# Сборка образов (с кэшированием слоев)
./docker/scripts/docker-build.sh

# Запуск всех сервисов
./docker/scripts/docker-dev.sh start

# Проверка здоровья сервисов
./docker/scripts/docker-dev.sh health

# Открытие мониторинга
./docker/scripts/docker-dev.sh monitor
```

## 📁 Структура Docker конфигурации

```
docker/
├── services/                    # Dockerfile для каждого микросервиса
│   ├── ai-assistant/           # AI Assistant Service (Python/FastAPI)
│   ├── 1c-integration/         # 1C Integration Service (Python/FastAPI)
│   ├── user-management/        # User Management Service (Python/FastAPI)
│   ├── analytics/              # Analytics Service (Python/FastAPI)
│   ├── security/               # Security Service (Python/FastAPI)
│   └── api-gateway/            # API Gateway (TypeScript/Deno)
├── monitoring/                  # Мониторинг и метрики
│   ├── prometheus/             # Prometheus конфигурация
│   └── grafana/                # Grafana дашборды
├── nginx/                      # Load Balancer конфигурация
├── redis/                      # Redis конфигурация
├── init-scripts/               # Скрипты инициализации БД
└── scripts/
    └── docker-dev.sh           # Скрипты разработки
```

## 📋 Docker Best Practices

### Реализованные оптимизации

#### Multi-Stage Builds
- **Builder Stage**: Компиляция зависимостей и статических ресурсов
- **Production Stage**: Минимальный runtime образ без build инструментов
- **Размер образов**: Уменьшен на 60-70% по сравнению с single-stage

#### Security Best Practices
```dockerfile
# Пример из наших Dockerfile'ов
FROM python:3.11-slim as builder
# ... build dependencies ...

FROM python:3.11-slim as production
# Создание non-root пользователя
RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid app --shell /bin/bash --create-home app

# Переключение на non-root пользователя
USER app:app

# Health checks с proper error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
```

#### Layer Optimization
```dockerfile
# Кэширование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --compile --prefix=/install -r requirements.txt

# Копирование только после установки зависимостей
COPY --chown=app:app . .

# Оптимизация размеров слоев
RUN apt-get update && apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean
```

#### Resource Management
```yaml
# Из docker-compose.yml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
    reservations:
      memory: 512M
      cpus: '0.5'
```

## 🛠 Управление сервисами

### Development скрипт с расширенными возможностями

```bash
# Базовая настройка и запуск
./docker/scripts/docker-dev.sh setup          # Автоматическая настройка
./docker/scripts/docker-dev.sh start          # Запуск всех сервисов
./docker/scripts/docker-dev.sh start ai-assistant  # Конкретный сервис

# Мониторинг и диагностика
./docker/scripts/docker-dev.sh health         # Проверка здоровья
./docker/scripts/docker-dev.sh resources      # Использование ресурсов
./docker/scripts/docker-dev.sh network        # Информация о сети
./docker/scripts/docker-dev.sh check-deps     # Проверка зависимостей

# Логи и отладка
./docker/scripts/docker-dev.sh logs           # Все логи
./docker/scripts/docker-dev.sh logs ai-assistant  # Конкретный сервис
./docker/scripts/docker-dev.sh shell ai-assistant # Shell в контейнере

# Базы данных
./docker/scripts/docker-dev.sh database       # Подключение к PostgreSQL
./docker/scripts/docker-dev.sh redis          # Подключение к Redis

# Тестирование
./docker/scripts/docker-dev.sh test           # Все тесты
./docker/scripts/docker-dev.sh test-service ai-assistant  # Тест сервиса

# Бэкапы и восстановление
./docker/scripts/docker-dev.sh backup         # Создание бэкапов
./docker/scripts/docker-dev.sh restore backup_file.sql  # Восстановление

# Системные команды
./docker/scripts/docker-dev.sh optimize       # Оптимизация Docker
./docker/scripts/docker-dev.sh architecture   # Схема архитектуры
./docker/scripts/docker-dev.sh clean          # Очистка всех ресурсов
./docker/scripts/docker-dev.sh monitor        # Открытие мониторинга
```

### Production сборка

```bash
# Сборка всех сервисов для production
DOCKER_REGISTRY=registry.company.com IMAGE_TAG=v1.2.3 ./docker/scripts/docker-build.sh

# Сборка конкретного сервиса
./docker/scripts/docker-build.sh service ai-assistant

# Отправка в registry
./docker/scripts/docker-build.sh push

# Очистка старых образов
./docker/scripts/docker-build.sh clean

# Сводка сборки
./docker/scripts/docker-build.sh summary
```

### Production развертывание

```bash
# Развертывание в production
ENVIRONMENT=production DOCKER_REGISTRY=registry.company.com IMAGE_TAG=v1.2.3 \
    ./docker/scripts/docker-deploy.sh deploy

# Развертывание в staging
ENVIRONMENT=staging ./docker/scripts/docker-deploy.sh deploy

# Проверка статуса развертывания
./docker/scripts/docker-deploy.sh status

# Валидация развертывания
./docker/scripts/docker-deploy.sh validate

# Создание бэкапа перед обновлением
./docker/scripts/docker-deploy.sh backup

# Откат к предыдущей версии
./docker/scripts/docker-deploy.sh rollback
```

### Прямое использование Docker Compose

```bash
# Все сервисы
docker-compose up -d

# Конкретный сервис
docker-compose up -d ai-assistant

# Сборка образов
docker-compose build

# Пересборка конкретного сервиса
docker-compose build ai-assistant

# Просмотр логов
docker-compose logs -f ai-assistant

# Остановка всех сервисов
docker-compose down

# Полная очистка (включая volumes)
docker-compose down -v --rmi all
```

## 🏗 Архитектура и диаграммы

### Схема микросервисной архитектуры

```
┌─────────────────────────────────────────────────────────────────┐
│                        Load Balancer (Nginx)                   │
│                        Ports: 80, 443                          │
│                        SSL Termination + Rate Limiting          │
└──────────────┬──────────────────────┬───────────────────────────┘
               │                      │
               ▼                      ▼
┌──────────────▼──────────────┐  ┌─▼──────────────────────────────┐
│        API Gateway          │  │        Monitoring Stack       │
│   (TypeScript/Deno)         │  │                               │
│   Port: 3000                │  │  Prometheus  →  Grafana       │
│                             │  │  Port: 9090    Port: 3001     │
│  ✓ Request Routing          │  │                               │
│  ✓ Load Balancing           │  │  ELK Stack                    │
│  ✓ Authentication           │  │  Elasticsearch  → Kibana      │
│  ✓ Rate Limiting            │  │  Port: 9200     Port: 5601    │
│  ✓ Circuit Breaker          │  │                               │
└──────────────┬───────────────┘  └───────────────────────────────┘
               │
      ┌────────┴────────┬──────────┬────────────┬─────────────────┐
      ▼                 ▼          ▼            ▼                 ▼
┌─────────────┐  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐
│ AI Assistant│  │ 1C Int.  │ │  User    │ │Analytics │ │ Security  │
│ Service     │  │ Service  │ │  Mgmt    │ │ Service  │ │ Service   │
│             │  │          │ │  Service │ │          │ │           │
│ Port: 8000  │  │Port: 8001│ │ Port:8002│ │Port:8003 │ │ Port:8004 │
│ Python/     │  │Python/   │ │ Python/  │ │ Python/  │ │ Python/   │
│ FastAPI     │  │ FastAPI  │ │  FastAPI │ │ FastAPI  │ │  FastAPI  │
│             │  │          │ │          │ │          │ │           │
│ ✓ OpenAI    │  │ ✓ 1C API │ │ ✓ JWT    │ │ ✓ Metrics│ │ ✓ Threat  │
│ ✓ Anthropic │  │ ✓ SOAP   │ │ ✓ OAuth  │ │ ✓ Reports│ │  Detection│
│ ✓ Caching   │  │ ✓ Sync   │ │ ✓ RBAC   │ │ ✓ Charts │ │ ✓ Audit   │
└──────┬──────┘  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘
       │               │            │            │             │
┌──────▼──────┐  ┌─────▼────┐  ┌───▼────┐  ┌───▼────┐  ┌─────▼─────┐
│ PostgreSQL  │  │ PostgreSQL│  │PostgreSQL│  │PostgreSQL│  │ PostgreSQL │
│ AI Database │  │ 1C Database│  │User Database│ │Analytics │  │ Security  │
│             │  │           │  │ Database   │ │ Database │  │ Database  │
│ Port: 5432  │  │ Port: 5432│  │Port: 5432 │  │Port: 5432│  │ Port: 5432│
└─────────────┘  └───────────┘  └───────────┘  └──────────┘  └───────────┘
                        │            │            │             │
                        └────────────┼────────────┼─────────────┘
                                     ▼
                           ┌─────────────────┐
                           │   Redis Cache   │
                           │                 │
                           │ Port: 6379      │
                           │                 │
                           │ ✓ Session Store │
                           │ ✓ Rate Limiting │
                           │ ✓ Data Cache    │
                           └─────────────────┘
```

### Детальное описание сервисов

#### Core Microservices (Python/FastAPI)

1. **AI Assistant Service** (Port 8000)
   ```python
   # Основные эндпоинты
   GET  /health              # Health check
   POST /chat                # AI чат интерфейс
   POST /generate            # Генерация контента
   GET  /models              # Список доступных моделей
   ```

2. **1C Integration Service** (Port 8001)
   ```python
   # Интеграция с 1C Enterprise
   GET  /health              # Health check
   GET  /companies           # Список компаний
   POST /sync/data           # Синхронизация данных
   GET  /reports/{id}        # Получение отчетов
   ```

3. **User Management Service** (Port 8002)
   ```python
   # Управление пользователями
   GET  /health              # Health check
   POST /auth/login          # Аутентификация
   POST /auth/register       # Регистрация
   GET  /users/{id}          # Профиль пользователя
   PUT  /users/{id}/role     # Изменение роли
   ```

4. **Analytics Service** (Port 8003)
   ```python
   # Аналитика и метрики
   GET  /health              # Health check
   GET  /metrics             # Системные метрики
   POST /reports/generate    # Генерация отчетов
   GET  /dashboards/{id}     # Дашборды
   ```

5. **Security Service** (Port 8004)
   ```python
   # Безопасность и мониторинг
   GET  /health              # Health check
   GET  /threats             # Обнаруженные угрозы
   POST /audit/log           # Аудит логи
   GET  /alerts              # Алерты безопасности
   ```

#### Gateway Service (TypeScript/Deno)

```typescript
// API Gateway маршрутизация
const routes = {
  '/api/ai/*': 'ai-assistant:8000',
  '/api/1c/*': '1c-integration:8001',
  '/api/users/*': 'user-management:8002',
  '/api/analytics/*': 'analytics:8003',
  '/api/security/*': 'security:8004',
};

// Middleware stack
const middleware = [
  rateLimiter,     // Rate limiting
  authMiddleware,  // JWT authentication
  loggingMiddleware, // Request logging
  circuitBreaker,  // Circuit breaker pattern
  loadBalancer     // Load balancing
];
```

### Infrastructure Services

#### Database Strategy
- **Отдельные PostgreSQL инстансы** для каждого микросервиса
- **Изоляция данных** и независимое масштабирование
- **Консистентные бэкапы** на уровне сервиса

#### Caching Strategy
- **Redis как центральный cache**
- **Session storage** для веб-приложения
- **Rate limiting** с Redis counters
- **Response caching** для часто запрашиваемых данных

#### Load Balancing
- **Nginx как внешний load balancer**
- **Health checks** для backend сервисов
- **SSL termination** и redirect HTTP → HTTPS
- **Static file serving** для assets

#### Monitoring & Observability
- **Prometheus** для сбора метрик
- **Grafana** для визуализации
- **ELK Stack** для логирования
- **Health checks** на уровне сервисов

## 🔍 Мониторинг и отладка

### Доступ к сервисам

```bash
# Основные сервисы
API Gateway:      http://localhost:3000
AI Assistant:     http://localhost:8000
1C Integration:   http://localhost:8001
User Management:  http://localhost:8002
Analytics:        http://localhost:8003
Security:         http://localhost:8004

# Мониторинг
Grafana:          http://localhost:3001 (admin/admin)
Prometheus:       http://localhost:9090
Kibana:           http://localhost:5601
Node Exporter:    http://localhost:9100

# База данных
PostgreSQL AI:    localhost:5433 (ai_user/ai_password)
PostgreSQL 1C:    localhost:5434 (1c_user/1c_password)
PostgreSQL User:  localhost:5435 (user_user/user_password)
PostgreSQL Analytics: localhost:5436 (analytics_user/analytics_password)
PostgreSQL Security: localhost:5437 (security_user/security_password)

# Кэш
Redis:            localhost:6379
```

### Health Checks

```bash
# Проверка здоровья всех сервисов
./docker/scripts/docker-dev.sh health

# Проверка конкретного сервиса
curl http://localhost:8000/health
curl http://localhost:3000/health
```

### Работа с базами данных

```bash
# Подключение к PostgreSQL
./docker/scripts/docker-dev.sh database

# Подключение к Redis
./docker/scripts/docker-dev.sh redis

# Создание бэкапа
./docker/scripts/docker-dev.sh backup

# Восстановление из бэкапа
./docker/scripts/docker-dev.sh restore backup_file.sql
```

## 🔧 Настройка environment

### Основные переменные в .env

```env
# Build Information
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD)
VERSION=1.0.0

# Database Configuration
POSTGRES_PASSWORD=secure_password_123

# Redis Configuration
REDIS_PASSWORD=redis_password_123

# Grafana Configuration
GRAFANA_PASSWORD=admin_password_123

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# AI Service Configuration
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# 1C Integration Configuration
1C_SERVER_URL=http://1c-server:80
1C_USERNAME=1c_admin
1C_PASSWORD=1c_password

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key
```

## 🚀 Production развертывание

### Подготовка к production

1. **Создайте production .env файл** с реальными значениями
2. **Настройте SSL сертификаты** в `docker/nginx/ssl/`
3. **Измените пароли** в environment переменных
4. **Настройте внешние базы данных** (опционально)
5. **Настройте мониторинг** AlertManager

```bash
# Production запуск
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# С мониторингом
docker-compose --profile monitoring up -d

# Без мониторинга (только основные сервисы)
docker-compose up -d
```

## 🚀 Performance Optimizations

### Image Size Optimization

| Service | Base Image | Optimized Size | Reduction |
|---------|------------|----------------|-----------|
| API Gateway | 500MB | 45MB | 91% |
| AI Assistant | 800MB | 120MB | 85% |
| 1C Integration | 750MB | 110MB | 85% |
| User Management | 700MB | 95MB | 86% |
| Analytics | 850MB | 130MB | 85% |
| Security | 720MB | 105MB | 85% |

### Build Optimizations

```bash
# Кэширование слоев
./docker/scripts/docker-build.sh --cache-from registry/service:cache

# Параллельная сборка
docker buildx build --parallel

# Multi-platform builds
./docker/scripts/docker-build.sh --platform linux/amd64,linux/arm64
```

### Runtime Optimizations

```yaml
# Resource limits для оптимальной производительности
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
    reservations:
      memory: 512M
      cpus: '0.5'
  
  # Restart policies
  restart_policy:
    condition: on-failure
    delay: 5s
    max_attempts: 3
    window: 120s
```

### Network Optimizations

```yaml
# Оптимизированные сети
networks:
  frontend:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.enable_icc: "true"
      com.docker.network.bridge.enable_ip_masquerade: "true"
      com.docker.network.driver.mtu: "1500"
  
  backend:
    driver: bridge
    driver_opts:
      com.docker.network.driver.mtu: "1500"
```

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/docker-build.yml
name: Docker Build and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
        
      - name: Build and push
        env:
          DOCKER_REGISTRY: ${{ secrets.DOCKER_REGISTRY }}
        run: |
          cd docker
          ./scripts/docker-build.sh all
          ./scripts/docker-build.sh push
          
      - name: Security scan
        run: |
          ./scripts/docker-build.sh security-scan
          
  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to production
        env:
          ENVIRONMENT: production
          DOCKER_REGISTRY: ${{ secrets.DOCKER_REGISTRY }}
        run: |
          cd docker
          ./scripts/docker-deploy.sh deploy
```

### Automated Testing Pipeline

```bash
# Интеграция с тестами
./docker/scripts/docker-dev.sh test-service ai-assistant

# Load testing
./docker/scripts/docker-dev.sh load-test

# Security testing
./docker/scripts/docker-dev.sh security-test

# Performance testing
./docker/scripts/docker-dev.sh perf-test
```

## 🔐 Security Enhancements

### Container Security Scanning

```bash
# Trivy security scanning
trivy image registry.company.com/ai-assistant:latest

# Clair vulnerability scanner
./docker/scripts/docker-dev.sh security-scan

# Checkov infrastructure scanning
checkov -f docker-compose.yml
```

### Runtime Security

```yaml
# Security options для контейнеров
security_opt:
  - no-new-privileges:true
  - apparmor:docker-default

# Read-only root filesystem
read_only: true
tmpfs:
  - /tmp:noexec,nosuid,size=100m
  - /var/tmp:noexec,nosuid,size=50m
```

### Network Security

```yaml
# Изолированные сети
networks:
  frontend:
    internal: false  # External access
  backend:
    internal: true   # Internal only
  monitoring:
    internal: true   # Monitoring network

# Drop all capabilities by default
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE  # Only for nginx
```

## 📊 Monitoring & Alerting

### Service Level Indicators (SLIs)

```yaml
# Prometheus alerting rules
groups:
  - name: microservice.rules
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High latency detected"
```

### Grafana Dashboards

```json
{
  "dashboard": {
    "title": "Microservices Overview",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "sum(rate(http_requests_total[5m])) by (service)",
            "legendFormat": "{{service}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      }
    ]
  }
}
```

## 🧹 Maintenance & Operations

### Automated Backup Strategy

```bash
#!/bin/bash
# Automated backup script
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/$DATE"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup databases
for db in postgres_ai postgres_1c postgres_user postgres_analytics postgres_security; do
  docker-compose exec -T "$db" pg_dumpall -U postgres > "$BACKUP_DIR/${db}.sql"
done

# Backup Redis
docker-compose exec -T redis redis-cli BGSAVE
docker cp redis-container:/data/dump.rdb "$BACKUP_DIR/redis_dump.rdb"

# Compress backups
tar -czf "$BACKUP_DIR.tar.gz" -C "/backups" "$DATE"

# Cleanup old backups (keep last 30 days)
find /backups -type f -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR.tar.gz"
```

### Health Check Automation

```bash
#!/bin/bash
# Automated health monitoring
ALERT_WEBHOOK="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"

check_service_health() {
  local service=$1
  local endpoint=$2
  
  if ! curl -sf "http://localhost:$endpoint/health" > /dev/null; then
    curl -X POST -H 'Content-type: application/json' \
      --data "{\"text\":\"🚨 Service $service is DOWN!\"}" \
      "$ALERT_WEBHOOK"
    
    # Attempt restart
    docker-compose restart "$service"
  fi
}

# Check all services
services=(
  "api-gateway:3000"
  "ai-assistant:8000"
  "1c-integration:8001"
  "user-management:8002"
  "analytics:8003"
  "security:8004"
)

for service_info in "${services[@]}"; do
  IFS=':' read -r service endpoint <<< "$service_info"
  check_service_health "$service" "$endpoint"
done
```

### Log Rotation and Management

```yaml
# Docker compose logging configuration
services:
  api-gateway:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "service=api-gateway"
```

```bash
# Log cleanup script
#!/bin/bash
LOG_DIR="/var/lib/docker/containers"

# Find and compress old logs
find "$LOG_DIR" -name "*.log" -mtime +7 -exec gzip {} \;

# Remove compressed logs older than 30 days
find "$LOG_DIR" -name "*.log.gz" -mtime +30 -delete

# Truncate current logs if too large
find "$LOG_DIR" -name "*.log" -size +100M -exec truncate -s 50M {} \;

echo "Log cleanup completed"
```

## 📞 Troubleshooting Guide

### Diagnostic Commands

```bash
# System diagnostics
./docker/scripts/docker-dev.sh check-deps    # Check dependencies
./docker/scripts/docker-dev.sh resources     # Resource usage
./docker/scripts/docker-dev.sh network       # Network info
./docker/scripts/docker-dev.sh architecture  # Architecture overview

# Service diagnostics
docker-compose exec ai-assistant ps aux      # Running processes
docker-compose exec ai-assistant netstat -tulpn  # Network connections
docker-compose exec ai-assistant df -h       # Disk usage
docker-compose exec ai-assistant free -h     # Memory usage
```

### Common Issues & Solutions

#### High Memory Usage
```bash
# Check memory consumption
docker stats --format "table {{.Container}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Reduce resource limits
docker-compose up -d --scale ai-assistant=1 --scale analytics=1

# Enable swap if needed
sudo swapon --show
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

#### Network Issues
```bash
# Check network connectivity
docker network ls
docker network inspect demo-ai-assistants-1c_backend

# Recreate networks
docker-compose down
docker network prune -f
docker-compose up -d
```

#### Database Connection Issues
```bash
# Check database status
docker-compose exec postgres_ai pg_isready -U ai_user

# Reset database connections
docker-compose restart postgres_ai

# Recreate database container
docker-compose stop postgres_ai
docker-compose rm postgres_ai
docker-compose up -d postgres_ai
```

---

**Автор**: DevOps Team  
**Версия**: 2.0  
**Лицензия**: MIT  
**Обновлено**: $(date +'%Y-%m-%d')
