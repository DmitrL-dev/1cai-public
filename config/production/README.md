# Production-Ready конфигурации для развертывания AI-Assistants

Данная папка содержит production-ready конфигурации для развертывания системы AI-ассистентов в production среде.

## 📁 Структура файлов

```
config/production/
├── docker-compose.yml              # Основной compose файл для production
├── .env.staging                    # Переменные окружения для staging
├── .env.production                 # Переменные окружения для production
├── nginx/
│   ├── nginx.conf                  # Конфигурация Nginx с SSL и load balancing
│   └── sites-available/            # Дополнительные конфигурации сайтов
├── postgresql/
│   ├── postgresql.conf             # Оптимизированная конфигурация PostgreSQL
│   └── pg_hba.conf                 # Настройки доступа к БД
├── redis/
│   └── redis.conf                  # Конфигурация Redis для production
├── backups/
│   └── scripts/                    # Скрипты резервного копирования
├── scripts/
│   ├── backup_database.sh          # Скрипт backup PostgreSQL
│   ├── backup_redis.sh             # Скрипт backup Redis
│   └── health_check.sh             # Скрипт проверки здоровья системы
├── crontab                         # Cron задачи для автоматизации
├── secrets/
│   ├── aws_secrets_manager.sh      # Скрипт для работы с AWS Secrets Manager
│   └── docker-compose.vault.yml    # Конфигурация HashiCorp Vault
├── vault/
│   ├── config/
│   │   └── vault.hcl               # Конфигурация HashiCorp Vault
│   ├── policies/
│   │   ├── database_policy.hcl     # Политики доступа к базе данных
│   │   └── application_policy.hcl  # Политики для приложения
│   └── vault_manager.sh            # Скрипт управления Vault
└── monitoring/
    ├── prometheus/
    │   ├── prometheus.yml          # Конфигурация Prometheus
    │   └── rules/
    │       └── ai-assistants-alerts.yml  # Правила алертов
    └── alertmanager/
        └── alertmanager.yml        # Конфигурация Alertmanager
```

## 🚀 Быстрый старт

### 1. Предварительные требования

- Docker 20.10+
- Docker Compose 2.0+
- AWS CLI (для AWS Secrets Manager)
- или Vault CLI (для HashiCorp Vault)

### 2. Настройка переменных окружения

```bash
# Копирование шаблонов
cp .env.staging .env.staging.local
cp .env.production .env.production.local

# Редактирование значений
nano .env.production.local
```

### 3. Инициализация secrets management

#### Вариант A: AWS Secrets Manager

```bash
# Настройка AWS credentials
aws configure

# Инициализация секретов
./secrets/aws_secrets_manager.sh init

# Генерация .env файла
./secrets/aws_secrets_manager.sh generate-env .env.production
```

#### Вариант B: HashiCorp Vault

```bash
# Запуск Vault
docker compose -f docker-compose.vault.yml up -d vault

# Инициализация
./vault/vault_manager.sh init

# Генерация .env файла
./vault/vault_manager.sh generate-env .env.production
```

### 4. Развертывание

#### Среда staging

```bash
# Сборка и запуск
docker compose -f docker-compose.yml --env-file .env.staging up -d

# Проверка статуса
docker compose ps
```

#### Среда production

```bash
# Сборка и запуск
docker compose -f docker-compose.yml --env-file .env.production up -d

# Проверка статуса
docker compose ps
```

### 5. Настройка SSL сертификатов

```bash
# Установка Certbot
sudo apt install certbot python3-certbot-nginx

# Получение сертификата
sudo certbot --nginx -d yourcompany.com -d www.yourcompany.com

# Автоматическое обновление (добавляется в cron)
0 12 * * * /usr/bin/certbot renew --quiet
```

## 🔐 Управление секретами

### AWS Secrets Manager

```bash
# Просмотр всех секретов
./secrets/aws_secrets_manager.sh list

# Получение конкретного секрета
./secrets/aws_secrets_manager.sh get database/password

# Ротация секрета
./secrets/aws_secrets_manager.sh rotate database/password

# Резервное копирование
./secrets/aws_secrets_manager.sh backup /backup/secrets_$(date +%Y%m%d).txt
```

### HashiCorp Vault

```bash
# Аутентификация
export VAULT_TOKEN=your_root_token
export VAULT_ADDR=http://localhost:8200

# Создание политики
./vault/vault_manager.sh create-policies

# Создание токена приложения
./vault/vault_manager.sh create-token ai-assistants-app

# Резервное копирование
./vault/vault_manager.sh backup /backup/vault_$(date +%Y%m%d).txt
```

## 📊 Мониторинг и алерты

### Доступ к мониторингу

- **Prometheus**: http://yourcompany.com:9090
- **Grafana**: http://yourcompany.com:3000
  - Логин: admin
  - Пароль: из Grafana_PASSWORD в secrets
- **Alertmanager**: http://yourcompany.com:9093

### Проверка здоровья системы

```bash
# Ручной запуск health check
./scripts/health_check.sh

# Автоматическая проверка каждые 15 минут (в crontab)
*/15 * * * * /opt/ai-assistants/scripts/health_check.sh
```

## 💾 Резервное копирование

### Автоматические backup'ы

Backup'ы настраиваются автоматически через cron:

```bash
# PostgreSQL - ежедневно в 3:00
0 3 * * * /opt/ai-assistants/scripts/backup_database.sh

# Redis - каждые 6 часов
0 */6 * * * /opt/ai-assistants/scripts/backup_redis.sh
```

### Ручные backup'ы

```bash
# Backup базы данных
./scripts/backup_database.sh

# Backup Redis
./scripts/backup_redis.sh

# Backup всех secrets
./secrets/aws_secrets_manager.sh backup /backup/full_backup_$(date +%Y%m%d).txt
```

### Восстановление из backup

```bash
# Восстановление базы данных (требует остановки приложения)
docker compose stop ai-assistants
./scripts/restore_database.sh /backup/backup_YYYYMMDD_HHMMSS.sql.gz

# Восстановление secrets
./secrets/aws_secrets_manager.sh restore /backup/secrets_backup.txt
```

## 🔧 Настройка Nginx

### SSL конфигурация

Включены следующие функции безопасности:
- TLS 1.2 и 1.3
- HSTS (HTTP Strict Transport Security)
- OCSP Stapling
- Security headers
- Rate limiting

### Load Balancing

```nginx
upstream ai_assistants_backend {
    least_conn;
    server ai-assistants:8000 max_fails=3 fail_timeout=30s weight=1;
    server ai-assistants-2:8000 max_fails=3 fail_timeout=30s weight=1;
    server ai-assistants-3:8000 max_fails=3 fail_timeout=30s weight=1;
    
    keepalive 32;
}
```

### Rate Limiting

- API endpoints: 10 req/s с burst до 20
- Auth endpoints: 1 req/s с burst до 5
- Общий лимит подключений: 50 per IP

## 📈 Производительность

### Рекомендуемые ресурсы

#### Минимальная конфигурация
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 100 GB SSD
- **Network**: 1 Gbps

#### Рекомендуемая конфигурация
- **CPU**: 8 cores
- **RAM**: 16 GB
- **Storage**: 500 GB NVMe SSD
- **Network**: 10 Gbps

#### Высокая нагрузка
- **CPU**: 16+ cores
- **RAM**: 32+ GB
- **Storage**: 1+ TB NVMe SSD
- **Network**: 10+ Gbps

### Оптимизация базы данных

```sql
-- Настройки PostgreSQL включены в конфигурации:
-- shared_buffers = 25% RAM
-- effective_cache_size = 75% RAM
-- work_mem = 4MB per operation
-- autovacuum включен
-- Параллельные запросы
-- Оптимизированные индексы
```

### Кэширование Redis

- Настроено LRU eviction policy
- Сжатие RDB файлов
- AOF для durability
- Оптимизированные настройки памяти

## 🔒 Безопасность

### SSL/TLS

```nginx
# Security headers
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header X-XSS-Protection "1; mode=block" always;
```

### Секреты

- Все секреты в AWS Secrets Manager или Vault
- Автоматическая ротация ключей
- Шифрование данных в покое и в передаче
- Минимальные привилегии доступа

### Сетевая безопасность

- Изолированная Docker сеть
- Доступ к БД только для нужных сервисов
- Firewall правила
- Fail2ban для защиты от брутфорса

## 🛠️ Обслуживание

### Обновление системы

```bash
# Обновление образов
docker compose pull

# Rolling update без простоя
docker compose up -d --no-deps ai-assistants

# Проверка статуса
docker compose ps
```

### Очистка ресурсов

```bash
# Очистка неиспользуемых образов
docker image prune -a

# Очистка неиспользуемых volume'ов
docker volume prune

# Очистка системных логов
journalctl --vacuum-size=100M
```

### Мониторинг производительности

```bash
# Просмотр метрик
docker stats

# Просмотр логов
docker compose logs -f ai-assistants

# Проверка состояния БД
docker exec postgres-prod psql -U postgres -d ai_assistants -c "SELECT * FROM pg_stat_activity;"
```

## 🚨 Алерты и уведомления

### Настройка уведомлений

```yaml
# alertmanager.yml уже настроен для:
# - Email уведомления
# - Slack интеграция
# - Эскалация критических алертов
# - Подавление дубликатов
```

### Добавление новых алертов

1. Добавить правила в `monitoring/prometheus/rules/`
2. Перезагрузить Prometheus: `docker compose reload prometheus`
3. Проверить алерты в Prometheus UI

## 📞 Поддержка

### Часто задаваемые вопросы

**Q: Как добавить новый сервис?**
A: Добавить сервис в docker-compose.yml и настроить мониторинг в prometheus.yml

**Q: Как масштабировать приложение?**
A: Изменить `deploy.replicas` в docker-compose.yml и использовать оркестратор

**Q: Как добавить custom metrics?**
A: Реализовать /metrics endpoint в приложении и добавить scrape config

### Диагностика проблем

```bash
# Проверка логов
docker compose logs -f [service_name]

# Проверка состояния контейнеров
docker compose ps

# Проверка сетевых подключений
docker network inspect ai-network-prod

# Проверка использования ресурсов
docker stats --no-stream

# Health check
./scripts/health_check.sh
```

### Логирование

Логи сохраняются в:
- `/var/log/ai-assistants/` - логи приложения
- `/var/log/nginx/` - логи веб-сервера
- `/var/log/postgresql/` - логи базы данных

Ротация логов настроена через logrotate.

## 📚 Дополнительная документация

- [Prometheus документация](https://prometheus.io/docs/)
- [Grafana документация](https://grafana.com/docs/)
- [Docker Compose документация](https://docs.docker.com/compose/)
- [Nginx документация](https://nginx.org/en/docs/)
- [PostgreSQL документация](https://www.postgresql.org/docs/)
- [Redis документация](https://redis.io/documentation)

---

**Версия**: 1.0.0  
**Дата**: 2025-10-30