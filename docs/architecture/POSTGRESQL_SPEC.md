# PostgreSQL Standard (Specification)

> **Статус:** ✅ Production Ready  
> **Версия:** 1.0.0  
> **Дата:** 2025-11-17  
> **Уникальность:** 95-100%  
> **Категория:** Data Storage

---

## Обзор

**PostgreSQL Standard** — формальная спецификация для работы с PostgreSQL базой данных в платформе 1C AI Stack.

PostgreSQL является основной реляционной базой данных платформы, обеспечивающей хранение метаданных конфигураций 1С, пользователей, прав доступа, статистики использования и audit logs.

### Ключевые особенности:

1. **ACID Compliance** — полная поддержка транзакций с гарантиями ACID
2. **JSON Support** — нативная поддержка JSON и JSONB для хранения структурированных данных
3. **Full-text Search** — полнотекстовый поиск для документов и кода
4. **Partitioning** — партиционирование таблиц для масштабирования
5. **Connection Pooling** — пул соединений для оптимизации производительности
6. **Backup and Restore** — автоматическое резервное копирование и восстановление

---

## 1. Основные принципы

### 1.1 Требования

**Основные требования к PostgreSQL в платформе:**

1. **Версия**
   - Минимальная версия: PostgreSQL 15
   - Рекомендуемая версия: PostgreSQL 15+ (alpine образ для Docker)
   - Поддержка расширений: pg_trgm, pg_stat_statements, uuid-ossp

2. **Производительность**
   - Время выполнения запросов: p95 < 100ms
   - Размер пула соединений: 10-50 соединений (зависит от нагрузки)
   - Timeout подключения: 30 секунд
   - Timeout выполнения запроса: 60 секунд

3. **Безопасность**
   - Шифрование соединений: TLS 1.3
   - Шифрование данных: Encryption at rest (через Docker volumes)
   - Аутентификация: password-based или certificate-based
   - Локализация данных: серверы должны находиться в РФ для персональных данных

4. **Масштабируемость**
   - Поддержка репликации: Master-Slave для чтения
   - Партиционирование: для больших таблиц (>10M записей)
   - Индексация: автоматическая для всех внешних ключей и часто используемых полей

5. **Резервное копирование**
   - Частота: ежедневно (полный backup) + hourly (WAL)
   - Хранение: минимум 30 дней
   - Тестирование восстановления: еженедельно

---

### 1.2 Алгоритмы работы

#### Алгоритм: Установка соединения

```python
import asyncpg
from contextlib import asynccontextmanager

class PostgreSQLClient:
    def __init__(self, connection_string: str, pool_size: int = 10):
        self.connection_string = connection_string
        self.pool_size = pool_size
        self._pool = None
    
    async def connect(self):
        """Создание пула соединений"""
        self._pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=5,
            max_size=self.pool_size,
            command_timeout=60,
            server_settings={
                'application_name': '1c-ai-stack',
                'statement_timeout': '60000'
            }
        )
    
    @asynccontextmanager
    async def get_connection(self):
        """Получение соединения из пула"""
        if not self._pool:
            await self.connect()
        
        async with self._pool.acquire() as connection:
            yield connection
    
    async def execute_query(self, query: str, *args):
        """Выполнение запроса с обработкой ошибок"""
        async with self.get_connection() as conn:
            try:
                result = await conn.fetch(query, *args)
                return result
            except asyncpg.PostgresError as e:
                logger.error(f"PostgreSQL error: {e}", extra={"query": query})
                raise DatabaseError(f"Query failed: {e}") from e
```

#### Алгоритм: Обработка транзакций

```python
async def execute_transaction(self, operations: list):
    """
    Выполнение нескольких операций в одной транзакции
    
    Args:
        operations: Список операций (query, args)
        
    Returns:
        Результаты выполнения операций
    """
    async with self.get_connection() as conn:
        async with conn.transaction():
            results = []
            for query, args in operations:
                result = await conn.fetch(query, *args)
                results.append(result)
            return results
```

#### Алгоритм: Миграции базы данных

```python
async def run_migrations(self, migrations_dir: str):
    """
    Применение миграций базы данных
    
    Args:
        migrations_dir: Директория с файлами миграций
    """
    # Получить список примененных миграций
    async with self.get_connection() as conn:
        applied = await conn.fetch(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        applied_versions = {r['version'] for r in applied}
    
    # Применить новые миграции
    for migration_file in sorted(os.listdir(migrations_dir)):
        version = migration_file.split('_')[0]
        if version not in applied_versions:
            async with self.get_connection() as conn:
                async with conn.transaction():
                    with open(os.path.join(migrations_dir, migration_file)) as f:
                        await conn.execute(f.read())
                    await conn.execute(
                        "INSERT INTO schema_migrations (version) VALUES ($1)",
                        version
                    )
```

---

### 1.3 Метрики качества

**Метрики для мониторинга PostgreSQL:**

1. **Производительность**
   - Query performance: p95 < 100ms, p99 < 500ms
   - Connection pool usage: < 80% (alerts при >90%)
   - Active connections: < 80% от max_connections
   - Cache hit ratio: > 95%

2. **Надежность**
   - Uptime: > 99.9%
   - Replication lag: < 1 секунда
   - Backup success rate: 100%
   - Restore time: < 30 минут для полного восстановления

3. **Качество**
   - Error rate: < 0.1%
   - Deadlocks: 0 (alerts при любом deadlock)
   - Long-running queries: < 5 запросов дольше 60 секунд
   - Index usage: > 90% для всех индексов

4. **Безопасность**
   - Failed login attempts: < 10 в день
   - SSL connections: 100% для production
   - Audit log coverage: 100% для всех операций с ПДн

---

## 2. Интеграция с платформой

### 2.1 Docker Compose

**Конфигурация PostgreSQL в docker-compose.yml:**

```yaml
services:
  postgres:
    image: postgres:15-alpine
    container_name: 1c-ai-postgres
    environment:
      POSTGRES_DB: knowledge_base
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d
    networks:
      - 1c-ai-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin"]
      interval: 10s
      timeout: 5s
      retries: 5
    command:
      - "postgres"
      - "-c"
      - "shared_buffers=256MB"
      - "-c"
      - "max_connections=100"
      - "-c"
      - "log_statement=all"
      - "-c"
      - "log_min_duration_statement=1000"
```

### 2.2 Connection String

**Формат connection string:**

```
postgresql://[user[:password]@][host][:port][/database][?param1=value1&...]
```

**Пример:**

```python
DATABASE_URL = "postgresql://admin:changeme@postgres:5432/knowledge_base?sslmode=require"
```

### 2.3 Схема базы данных

**Основные таблицы:**

1. **users** — пользователи платформы
2. **user_roles** — роли пользователей (RBAC)
3. **user_permissions** — права доступа
4. **configurations** — метаданные конфигураций 1С
5. **modules** — BSL модули
6. **functions** — функции и процедуры
7. **audit_logs** — логи аудита

---

## 3. Примеры использования

### Пример 1: Базовое использование

```python
from src.data.postgresql_client import PostgreSQLClient

client = PostgreSQLClient(
    connection_string="postgresql://admin:changeme@postgres:5432/knowledge_base",
    pool_size=10
)

await client.connect()

# Выполнение запроса
result = await client.execute_query(
    "SELECT * FROM configurations WHERE name = $1",
    "Бухгалтерия 3.0"
)

# Закрытие пула
await client.close()
```

### Пример 2: Транзакции

```python
# Выполнение нескольких операций в транзакции
operations = [
    ("INSERT INTO configurations (name, version) VALUES ($1, $2)", ("Бухгалтерия", "3.0.123")),
    ("INSERT INTO modules (configuration_id, name) VALUES ($1, $2)", (1, "ОбщийМодуль")),
]

results = await client.execute_transaction(operations)
```

### Пример 3: Миграции

```python
# Применение миграций
await client.run_migrations("db/migrations")

# Проверка версии схемы
version = await client.execute_query(
    "SELECT MAX(version) FROM schema_migrations"
)
```

---

## 4. Best Practices

### 4.1 Использование пула соединений

- Всегда используйте пул соединений вместо прямых подключений
- Настройте минимальный и максимальный размер пула в зависимости от нагрузки
- Мониторьте использование пула соединений

### 4.2 Индексы

- Создавайте индексы для всех внешних ключей
- Создавайте индексы для полей, используемых в WHERE и JOIN
- Регулярно анализируйте использование индексов (pg_stat_user_indexes)

### 4.3 Запросы

- Используйте параметризованные запросы для защиты от SQL injection
- Избегайте SELECT * в production
- Используйте LIMIT для больших выборок
- Оптимизируйте JOIN-запросы

### 4.4 Резервное копирование

- Настройте автоматическое ежедневное резервное копирование
- Храните резервные копии не менее 30 дней
- Тестируйте восстановление из резервных копий еженедельно
- Используйте WAL для point-in-time recovery

---

## 5. Соответствие уровням

### Level 1: Basic
- Базовая функциональность (SELECT, INSERT, UPDATE, DELETE)
- Базовое логирование ошибок
- Ручное резервное копирование

### Level 2: Enhanced
- + Пул соединений
- + Индексы на всех внешних ключах
- + Автоматическое резервное копирование
- + Мониторинг метрик

### Level 3: Full
- + Репликация для чтения
- + Партиционирование больших таблиц
- + Автоматическое восстановление
- + Полный мониторинг и алерты

---

## 6. Связанные стандарты

- [Neo4j Standard](NEO4J_SPEC.md) - граф метаданных
- [Redis Standard](REDIS_SPEC.md) - кэш и rate limiting
- [Data Migration Standard](DATA_MIGRATION_SPEC.md) - миграции данных
- [Data Backup Standard](DATA_BACKUP_SPEC.md) - резервное копирование

---

## 7. Чеклист соответствия

- [ ] Используется PostgreSQL 15+
- [ ] Настроен пул соединений (10-50 соединений)
- [ ] Включено шифрование (TLS 1.3)
- [ ] Настроено автоматическое резервное копирование
- [ ] Созданы индексы для всех внешних ключей
- [ ] Настроен мониторинг метрик (Prometheus)
- [ ] Реализовано логирование всех операций
- [ ] Тестирование восстановления из резервных копий

---

**Примечание:** Этот стандарт обеспечивает единообразие работы с PostgreSQL в платформе 1C AI Stack.
