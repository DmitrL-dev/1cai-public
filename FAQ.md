# ❓ FAQ - Frequently Asked Questions

**Последнее обновление:** 7 ноября 2025

---

## 🚀 Начало работы

### Q: Как быстро запустить проект?

**A:** Самый простой способ - Telegram Bot (5 минут):

```bash
# 1. Установить зависимости
pip install -r requirements-telegram.txt

# 2. Создать .env
cp env.example .env

# 3. Добавить токен бота
echo "TELEGRAM_BOT_TOKEN=your_token" >> .env

# 4. Запустить
docker-compose up -d postgres redis
python src/telegram/bot_minimal.py
```

См. подробнее: [Quick Start Guide](QUICK_START.md)

---

### Q: Как получить JWT токен для API?

**A:**

```bash
# Запросить токен (демо-учётки задаются через AUTH_DEMO_USERS)
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=<your_username>&password=<your_password>"

# Использовать токен
curl http://localhost:8000/marketplace/plugins \
  -H "Authorization: Bearer <your_token>"
```

В production обязательно задайте собственный `JWT_SECRET`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` и переопределите `AUTH_DEMO_USERS`.

---

## 🛡️ Marketplace & Security

### Q: Как изменить лимиты запросов к Marketplace и REST API?

**A:** Используйте переменные окружения в `.env`:

```bash
USER_RATE_LIMIT_PER_MINUTE=120      # Количество запросов на пользователя в минуту
USER_RATE_LIMIT_WINDOW_SECONDS=60   # Размер окна (секунды)
MARKETPLACE_CACHE_REFRESH_MINUTES=5 # Как часто пересчитывать кэш витрин
```

После изменения перезапустите backend (`uvicorn`, `docker-compose` или systemd-сервис).

### Q: Как включить скачивание плагинов через S3/MinIO?

**A:** Укажите параметры хранилища в `.env`:

```bash
AWS_S3_BUCKET=onecai-marketplace
AWS_S3_REGION=ru-1
AWS_S3_ENDPOINT=https://s3.selectel.ru  # для MinIO/Selectel
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

При наличии `artifact_path` в карточке плагина API вернёт подписанную ссылку (TTL 5 минут). Без этих переменных останется fallback-URL.

---

### Q: Какие минимальные требования?

**A:** 
- **Python:** 3.11.x (рекомендуем 3.11.9)
- **RAM:** 2-4 GB (MVP) или 8-12 GB (full stack)
- **Docker:** 20.10+ (опционально, но рекомендуется)
- **OS:** Windows, Linux, macOS

---

### Q: Нужно ли устанавливать все 5 баз данных?

**A:** **НЕТ!** Для MVP достаточно 2:
- ✅ PostgreSQL (обязательно)
- ✅ Redis (обязательно)

Остальные опциональны:
- 🟡 Neo4j (для графа зависимостей)
- 🟡 Qdrant (для семантического поиска)
- ❌ Elasticsearch (не нужен, PostgreSQL FTS достаточно)

См.: [Что реально работает](docs/02-architecture/PROJECT_SUMMARY.md)

---

## 🔧 Проблемы и решения

### Q: Ошибка "ModuleNotFoundError"

**A:** Установите зависимости:
```bash
pip install -r requirements.txt
```

Для Telegram бота:
```bash
pip install -r requirements-telegram.txt
```

---

### Q: Docker контейнеры не запускаются

**A:** Проверьте:
```bash
# 1. Docker запущен?
docker ps

# 2. Порты свободны?
netstat -an | findstr "5432 6379"

# 3. Логи контейнеров
docker-compose logs postgres redis
```

---

### Q: Telegram бот не отвечает

**A:** Проверьте:
1. **Токен корректный?**
   ```bash
   cat .env | grep TELEGRAM_BOT_TOKEN
   ```

2. **База данных запущена?**
   ```bash
   docker ps | grep postgres
   ```

3. **Логи бота:**
   ```bash
   # В консоли где запущен бот
   # Должно быть "Bot started successfully"
   ```

---

### Q: Ошибка "Connection refused" при подключении к PostgreSQL

**A:** 
```bash
# Проверьте что PostgreSQL запущен
docker-compose ps postgres

# Если не запущен - запустите
docker-compose up -d postgres

# Проверьте логи
docker-compose logs postgres
```

---

## 🤖 AI и модели

### Q: Нужен ли OpenAI API ключ?

**A:** **НЕТ**, опционально:
- ✅ **Без OpenAI:** Используйте локальные модели (Ollama + Qwen)
- 🟡 **С OpenAI:** Расширенные функции (GPT-4, Whisper STT)

---

### Q: Как использовать локальные LLM модели?

**A:** Через Ollama:
```bash
# 1. Запустить Ollama
docker-compose up -d ollama

# 2. Загрузить модель
docker exec -it 1c-ai-ollama ollama pull qwen2.5-coder:7b

# 3. Проверить
curl http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5-coder:7b","prompt":"Hello"}'
```

---

### Q: Какие AI агенты доступны?

**A:** 8 специализированных агентов:
1. **AI Architect** - архитектурный анализ
2. **Developer Agent** - генерация кода
3. **QA Engineer** - генерация тестов
4. **DevOps Agent** - CI/CD оптимизация
5. **Business Analyst** - анализ требований
6. **SQL Optimizer** - оптимизация запросов
7. **Tech Log Analyzer** - анализ логов
8. **Security Scanner** - поиск уязвимостей

См.: [docs/03-ai-agents/](docs/03-ai-agents/)

---

## 🔌 Интеграции

### Q: Как подключить Cursor/VSCode?

**A:** Через MCP Server:

1. Запустите MCP Server:
   ```bash
   python src/ai/mcp_server.py
   ```

2. Настройте в Cursor (Settings → MCP Servers):
   ```json
   {
     "mcpServers": {
       "1c-ai": {
         "command": "python",
         "args": ["src/ai/mcp_server.py"]
       }
     }
   }
   ```

---

### Q: Как работает с 1C:EDT?

**A:** Через EDT Plugin (Beta 95%):
1. Скомпилируйте плагин:
   ```bash
   cd edt-plugin
   mvn clean package
   ```

2. Установите в EDT:
   - Help → Install New Software
   - Add → Archive → выберите .jar файл

См.: [docs/05-development/edt-plugin/](docs/05-development/edt-plugin/)

---

## 📦 Deployment

### Q: Как развернуть в production?

**A:** Через Kubernetes:
```bash
# 1. Настроить k8s конфиги
cd k8s/

# 2. Применить
kubectl apply -f namespace.yaml
kubectl apply -f deployments/
kubectl apply -f ingress.yaml
```

См.: [docs/01-getting-started/DEPLOYMENT_INSTRUCTIONS.md](docs/01-getting-started/DEPLOYMENT_INSTRUCTIONS.md)

---

### Q: Можно ли запустить без Docker?

**A:** **ДА**, но сложнее:
```bash
# 1. Установить PostgreSQL и Redis вручную

# 2. Настроить .env
DATABASE_URL=postgresql://user:pass@localhost:5432/db
REDIS_HOST=localhost

# 3. Запустить
python src/telegram/bot_minimal.py
```

---

## 🔐 Безопасность

### Q: Безопасно ли хранить API ключи в .env?

**A:** **ДА**, но:
- ✅ .env добавлен в .gitignore
- ✅ НЕ коммитьте .env в git
- ✅ Для production используйте секреты (Kubernetes Secrets, AWS Secrets Manager)

---

### Q: Как защитить Telegram бота от злоупотребления?

**A:** Встроенный Rate Limiting:
```python
# В .env
TELEGRAM_RATE_LIMIT_MIN=10   # 10 запросов/минуту
TELEGRAM_RATE_LIMIT_DAY=100  # 100 запросов/день

# Premium пользователи (больше лимиты)
TELEGRAM_PREMIUM_IDS=123456,789012
```

---

## 🌍 Локализация

### Q: Поддерживается ли английский язык?

**A:** **ДА!**
- Telegram бот: автоопределение языка
- Переключение: `/lang en` или `/lang ru`
- Документация: частично на EN

---

## 📊 Мониторинг

### Q: Как мониторить систему?

**A:** Через Prometheus + Grafana (опционально):
```bash
# Запустить monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# Доступ:
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000
```

См.: [monitoring/](monitoring/)

---

## 💰 Стоимость

### Q: Сколько стоит использование OpenAI API?

**A:** Зависит от использования:
- **GPT-4:** ~$0.03/1K tokens
- **Whisper STT:** ~$0.006/минута аудио
- **Embeddings:** ~$0.0001/1K tokens

**Альтернатива:** Используйте локальные модели (бесплатно)

---

### Q: Проект бесплатный?

**A:** **ДА!**
- ✅ MIT License - полностью бесплатный
- ✅ Все зависимости Open Source
- 🟡 API ключи (OpenAI) - опциональны и платные

---

## 🤝 Сообщество

### Q: Где сообщить о проблеме?

**A:** 
- 🐛 **GitHub Issues:** https://github.com/DmitrL-dev/1cai-public/issues
- 💬 **Discussions:** https://github.com/DmitrL-dev/1cai-public/discussions

---

### Q: Как внести вклад?

**A:** См. [CONTRIBUTING.md](CONTRIBUTING.md)

Кратко:
1. Fork проекта
2. Создайте feature branch
3. Commit изменения
4. Откройте Pull Request

---

## 📚 Дополнительные вопросы

### Q: Где полная документация?

**A:**
- 📖 **Main docs:** [docs/README.md](docs/README.md)
- 📗 **Getting Started:** [docs/01-getting-started/](docs/01-getting-started/)
- 🏗️ **Architecture:** [docs/02-architecture/](docs/02-architecture/)
- 🤖 **AI Agents:** [docs/03-ai-agents/](docs/03-ai-agents/)

---

### Q: Не нашли ответ?

**A:** Создайте issue: https://github.com/DmitrL-dev/1cai-public/issues/new

---

**Обновлено:** 6 ноября 2025  
**Следующее обновление:** По мере поступления вопросов

---

### Q: Как интегрировать внутренний сервис без OAuth?

**A:** Используйте заголовок `X-Service-Token`:

1. В `.env` задайте JSON в `SERVICE_API_TOKENS`:
   ```bash
   SERVICE_API_TOKENS=[{"name":"analytics","token":"secret","roles":["service"],"permissions":["marketplace:read"]}]
   ```
2. Перезапустите backend.
3. В запросе передайте `X-Service-Token: secret`.

> Убедитесь, что токены хранятся в Vault/Secrets Manager и не попадают в репозиторий.

---

