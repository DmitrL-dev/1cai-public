# 🚀 Инструкции по развертыванию

## Enterprise 1C AI Development Stack v4.1

---

## 📋 Полный план развертывания

### Этап 0: Базовая инфраструктура ✅ ГОТОВО

```bash
# 1. Запустить базовые сервисы
docker-compose up -d

# Ожидается:
# ✓ postgres (PostgreSQL)
# ✓ redis (Redis)
# ✓ nginx (Nginx)
```

### Этап 1: Расширенная инфраструктура

```bash
# 2. Запустить Stage 1 сервисы
docker-compose -f docker-compose.yml -f docker-compose.stage1.yml up -d

# Добавляются:
# ✓ neo4j (Graph Database)
# ✓ qdrant (Vector Search)
# ✓ elasticsearch (Full-text Search)
# ✓ ollama (Local LLM)
# ✓ kibana (ES UI, dev only)
```

### Этап 2: Миграция данных

```bash
# 3. Установить дополнительные зависимости
pip install -r requirements-stage1.txt

# 4. Мигрировать JSON → PostgreSQL
python migrate_json_to_postgres.py

# 5. Мигрировать PostgreSQL → Neo4j
python migrate_postgres_to_neo4j.py

# 6. Векторизация в Qdrant
python migrate_to_qdrant.py
```

### Этап 3: Настройка AI моделей

```bash
# 7. Загрузить Qwen3-Coder в Ollama
docker-compose exec ollama ollama pull qwen2.5-coder:7b

# Опционально: более мощная модель
docker-compose exec ollama ollama pull qwen2.5-coder:32b

# 8. Проверить модель
docker-compose exec ollama ollama list
```

### Этап 4: Запуск API сервисов

```bash
# 9. Запустить Graph API
python -m uvicorn src.api.graph_api:app --host 0.0.0.0 --port 8080

# 10. Запустить MCP Server
python -m uvicorn src.ai.mcp_server:app --host 0.0.0.0 --port 6001
```

### Этап 5: Проверка работоспособности

#### Проверка сервисов:

```bash
# PostgreSQL
curl http://localhost:5050

# Neo4j
curl http://localhost:7474

# Qdrant
curl http://localhost:6333

# Elasticsearch
curl http://localhost:9200

# API Gateway
curl http://localhost:8080/health

# MCP Server
curl http://localhost:6001/mcp
```

#### Доступ к UI:

| Сервис | URL | Credentials |
|--------|-----|-------------|
| PgAdmin | http://localhost:5050 | admin@1c-ai.local / admin |
| Neo4j Browser | http://localhost:7474 | neo4j / (NEO4J_PASSWORD) |
| Kibana | http://localhost:5601 | - |
| Qdrant Dashboard | http://localhost:6333/dashboard | - |

---

## 📊 Проверочные запросы

### PostgreSQL (через PgAdmin):

```sql
-- Сводка
SELECT * FROM v_configuration_summary;

-- Топ сложные функции
SELECT * FROM v_complex_functions LIMIT 20;

-- Статистика
SELECT 
    COUNT(*) as total_modules,
    SUM(line_count) as total_lines
FROM modules;
```

### Neo4j (через Neo4j Browser):

```cypher
// Все конфигурации
MATCH (c:Configuration)
RETURN c.name, c.full_name;

// Граф одного документа
MATCH path = (c:Configuration)-[:HAS_OBJECT]->(o:Object {type: 'Документ'})
              -[:HAS_MODULE]->(m:Module)
WHERE c.name = 'DO'
RETURN path
LIMIT 10;

// Граф вызовов функции
MATCH path = (f:Function {name: 'РассчитатьНДС'})-[:CALLS*1..3]->(called)
RETURN path;

// Статистика
MATCH (c:Configuration)
OPTIONAL MATCH (c)-[:HAS_OBJECT]->(o:Object)
OPTIONAL MATCH (c)-[:HAS_MODULE]->(m:Module)
OPTIONAL MATCH (m)-[:DEFINES]->(f:Function)
RETURN 
    c.name,
    count(DISTINCT o) as objects,
    count(DISTINCT m) as modules,
    count(DISTINCT f) as functions;
```

### API Gateway:

```bash
# Получить все конфигурации
curl http://localhost:8080/api/graph/configurations

# Получить объекты DO
curl http://localhost:8080/api/graph/objects/DO

# Статистика
curl http://localhost:8080/api/stats/overview

# Семантический поиск (POST)
curl -X POST http://localhost:8080/api/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "расчет НДС", "limit": 10}'
```

### MCP Server (для Cursor):

```bash
# Список инструментов
curl http://localhost:6001/mcp/tools

# Вызов инструмента
curl -X POST http://localhost:6001/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "search_metadata",
    "arguments": {
      "query": "Найди все документы",
      "configuration": "DO"
    }
  }'
```

---

## ⚙️ Конфигурация Cursor для MCP

### Файл: `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "1c-ai-assistant": {
      "url": "http://localhost:6001/mcp",
      "connection_id": "1c_ai_service_001",
      "alwaysAllow": [
        "search_metadata",
        "search_code_semantic",
        "generate_bsl_code",
        "analyze_dependencies"
      ],
      "type": "streamable-http",
      "timeout": 300
    }
  }
}
```

---

## 🔧 Настройка EDT Plugin

### Установка (в разработке):

1. **Сборка плагина:**
```bash
cd edt-plugin
mvn clean package
```

2. **Установка в EDT:**
- Help → Install New Software
- Add → Local → выбрать `edt-plugin/target/repository`
- Выбрать "1C AI Assistant"
- Next → Finish → Restart EDT

3. **Настройка подключения:**
- Window → Preferences → 1C AI Assistant → Connection Settings
- MCP Server URL: http://localhost:6001
- Test Connection
- Apply and Close

---

## 📦 Полный Docker Compose

### Объединенный запуск всех сервисов:

```bash
# Запустить все сразу
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.stage1.yml \
  up -d

# Проверить статус
docker-compose ps

# Логи всех сервисов
docker-compose logs -f

# Логи конкретного сервиса
docker-compose logs -f neo4j
```

---

## 🎯 Порядок запуска

### Правильная последовательность:

1. **Базовые сервисы**
   ```bash
   docker-compose up -d postgres redis nginx
   sleep 30  # Подождать инициализации
   ```

2. **Stage 1 сервисы**
   ```bash
   docker-compose -f docker-compose.stage1.yml up -d neo4j qdrant elasticsearch
   sleep 60  # Особенно Elasticsearch медленно стартует
   ```

3. **AI сервисы**
   ```bash
   docker-compose -f docker-compose.stage1.yml up -d ollama
   sleep 30
   docker-compose exec ollama ollama pull qwen2.5-coder:7b
   ```

4. **Миграция данных**
   ```bash
   python migrate_json_to_postgres.py
   python migrate_postgres_to_neo4j.py
   python migrate_to_qdrant.py
   ```

5. **API сервисы**
   ```bash
   # Terminal 1: Graph API
   python -m uvicorn src.api.graph_api:app --port 8080

   # Terminal 2: MCP Server
   python -m uvicorn src.ai.mcp_server:app --port 6001
   ```

---

## 🐛 Troubleshooting

### Сервис не стартует

```bash
# Проверить логи
docker-compose logs [service_name]

# Проверить health
docker-compose ps

# Рестарт сервиса
docker-compose restart [service_name]
```

### Нехватка памяти

```bash
# Увеличить лимиты Docker Desktop
# Settings → Resources → Memory: 8GB minimum

# Или уменьшить сервисы:
# Не запускать Elasticsearch (большой)
# Использовать меньшую модель Qwen
```

### Порты заняты

```bash
# Найти процесс на порту
netstat -ano | findstr :7474

# Убить процесс или изменить порт в docker-compose.yml
```

---

## ✅ Success Checklist

Перед началом работы проверьте:

- [ ] Docker Desktop запущен и работает
- [ ] .env файл настроен (все пароли установлены)
- [ ] PostgreSQL доступна (PgAdmin работает)
- [ ] Neo4j доступен (Browser работает)
- [ ] Qdrant доступен (Dashboard работает)
- [ ] Ollama загрузил модель qwen2.5-coder
- [ ] API отвечает на /health
- [ ] MCP Server отвечает на /mcp
- [ ] Данные мигрированы во все БД

---

## 📞 Помощь

**Если что-то не работает:**

1. Проверьте Docker: `docker-compose ps`
2. Проверьте логи: `docker-compose logs -f [service]`
3. Проверьте .env файл
4. Проверьте сеть: `docker network ls`
5. Перезапустите все: `docker-compose down && docker-compose up -d`

**Полный сброс (если совсем не работает):**

```bash
# ⚠️ ВНИМАНИЕ: Удалит ВСЕ данные!
docker-compose down -v
docker-compose -f docker-compose.stage1.yml down -v

# Заново запустить
docker-compose up -d
docker-compose -f docker-compose.stage1.yml up -d
```

---

**Готово! Следуйте этим инструкциям для развертывания! 🚀**





