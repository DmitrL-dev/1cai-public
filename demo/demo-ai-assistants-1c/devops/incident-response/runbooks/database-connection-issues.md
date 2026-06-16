# Runbook: Database Connection Issues

## Симптомы

- Ошибки подключения к базе данных
- Таймауты при обращении к БД
- Повышенное время отклика API
- Ошибки в логах: `connection refused`, `timeout`, `database unavailable`

## Диагностика

### 1. Проверка статуса базы данных

```bash
# Подключение к базе данных
psql -h $DATABASE_HOST -U postgres -d aiassistants -c "SELECT version();"

# Проверка подключений
psql -h $DATABASE_HOST -U postgres -d aiassistants -c "
  SELECT count(*) as active_connections 
  FROM pg_stat_activity 
  WHERE state = 'active';
"

# Проверка блокировок
psql -h $DATABASE_HOST -U postgres -d aiassistants -c "
  SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS current_statement_in_blocking_process
  FROM pg_catalog.pg_locks blocked_locks
  JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
  JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
  JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
  WHERE NOT blocked_locks.granted;
"
```

### 2. Проверка ресурсов БД

```bash
# Проверка использования CPU и памяти
psql -h $DATABASE_HOST -U postgres -d aiassistants -c "
  SELECT 
    datname,
    numbackends as active_connections,
    xact_commit,
    xact_rollback,
    blks_read,
    blks_hit,
    tup_returned,
    tup_fetched,
    tup_inserted,
    tup_updated,
    tup_deleted
  FROM pg_stat_database 
  WHERE datname = 'aiassistants';
"

# Проверка размера таблиц
psql -h $DATABASE_HOST -U postgres -d aiassistants -c "
  SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
  FROM pg_stats 
  WHERE schemaname = 'public'
  ORDER BY tablename, attname;
"
```

### 3. Проверка сетевого подключения

```bash
# Ping базы данных
ping $DATABASE_HOST

# Проверка порта
nc -zv $DATABASE_HOST 5432

# Проверка DNS
nslookup $DATABASE_HOST
```

## Решения

### Решение 1: Перезапуск подключений

```bash
# Перезапуск подключений (если проблема в зависших соединениях)
# Внимание: Это разорвет все активные соединения!

kubectl rollout restart deployment/ai-assistants-api -n ai-assistants

# Или для конкретного пода
kubectl delete pod -l app=ai-assistants-api -n ai-assistants
```

### Решение 2: Масштабирование БД

```bash
# Временно увеличить количество подключений
psql -h $DATABASE_HOST -U postgres -d aiassistants -c "
  ALTER SYSTEM SET max_connections = '200';
  SELECT pg_reload_conf();
"

# Проверить текущие настройки
psql -h $DATABASE_HOST -U postgres -d aiassistants -c "
  SHOW max_connections;
"
```

### Решение 3: Переключение на реплику

```bash
# Обновить конфигурацию для использования read реплики
kubectl create configmap db-replica-config --from-literal=database.host=replica-db.company.com -n ai-assistants --dry-run=client -o yaml | kubectl apply -f -

# Перезапуск приложения
kubectl rollout restart deployment/ai-assistants-api -n ai-assistants
```

### Решение 4: Масштабирование приложения

```bash
# Увеличить количество реплик приложения
kubectl scale deployment ai-assistants-api --replicas=10 -n ai-assistants

# Увеличить ресурсы для БД (через Terraform/Console)
# В продакшене - через Terraform модуль
terraform apply -target=module.rds
```

## Мониторинг

### Метрики для отслеживания

```bash
# Графана дашборд: Database Performance
# - Database connections
# - Query response time
# - Database CPU utilization
# - Database memory usage
# - Slow queries count

# Промetheus метрики
# - database_connection_pool_active
# - database_connection_pool_idle
# - database_query_duration
# - database_errors_total
```

### Алерты

```yaml
# PrometheusRule для алертов БД
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: database-alerts
  namespace: ai-assistants
spec:
  groups:
  - name: database.rules
    rules:
    - alert: DatabaseConnectionsHigh
      expr: database_connection_pool_active > 80
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Database connections are high"
        description: "Active database connections: {{ $value }}"

    - alert: DatabaseQuerySlow
      expr: database_query_duration_p95 > 1000
      for: 2m
      labels:
        severity: warning
      annotations:
        summary: "Database queries are slow"
        description: "95th percentile query time: {{ $value }}ms"

    - alert: DatabaseDown
      expr: up{job="database"} == 0
      for: 1m
      labels:
        severity: critical
      annotations:
        summary: "Database is down"
        description: "Database has been unreachable for more than 1 minute"
```

## Профилактика

### 1. Настройка пула соединений

```javascript
// В приложении - ограничение количества соединений
const pool = new Pool({
  host: process.env.DATABASE_HOST,
  port: process.env.DATABASE_PORT,
  database: process.env.DATABASE_NAME,
  user: process.env.DATABASE_USER,
  password: process.env.DATABASE_PASSWORD,
  max: 20,        // Максимум соединений
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});
```

### 2. Мониторинг и алертинг

- Настройка метрик пула соединений
- Алерты при превышении 80% от максимума
- Мониторинг медленных запросов

### 3. Регулярное обслуживание

```bash
# Автоматическое обслуживание БД
# Добавить в crontab
0 2 * * 0 psql -h $DB_HOST -U postgres -d aiassistants -c "VACUUM ANALYZE;"

# Мониторинг размера таблиц
# Автоматическая очистка старых данных
```

## Контакты

- **DevOps Team**: devops@company.com
- **Database Team**: dba@company.com
- **Emergency**: +7 (495) 123-45-67