# 🔄 Миграция данных из JSON в PostgreSQL

## Быстрый старт

### 1. Убедитесь что Docker запущен

```bash
docker-compose ps
```

Должны работать: postgres, redis, nginx

Если нет:
```bash
docker-compose up -d
```

### 2. Убедитесь что .env настроен

```bash
# Проверьте что файл .env существует
type .env

# Если нет, создайте из шаблона
copy env.example .env

# Отредактируйте .env и установите POSTGRES_PASSWORD
notepad .env
```

### 3. Активируйте виртуальное окружение

```bash
# Если еще не создано
python -m venv venv

# Активировать
venv\Scripts\activate

# Установить зависимости если еще не установлены
pip install -r requirements.txt
```

### 4. Запустите миграцию

```bash
python migrate_json_to_postgres.py
```

---

## Что произойдет

Скрипт:
1. ✅ Подключится к PostgreSQL
2. ✅ Найдет все .json файлы в knowledge_base/
3. ✅ Для каждой конфигурации:
   - Создаст запись в таблице `configurations`
   - Создаст объекты в таблице `objects`
   - Создаст модули в таблице `modules`
   - Создаст функции в таблице `functions`
   - Сохранит API usage, regions
4. ✅ Покажет статистику миграции
5. ✅ Проверит данные в БД

---

## Пример вывода

```
============================================================
JSON to PostgreSQL Migration
Enterprise 1C AI Development Stack
============================================================
✓ Connected to PostgreSQL

Found 4 configuration(s):
  - do.json
  - erp.json
  - zup.json
  - buh.json

============================================================
Migrating: do
============================================================
✓ Created configuration: DO (ID: uuid...)
  Migrating 145 modules...
  Progress: 10/145 modules...
  Progress: 20/145 modules...
  ...
✓ Completed: do
  Modules: 145

============================================================
MIGRATION STATISTICS
============================================================
Configurations migrated: 4
Modules migrated:        542
Functions migrated:      3,847
Errors:                  0
============================================================

============================================================
VERIFICATION
============================================================
Database contains:
  Configurations: 4
  Objects:        89
  Modules:        542
  Functions:      3,847
  Total lines:    125,483

✓ Migration successful! Numbers match.

============================================================
✓ MIGRATION COMPLETED SUCCESSFULLY!
============================================================

Next steps:
1. Open PgAdmin: http://localhost:5050
2. Connect to database 'knowledge_base'
3. Run query: SELECT * FROM v_configuration_summary;
```

---

## Проверка результатов

### 1. Через PgAdmin

```
URL: http://localhost:5050
Login: admin@1c-ai.local / admin

Add Server:
  Name: Local PostgreSQL
  Host: postgres
  Port: 5432
  Database: knowledge_base
  Username: admin
  Password: (из .env файла)
```

### 2. SQL запросы для проверки

```sql
-- Сводка по конфигурациям
SELECT * FROM v_configuration_summary;

-- Список всех модулей
SELECT 
    c.name as config,
    o.name as object,
    m.module_type,
    m.line_count
FROM modules m
JOIN configurations c ON c.id = m.configuration_id
LEFT JOIN objects o ON o.id = m.object_id
ORDER BY m.line_count DESC
LIMIT 20;

-- Самые сложные функции
SELECT * FROM v_complex_functions LIMIT 20;

-- Топ используемых API
SELECT * FROM v_top_api_usage LIMIT 20;

-- Общая статистика
SELECT 
    COUNT(DISTINCT c.id) as configs,
    COUNT(DISTINCT o.id) as objects,
    COUNT(DISTINCT m.id) as modules,
    COUNT(DISTINCT f.id) as functions,
    SUM(m.line_count) as total_lines
FROM configurations c
LEFT JOIN objects o ON o.id = c.configuration_id
LEFT JOIN modules m ON m.configuration_id = c.id
LEFT JOIN functions f ON f.module_id = m.id;
```

---

## Troubleshooting

### Ошибка: Cannot connect to PostgreSQL

**Решение:**
```bash
# Проверить что Docker запущен
docker-compose ps

# Если postgres не запущен
docker-compose up -d postgres

# Подождать 30 секунд
timeout /t 30

# Попробовать снова
python migrate_json_to_postgres.py
```

### Ошибка: PostgreSQLSaver not found

**Решение:**
```bash
# Убедитесь что файл существует
dir src\db\postgres_saver.py

# Убедитесь что __init__.py существуют
dir src\__init__.py
dir src\db\__init__.py

# Если нет, что-то пошло не так при создании файлов
```

### Ошибка: psycopg2 module not found

**Решение:**
```bash
# Активировать venv
venv\Scripts\activate

# Установить psycopg2
pip install psycopg2-binary

# Попробовать снова
python migrate_json_to_postgres.py
```

### Ошибка: POSTGRES_PASSWORD not set

**Решение:**
```bash
# Проверить .env файл
type .env

# Убедиться что есть строка:
# POSTGRES_PASSWORD=ваш_пароль

# Если нет, добавить
echo POSTGRES_PASSWORD=yourpassword >> .env
```

---

## После миграции

### Что делать дальше:

1. ✅ **Проверить данные в PgAdmin**
   - Открыть http://localhost:5050
   - Посмотреть таблицы
   - Запустить примеры SQL

2. ✅ **Обновить TODO**
   - Миграция завершена ✓
   - Stage 0 завершен ✓
   - Готов к Stage 1

3. ✅ **Перейти к Stage 1**
   - Настроить Neo4j
   - Настроить Qdrant
   - Мигрировать данные в граф

---

## Повторная миграция

Если нужно перемигрировать данные:

```bash
# Вариант 1: Очистить все данные
# ВНИМАНИЕ: Удалит ВСЕ данные!
docker-compose down -v
docker-compose up -d
timeout /t 30
python migrate_json_to_postgres.py

# Вариант 2: Очистить только одну конфигурацию (SQL)
# В PgAdmin выполнить:
DELETE FROM configurations WHERE name = 'DO';
# Потом снова запустить миграцию
```

---

## Бэкап данных

### Создать бэкап после миграции:

```bash
# Создать дамп базы
docker-compose exec postgres pg_dump -U admin knowledge_base > backup_after_migration.sql

# Дата в имени файла
docker-compose exec postgres pg_dump -U admin knowledge_base > backup_%date:~-4,4%%date:~-7,2%%date:~-10,2%.sql
```

### Восстановить из бэкапа:

```bash
docker-compose exec -T postgres psql -U admin knowledge_base < backup_after_migration.sql
```

---

## Успех!

После успешной миграции у вас будет:
- ✅ Все конфигурации в PostgreSQL
- ✅ Полная структура метаданных
- ✅ Все функции и процедуры
- ✅ API usage tracking
- ✅ Готово для Neo4j миграции (Stage 1)

**Stage 0 ЗАВЕРШЕН! 🎉**

Next: See IMPLEMENTATION_PLAN.md → Stage 1





