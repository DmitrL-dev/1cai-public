# ⚡ SQL Optimizer & 1C Server Optimizer Guide

**Статус:** ✅ Production (ядро реализовано, тесты добавлены)  
**Файлы:** `src/ai/agents/sql_optimizer.py`, `src/ai/agents/onec_server_optimizer.py`, `src/ai/sql_optimizer_secure.py`

---

## 🎯 Назначение

SQL Optimizer решает две задачи:

- анализ и оптимизация запросов 1С/SQL (PostgreSQL, MS SQL);
- рекомендации по индексам и конфигурации сервера 1С.

Secure-обёртка (`SQLOptimizerSecure`) добавляет Rule-of-Two, аудит и approval‑флоу для опасных запросов.

---

## 🧠 Основные возможности

1. **Детекция anti‑patterns**  
   - `SELECT *`  
   - отсутствие `WHERE` при `JOIN`  
   - N+1 (запрос в цикле / `Для Каждого … Запрос`)  
   - отсутствие `LIMIT/TOP` для выборок  
   - `MULTIPLE_OR` вместо `IN`  
   - функции в `WHERE` (ломают индексы)  
   - implicit type conversion, `NOT IN` с `NULL`.

2. **Генерация оптимизаций**  
   - переписывание `SELECT *` в явный список колонок;  
   - рекомендации по добавлению фильтрации / LIMIT;  
   - предложения по переписыванию N+1 в batch‑запросы.

3. **Рекомендации по индексам и конфигурации**  
   - типы индексов (btree/hash/gin/gist) и `CREATE INDEX` statements;  
   - hints по настройке сервера БД и кластера 1С.

4. **Secure‑контур (`SQLOptimizerSecure`)**  
   - Rule-of-Two: `[A,B]` без автоматического изменения состояния;  
   - детекция SQL injection и блокировка опасных запросов;  
   - токены и approval‑флоу с audit‑логами.

---

## 🚀 Примеры использования

### 1. Оптимизация запроса (Architect MCP / внутренний сервис)

```python
from src.ai.agents.sql_optimizer import SQLOptimizer

optimizer = SQLOptimizer("postgresql")
query = "SELECT * FROM orders JOIN customers ON orders.customer_id = customers.id"

result = await optimizer.optimize_query(query, context={"database": "postgresql"})

print(result["optimized_query"])
print(result["index_recommendations"])
```

### 2. Secure-режим для production

```python
from src.ai.sql_optimizer_secure import SQLOptimizerSecure

secure = SQLOptimizerSecure()

draft = secure.optimize_query("SELECT * FROM users WHERE name = 'admin' OR '1'='1'")
if draft.get("blocked"):
    # SQL injection или небезопасный ввод
    raise ValueError(draft["error"])

# безопасный SELECT:
draft = secure.optimize_query("SELECT id, name FROM users WHERE active = true")
token = draft["token"]

result = secure.execute_approved_query(token, approved_by_user="dba_user")
```

---

## 🧪 Тестирование

Юнит‑тесты:

- `tests/unit/test_sql_optimizer.py` — детекция anti‑patterns и базовый `optimize_query`.  
- `tests/unit/test_sql_optimizer_secure.py` — SQL injection, токены, истечение, Rule-of-Two.

Запуск:

```bash
python -m pytest tests/unit/test_sql_optimizer.py tests/unit/test_sql_optimizer_secure.py -q
```

---

## 🔐 Безопасность

- Все входные запросы проходят через `AISecurityLayer` в secure‑режиме.  
- Опасные операции (`DROP`, `DELETE`, `UPDATE`, `ALTER`) требуют явного подтверждения (CONFIRM) и audit‑логируются.  
- Для интеграции с API используйте только secure‑вариант (`sql_optimizer_secure`) на production.

---

## 📚 Связанные материалы

- `docs/03-ai-agents/SQL_OPTIMIZER_COMPLETE.md` — подробное описание фич и источников best practices.  
- `docs/03-ai-agents/TECH_LOG_INTEGRATION_COMPLETE.md` — использование SQL Optimizer в TechLog‑потоке.  
- `tests/security/test_ai_security.py` — проверка Rule-of-Two и security‑слоя.


