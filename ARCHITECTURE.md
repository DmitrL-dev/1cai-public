# Архитектура 1C AI Platform v5.0

## Принципы

1. **Только живой код** — никаких заглушек, фантомов и мёртвых модулей
2. **Clean Architecture** — domain → application → infrastructure → api
3. **Честный README** — документируем только то, что реально работает
4. **Три пайплайна** — BSL Analysis, Code Generation, AI Orchestration

## Целевая структура

```
src/
├── main.py                          # Точка входа FastAPI
├── config.py                        # Конфигурация
├── app/                             # Application Factory
│   ├── factory.py                   # create_app()
│   ├── routers.py                   # Регистрация роутеров
│   ├── middleware.py                # Middleware chain
│   └── lifespan.py                  # Startup/shutdown
│
├── core/                            # Ядро платформы (без внешних зависимостей)
│   ├── bsl/                         # BSL-специфичная логика
│   │   ├── parser.py                # BSL парсер (regex-based)
│   │   ├── analyzer.py              # Анализ качества кода
│   │   └── patterns.py              # Паттерны и антипаттерны 1С
│   ├── agents/                      # AI-агенты (домен)
│   │   ├── base.py                  # BaseAgent ABC
│   │   ├── registry.py              # Реестр агентов
│   │   ├── developer.py             # Разработчик
│   │   ├── architect.py             # Архитектор
│   │   ├── security.py              # Безопасность
│   │   ├── qa.py                    # Тестирование
│   │   ├── reviewer.py              # Code Review
│   │   └── analyst.py               # Бизнес-аналитик
│   └── domain/                      # Доменные модели
│       ├── models.py                # Базовые модели
│       └── events.py                # Доменные события
│
├── micro_swarm/                     # Zero-dep ML движок (ЖИВОЙ, НЕ ТРОГАТЬ)
│   ├── engine.py                    # Autograd
│   ├── model.py                     # MicroModel
│   ├── domains.py                   # 3 базовых домена
│   ├── bsl_domains.py               # 5 BSL доменов
│   ├── router.py                    # SwarmRouter (CLEAN/TEMPLATE/LLM)
│   ├── go_bridge.py                 # Python↔Go мост
│   └── cli.py                       # bsl-review CLI
│
├── services/                        # Прикладные сервисы
│   ├── llm_gateway.py               # Multi-LLM шлюз
│   ├── llm_health_monitor.py        # Мониторинг LLM
│   ├── embedding_service.py         # Векторные эмбеддинги
│   ├── health_checker.py            # Health checks
│   ├── code_generation.py           # Генерация кода 1С
│   ├── code_review.py               # AI Code Review
│   └── documentation.py             # Генерация документации
│
├── integrations/                    # Внешние интеграции
│   ├── onec/                        # 1С интеграция
│   │   ├── odata_client.py          # OData API
│   │   └── ras_client.py            # RAS (Remote Admin)
│   ├── llm/                         # LLM провайдеры
│   │   ├── openai_client.py
│   │   ├── gigachat_client.py
│   │   ├── yandexgpt_client.py
│   │   ├── ollama_client.py
│   │   └── kimi_client.py
│   ├── git/                         # Git интеграция
│   │   └── github_client.py
│   └── mcp/                         # MCP Server
│       ├── server.py                # MCP протокол
│       ├── architect.py             # Архитектурные инструменты
│       └── multi_role.py            # Multi-role tools
│
├── infrastructure/                  # Инфраструктура
│   ├── db/                          # БД клиенты
│   │   ├── postgres.py
│   │   ├── neo4j.py
│   │   └── qdrant.py
│   ├── events/                      # Event Bus
│   │   └── nats_bus.py
│   ├── auth/                        # Аутентификация
│   │   ├── jwt.py
│   │   ├── oauth2.py
│   │   └── rbac.py
│   ├── monitoring/                  # Метрики
│   │   └── prometheus.py
│   └── logging/                     # Логирование
│       └── structured.py
│
├── api/                             # HTTP API слой
│   ├── v1/                          # API v1
│   │   ├── orchestrator.py          # AI оркестратор
│   │   ├── code_review.py           # Code Review
│   │   ├── agents.py                # Управление агентами
│   │   ├── analytics.py             # Аналитика
│   │   ├── health.py                # Health/Monitoring
│   │   └── wiki.py                  # Wiki
│   └── middleware/                   # HTTP middleware
│       ├── auth.py
│       ├── rate_limit.py
│       └── logging.py
│
├── telegram/                        # Telegram бот
│   ├── bot.py
│   ├── handlers.py
│   └── formatters.py
│
└── parsers/                         # Парсеры
    └── onec_xml_parser.py           # XML метаданных 1С

go/                                  # Go BSL Scanner
├── cmd/bsl-scan/main.go
├── internal/extractor/
└── internal/scanner/

1c_mcp/                              # MCP Server + 1C Extension
├── src/py_server/                   # Python MCP сервер
└── src/1c_ext/                      # Расширение 1С (BSL)

1c_mcp_code_generation/              # Генерация кода 1С
├── src/py_server/code_generation/
└── templates/
```

## Три пайплайна

### 1. BSL Analysis Pipeline
```
.bsl файл → Go Scanner (параллельный) → Feature JSON →
→ MicroSwarm (8 доменов ML) → SwarmRouter →
→ CLEAN (мгновенный ответ) / TEMPLATE (шаблон) / LLM_REQUIRED (AI)
```
**Статус: РАБОТАЕТ** — CLI `bsl-review`, 78 тестов

### 2. Code Generation Pipeline
```
Запрос → Query Classifier → Agent Selection →
→ LLM Gateway (multi-provider) → BSL Template + LLM →
→ Code Validation → Output
```
**Статус: ЧАСТИЧНО** — LLM Gateway работает, шаблоны есть, нет единого пайплайна

### 3. AI Orchestration Pipeline
```
Запрос → Orchestrator → Role-Based Router →
→ Agent (Developer/Architect/Security/QA/BA) →
→ Memory (context) → LLM Strategy → Response
```
**Статус: РАБОТАЕТ** — через orchestrator_api, MCP, Telegram

## Что реально работает (аудит Phase 7)

### ЖИВОЕ ядро
- **micro_swarm/** — zero-dep ML, 8 доменов, SwarmRouter, Go bridge
- **ai/orchestrator.py** — центральный хаб
- **ai/agents/** — 16 живых агентов
- **ai/clients/** — 6 LLM клиентов (все живые)
- **ai/mcp/** — MCP сервер (3 файла, production)
- **ai/strategies/** — 6 живых стратегий
- **ai/memory/** — Memory manager
- **services/** — 20+ живых сервисов
- **modules/** — 27 живых модулей с роутерами

### УДАЛЕНО (Phase 7)
- 8 мёртвых модулей из src/modules/ (~8K LOC)
- 35 мёртвых AI файлов (~8K LOC)
- Фантомные импорты починены (12 шт)
- Сломанный security_monitoring починен

## Технологический стек

| Компонент | Технология | Статус |
|-----------|-----------|--------|
| Backend | Python 3.11 + FastAPI | ✅ |
| ML Engine | MicroSwarm (zero-dep) | ✅ |
| BSL Scanner | Go 1.25 (goroutines) | ✅ |
| LLM | OpenAI, GigaChat, YandexGPT, Ollama, Kimi | ✅ |
| Database | PostgreSQL 17 + pgvector | ✅ |
| Graph DB | Neo4j | ✅ |
| Vector DB | Qdrant | ✅ |
| Events | NATS JetStream | ✅ |
| Auth | Keycloak + JWT | ✅ |
| MCP | Custom Python server | ✅ |
| IDE | VS Code Extension + Cursor | ✅ |
| Bot | Telegram (aiogram) | ✅ |
| CI/CD | GitHub Actions | ✅ |
