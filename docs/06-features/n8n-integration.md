## n8n + 1C AI Stack

> **Статус:** MVP готов · обновлено 2025‑11‑06

### Почему это важно

- Быстрая автоматизация 1С-процессов (code review, отчёты, миграции) без написания кода
- Нативная интеграция с REST API 1C AI Stack и enterprise-мессенджерами (Slack/Telegram)
- Готовые сценарии для DevOps/QA команд → экономия времени и прозрачность

### Архитектура

```
n8n Workflow  ──▶  @onecai/n8n-nodes-onec-ai (custom node) ──▶  1C AI Stack API
        ▲                                                      │
        └──────────────────────────────────────────────────────┘
```

### Быстрый старт

```bash
cd integrations/n8n
npm install
npm run build

# указываем путь для n8n (пример для Windows PowerShell)
$env:N8N_CUSTOM_EXTENSIONS = "C:\path\to\repo\integrations\n8n"
n8n start
```

1. В n8n появится раздел *Community → 1C AI Stack*
2. Создайте кред `1C AI Stack API` (base URL, API key, ignore SSL при необходимости)
3. Импортируйте один из шаблонов из `integrations/n8n/workflows/`

> ⚠️ Для production используйте `Authorization: Bearer <token>` из `/auth/token` (JWT), вместо устаревшего API key.

### Поддерживаемые операции

| Resource | Operation | Что делает |
|----------|-----------|------------|
| `Semantic Search / search` | Семантический поиск в Qdrant |
| `Graph / query` | Cypher-запрос к Neo4j |
| `Graph / dependencies` | Граф вызовов функции 1С |
| `Graph / configurations` | Список конфигураций |
| `Graph / objects` | Объекты конфигурации с фильтром по типу |
| `Code Review / analyze` | Анализ кода (локальные правила + OpenAI) |
| `Test Generation / generate` | Генерация тестов (BSL/TS/Python) |
| `Statistics / overview` | Метрики сервисов (Postgres, Neo4j, Qdrant) |
| `Statistics / health` | Health-check |
| `Custom / request` | Произвольный REST-вызов |

### Готовые workflows (пример)

| Файл | Что делает |
|------|------------|
| `daily_semantic_digest.json` | Ежедневный дайджест по НДС (email) |
| `github_pr_code_review.json` | Webhook из GitHub → AI review → ответ |
| `platform_health_telegram_alert.json` | Мониторинг сервисов → Telegram |

> Импортируйте файл, выберите кред и отредактируйте параметры Email/Telegram.

### Проверка

1. Запустите `npm run build` — TypeScript соберёт `dist/`
2. В n8n выполните Cron вручную (Execute Node) → увидите результаты поиска / анализа
3. Для Webhook сценария выполните `curl POST` на URL из ноды `Incoming PR Webhook`

### Безопасность и best practices

- **API-ключи**: создайте отдельный service-token 1C AI Stack, храните его в n8n Credentials / Vault, включите ротацию.
- **Сеть**: держите n8n и API в одной приватной подсети; внешний доступ — через VPN/SSH-туннель.
- **HTTPS**: настройте обратный прокси (Caddy/Nginx) или используйте облачный TLS.
- **Rate limiting**: в .env задайте лимиты (`TELEGRAM_RATE_LIMIT_*`, `N8N_REQUEST_LIMIT`), включите slowapi в API.
- **Логи**: включите audit-логирование запросов и хранение в центральном хранилище (Grafana/Loki).
- **CI/CD**: перед публикацией пакета запускайте `npm run lint && npm run smoke`.

### Ограничения и TODO

- Авторизация: сейчас только Bearer токен (OAuth2 в планах)
- Нет автоматических E2E тестов для workflow-шаблонов
- Marketplace публикация (n8n Hub) — запланировано

Подробности и roadmap: `integrations/n8n/README.md`.

