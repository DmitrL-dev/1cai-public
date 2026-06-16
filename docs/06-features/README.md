# 🎁 Специальные возможности 1C AI Stack

**Обновлено:** 17 ноября 2025

---

## 📋 Доступные Features

### 🔒 [Security Agent Framework](../../security/agent_framework/README.md)
**Автоматизированные security-проверки**

- CLI для проверки веб-API, репозиториев, n8n workflow и BSL-кода
- Пресеты (`security/agent_framework/presets/*.yaml`) и примеры интеграций (CI, n8n)
- Поддержка публикации отчётов (Markdown/HTML/S3/Confluence) и синхронизации с Neo4j
- Sandbox manager + локальный режим (`--local`) для CI

**Status:** 🟡 MVP (готов к пилотам, требуется доработка sandbox)

---

### 🎤 [Voice Queries](./VOICE_QUERIES.md)
**Голосовые запросы к AI**

- Speech-to-Text через OpenAI Whisper
- Поддержка RU + EN языков
- Интеграция с Telegram Bot
- Accuracy: 95%+

**Status:** ✅ Production

---

### 📸 [OCR Integration](./OCR_INTEGRATION.md)
**Распознавание документов**

- OCR через DeepSeek-OCR (91%+ accuracy)
- Распознавание накладных, актов, счетов
- Извлечение структурированных данных
- Auto-ввод в 1С

**Status:** ✅ Beta (90%)

---

### 🌍 [Multi-language (i18n)](./I18N_GUIDE.md)
**Мультиязычность**

- Полная поддержка RU + EN
- 400+ переведённых ключей
- Легко добавить новые языки
- UI + Documentation

**Status:** ✅ Production

---

### 🧠 [BSL Fine-tuning](./BSL_FINETUNING_GUIDE.md)
**Обучение модели для BSL**

- Dataset с 50+ quality примерами
- 7 категорий (API, business logic, etc.)
- 3 формата (Alpaca, OpenAI, HF)
- Ready для fine-tuning Qwen/Llama

**Status:** 🚧 Dataset Ready (80%)

---

### 🔗 [n8n Integration](./n8n-integration.md)
**No-code автоматизация с 1C AI Stack**

- Кастомная нода `@onecai/n8n-nodes-onec-ai`
- Шаблоны workflow (PR code review, ежедневные дайджесты, health-check)
- Поддержка Graph/Qdrant/PostgreSQL/Code Generation API
- Быстрый запуск: `npm install && npm run build`, переменная `N8N_CUSTOM_EXTENSIONS`

**Безопасность:**
- Используйте отдельный API-ключ и храните его в менеджере секретов (Vault, Doppler, n8n credentials)
- Ограничьте доступ по IP/ VPN, включите HTTPS и rate limiting (`TELEGRAM_RATE_LIMIT_*`, SlowAPI)
- Для production — разворачивайте n8n в приватной сети рядом с API, логируйте audit-следы

**Status:** 🟡 MVP (готов к пилотным внедрениям)

---

### 📦 Marketplace Hardening (Nov 7, 2025)
**См:** [docs/API_REFERENCE.md](../API_REFERENCE.md#-marketplace-api)

- Redis-кэш для витрин (`featured`, `trending`, категории)
- APScheduler обновляет данные каждые `MARKETPLACE_CACHE_REFRESH_MINUTES`
- JWT + Redis rate limiting (по user_id/IP)
- Подписанные ссылки на скачивание через S3/MinIO (`artifact_path`)

**Status:** 🟡 Beta → Production-ready ядро

---

### 🏁 [Feature Flags / Progressive Rollouts](./FEATURE_FLAGS_GUIDE.md)
**Динамическое включение возможностей**

- Управление для пользователей/тенантов/процентов трафика
- Поддержка режимов enabled/disabled/beta/percentage
- Structured logging + in-memory registry (`src/services/feature_flags.py`)

**Status:** ✅ Production

---

### 👨‍💻 [Developer AI Secure](./DEVELOPER_AGENT_GUIDE.md)
**Rule-of-Two разработчик**

- Класс `DeveloperAISecure` с двойной проверкой ввода/вывода через `AISecurityLayer`
- Approval-токены, аудит действий, bulk-approve только для безопасных предложений
- REST-API `/api/code-review/*` + интеграция с UI

**Status:** ✅ Production

---

### 🧪 [QA Engineer AI](./QA_ENGINEER_GUIDE.md)
**Генерация тестов и покрытие**

- Unit/Vanessa/negative шаблоны для BSL
- Edge cases, coverage estimate, рекомендации по тест-плану
- Интеграция с LLM Gateway и pipeline DevOps/QA

**Status:** ✅ Production

---

### ⚡ [SQL Optimizer](./SQL_OPTIMIZER_GUIDE.md)
**Оптимизация SQL и сервера 1С**

- Детекция SQL anti‑patterns, рекомендации по индексам
- Secure-обёртка с Rule-of-Two и audit‑логированием
- Интеграция с Architect MCP и TechLog Analyzer

**Status:** ✅ Production

---

### 📈 [AI Performance & Observability](./AI_PERFORMANCE_GUIDE.md)
**Производительность AI-контуров**

- Метрики Orchestrator/Kimi/Qwen, cache hit rate и fallback‑частота
- Prometheus/Grafana дашборды и alert‑правила
- Практические promql‑запросы и локальные synthetic‑тесты

**Status:** ✅ Production

---

### 🧭 [Scenario Hub & Unified Change Graph](./UNIFIED_CHANGE_GRAPH_GUIDE.md)
**Протокол-независимый слой для сценариев и граф изменений**

- Scenario Recommender: автоматическое предложение релевантных сценариев на основе запроса и Unified Change Graph
- Impact Analyzer: анализ влияния изменений через граф, определение затронутых компонентов и тестов
- OneCCodeGraphBuilder: автоматическое построение графа из BSL модулей для 1С кода
- Unified Change Graph: централизованный граф знаний для всех артефактов проекта
- REST API: `/api/scenarios/recommend`, `/api/graph/impact`, `/api/scenarios/examples`

**Status:** ✅ Production

---

### 🔌 [LLM Provider Abstraction](../../src/ai/llm_provider_abstraction.py)
**Унифицированный уровень абстракции для LLM провайдеров**

- Автоматический выбор провайдера (Kimi, Qwen, GigaChat, YandexGPT) на основе типа запроса, рисков, стоимости и compliance
- ModelProfile: описание рисков, стоимости, latency и поддерживаемых типов запросов
- Интеграция с QueryClassifier для автоматического выбора
- REST API: `/api/llm/providers`, `/api/llm/select-provider`

**Status:** ✅ Production

---

### 💾 [Intelligent Cache](../../src/ai/intelligent_cache.py)
**Интеллектуальное кэширование с контекстной инвалидацией**

- TTL на основе типа запроса, инвалидация по тегам и типу запроса
- LRU eviction, метрики производительности (hit rate, размер кэша)
- Автоматическая отправка метрик в Prometheus
- REST API: `/api/cache/metrics`, `/api/cache/invalidate`

**Status:** ✅ Production

---

### 🖥️ [Unified CLI Tool](../01-getting-started/CLI_GUIDE.md)
**Командная строка для работы с платформой**

- Команды для Orchestrator, Scenario Hub, Unified Change Graph, LLM провайдеров, кэша
- Интеграция с REST API, удобные make-таргеты
- Примеры использования в документации

**Status:** ✅ Production

---

### 🧭 Scenario Hub & Execution Plans (experimental)
**Сценарии, плейбуки и двухконтурный режим**

- Scenario Hub как слой поверх Orchestrator и агентов
- Online-планирование (цели/сценарии) и offline-выполнение плейбуков
- Модели сценариев, шагов, уровней риска и автономности, trust-score

**Docs:** [`AI_SCENARIO_HUB_REFERENCE`](../architecture/AI_SCENARIO_HUB_REFERENCE.md)

---

### 🧰 Tool / Skill Registry (experimental)
**Единый реестр инструментов и skills**

- Абстракция инструментов поверх HTTP/MCP/скриптов
- Описание риска, категорий, схем входа/выхода и SLO
- База для Scenario Hub и Orchestrator при выборе маршрута

**Docs:** [`TOOL_REGISTRY_REFERENCE`](../architecture/TOOL_REGISTRY_REFERENCE.md)

---

### 🧭 [BA-03 Process & Journey Modelling](./BA_PROCESS_MODELLING_GUIDE.md)
**Моделирование процессов и customer journeys**

- Черновики BPMN 2.0 / CJM по тексту требований
- Чек-листы полноты процесса и выявление пробелов
- Подготовка артефактов для Confluence/Jira

**Status:** 🟡 In Progress

---

### 📊 [BA-04 Analytics & KPI Toolkit](./BA_ANALYTICS_KPI_GUIDE.md)
**Аналитика и метрики для BA**

- Конструктор KPI/OKR и бизнес‑метрик
- SQL/BI‑подсказки для PostgreSQL/ClickHouse и Power BI/DataLens
- Связка технических SLO/DORA с бизнес‑эффектом

**Status:** 🟡 In Progress

---

### 🛡 [BA-05 Traceability & Compliance](./BA_TRACEABILITY_COMPLIANCE_GUIDE.md)
**Трассируемость требований и соответствие политикам**

- Матрица «требования → задачи → тесты → релизы»
- Риск‑реестр и heatmap с приоритизацией
- Compliance‑чек‑листы по регуляторике и внутренним политикам

**Status:** 🟡 In Progress

---

### 🤝 [BA-06 Integrations & Collaboration](./BA_INTEGRATIONS_COLLAB_GUIDE.md)
**Интеграции BA-агента и совместная работа**

- Синхронизация требований и артефактов с Jira/Confluence/ServiceNow/Docflow
- Публикация спецификаций, схем и отчётов в Wiki/процессные системы
- Подготовка summary и action items для встреч/воркшопов

**Status:** 🟡 In Progress

---

### 📚 [BA-07 Documentation & Enablement](./BA_ENABLEMENT_GUIDE.md)
**Документация и enablement для BA-команды**

- Генерация playbook/guide материалов по BA‑функциям платформы
- Подготовка презентаций и сценариев демонстраций
- Onboarding‑чек‑листы и training‑сценарии

**Status:** 🟡 In Progress

---

## 🆕 NEW Features (Nov 6, 2025)

### ⚡ Code Execution with MCP
**См:** [docs/08-code-execution/](../08-code-execution/)

- Progressive Disclosure (98.7% token savings)
- PII Protection (152-ФЗ)
- Deno Sandbox
- Skills System

**Status:** ✅ Production Ready

---

### 📋 ITIL/ITSM Support
**См:** [docs/07-itil-analysis/](../07-itil-analysis/)

- Service Desk (planned)
- Incident Management
- Problem Management
- SLA Management

**Status:** 📋 Planned (roadmap ready)

---

## 🎯 Quick Links

- [Security Agent Framework](../../security/agent_framework/README.md)
- [Voice Queries Guide](./VOICE_QUERIES.md)
- [OCR Integration](./OCR_INTEGRATION.md)
- [i18n Guide](./I18N_GUIDE.md)
- [BSL Fine-tuning](./BSL_FINETUNING_GUIDE.md)
- [n8n Integration](./n8n-integration.md)

---

**Все features документированы и готовы к использованию!**

[← Back to Docs](../README.md)
