# MCP Server Guide

> Обновлено: 19 ноября 2025

## 1. Обзор

MCP сервер (`src/ai/mcp_server.py`) реализует Model Context Protocol для IDE (Cursor, VS Code, расширения EDT). Он предоставляет единый HTTP-интерфейс с набором инструментов (tools), которые вызывают AI-оркестратор, хранилища данных (Neo4j, Qdrant) и внешние MCP-сервисы.

Основные возможности:
- каталог инструментов (`/mcp/tools`) с описанными схемами аргументов;
- маршрутизация вызовов на AI Orchestrator и внешние MCP;
- работа через FastAPI + Uvicorn (порт 6001 по умолчанию);
- поддержка IDE-плагинов через стандарт MCP.

### 🔍 Интеграция внешних MCP серверов

Проект поддерживает интеграцию с внешними MCP серверами через прокси-слой. Проведён анализ применимости популярных MCP серверов:

- **📚 [Анализ применимости MCP серверов](../research/MCP_SERVERS_APPLICABILITY_ANALYSIS.md)** — детальный анализ 5 популярных MCP серверов (Context7, Exa, GitHub, Chroma, Atlassian) с рекомендациями по интеграции.

**Рекомендуемые для интеграции:**
- 🟢 **MCP Atlassian** — очень высокая применимость (упростит Business Analyst Agent)
- 🟢 **Context7** — высокая применимость (актуальная документация библиотек)
- 🟢 **GitHub MCP** — высокая применимость (автоматизация GitHub операций)

## 2. Требования и окружение

| Компонент | Версия/Комментарий |
|-----------|--------------------|
| Python | 3.11.x (строгая проверка в `src/main.py`) |
| FastAPI + Uvicorn | Устанавливаются через `requirements.txt` |
| Graph API | Нужен для инструментов, работающих с Neo4j/Qdrant |
| Docker Compose | Для поднятия инфраструктуры (`make docker-up`) |
| Конфигурация в `.env` | Ключи OpenAI, Supabase, БД, Redis, внешние MCP |

## 3. Запуск сервиса

### Через Makefile (предпочтительно)
```bash
make docker-up     # базы данных и вспомогательные сервисы
make migrate       # миграции и подготовка данных
make servers       # старт Graph API (8080) и MCP сервера (6001)
```

### Альтернатива (PowerShell / без make)
```powershell
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080   # Graph API
python -m src.ai.mcp_server --host 0.0.0.0 --port 6001       # MCP сервер
```
> Проверьте, что в `.env` заданы все обязательные переменные (OpenAI, Supabase, БД).

## 4. Подключение из IDE

1. Убедитесь, что `http://localhost:6001/mcp` возвращает JSON c информацией о сервере.
2. В Cursor/VS Code добавьте MCP endpoint:
   - URL: `http://localhost:6001/mcp`
   - Имя: `1C AI Stack`
3. Для плагина EDT используйте ту же конечную точку; убедитесь, что Graph API (8080) и MCP (6001) доступны из среды EDT.
4. При первом подключении IDE запросит список инструментов — убедитесь, что `/mcp/tools` отвечает списком (см. таблицу ниже).

## 5. Инструменты MCP

| Название | Описание | Аргументы |
|----------|----------|-----------|
| `search_metadata` | Поиск объектов метаданных 1С через Neo4j граф. | `query` (обяз.), `configuration`, `object_type` |
| `search_code_semantic` | Семантический поиск по коду (Qdrant). | `query` (обяз.), `configuration`, `limit` |
| `generate_bsl_code` | Генерация BSL кода (Qwen3-Coder). | `description` (обяз.), `function_name`, `parameters`, `context` |
| `analyze_dependencies` | Анализ зависимостей функций/модулей. | `module_name` (обяз.), `function_name` (обяз.) |
| `bsl_platform_context` | Прокси к внешнему MCP alkoleft/mcp-bsl-platform-context. | `query` (обяз.), `scope` |
| `bsl_test_runner` | Прокси к внешнему MCP alkoleft/mcp-onec-test-runner. | `workspace` (обяз.), `testPlan`, `arguments` |

Каждый инструмент вызывает `AIOrchestrator.process_query`, передавая тип запроса и контекст.

## 6. Внешние MCP и переменные окружения

| Переменная | Назначение | Пример |
|------------|------------|--------|
| `MCP_BSL_CONTEXT_BASE_URL` | Базовый URL сервера платформенного контекста. | `http://localhost:7001` |
| `MCP_BSL_CONTEXT_TOOL_NAME` | Имя инструмента на внешнем сервере. | `platform_context` |
| `MCP_BSL_CONTEXT_AUTH_TOKEN` | Bearer-токен (если требуется). | `Bearer ...` |
| `MCP_BSL_TEST_RUNNER_BASE_URL` | Базовый URL тест-раннера. | `http://localhost:7002` |
| `MCP_BSL_TEST_RUNNER_TOOL_NAME` | Имя инструмента на тест-раннере. | `run_tests` |
| `MCP_BSL_TEST_RUNNER_AUTH_TOKEN` | Токен доступа (опционально). | `Bearer ...` |

Если переменная не задана, соответствующий инструмент вернёт ошибку `configured=False`.

## 7. Логи и мониторинг

- Все сервисы пишут логи в директорию, заданную `log_dir` (`./logs` по умолчанию).
- MCP сервер использует стандартный `logging`; на прод окружении настройте ротацию файлов и централизованный сбор.
- Для диагностики вызовов смотрите уровень INFO в `src/ai/mcp_server.py` (`MCP tool called: ...`).

## 8. Troubleshooting

| Симптом | Возможная причина | Решение |
|---------|-------------------|---------|
| `Connection refused` при обращении к `/mcp` | MCP сервер не запущен / порт занят | Перезапустите `make servers` или `python -m src.ai.mcp_server`, проверьте фаервол |
| `Tool not found` в ответе | IDE отправила некорректное имя | Обновите список инструментов (`/mcp/tools`), проверьте конфигурацию IDE |
| Ошибка `configured=False` | Внешний MCP не настроен | Запустите соответствующий сервис (см. README) и задайте URL/токен |
| 5xx при вызове инструмента | Ошибка оркестратора или внешнего сервиса | Проверьте логи Graph API / внешних MCP, убедитесь в доступности Neo4j и Qdrant |

## 9. Безопасность и правила

- Публикуя эндпоинт, убедитесь в настройке CORS и rate limiting (см. `src/security`, правила из `docs/research/constitution.md`).
- Не храните токены и секреты в репозитории; используйте `.env` (см. `.gitignore`).
- Для прод окружения настройте авторизацию (JWT) и HTTPS-передачу.

## 10. Благодарности

- [alkoleft/mcp-bsl-platform-context](https://github.com/alkoleft/mcp-bsl-platform-context) — внешний MCP для платформенного контекста.
- [alkoleft/mcp-onec-test-runner](https://github.com/alkoleft/mcp-onec-test-runner) — MCP для запуска тестов.
- Сообщество MCP и GitHub Spec Kit — за примеры спецификаций и автоматизации.
