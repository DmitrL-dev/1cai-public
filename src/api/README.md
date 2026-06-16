# API Layer

FastAPI эндпоинты и сервисы Graph API/Assistants/Marketplace/Monitoring.

## Основные модули
- `graph_api.py` — GraphQL/REST endpoints для платформы (Neo4j/Qdrant доступы).
- `assistants.py`, `copilot_api.py`, `copilot_api_perfect.py` — API для общения с AI-ассистентами.
- `github_integration.py`, `code_review.py`, `documentation.py` — интеграции с GitHub, код-ревью, документацией.
- `gateway.py`, `marketplace.py`, `risk.py`, `monitoring.py` — API для внешних сервисов и мониторинга.
- `test_generation.py`, `test_generation_ts.py` — генерация тестов (Python/TypeScript).
- `billing_webhooks.py`, `tenant_management.py`, `admin_*` — управление биллингом, многотенантность и административные панели.

## Middleware
В папке [`middleware/`](middleware/) находятся промежуточные слои: `tenant_context`, security headers, rate limiter. Дополнительно глобальные middleware лежат в `src/middleware/`.

## Связанные разделы
- [docs/06-features/MCP_SERVER_GUIDE.md](../../docs/06-features/MCP_SERVER_GUIDE.md)
- [docs/runbooks/](../../docs/runbooks/README.md)
- [docs/ops/devops_platform.md](../../docs/ops/devops_platform.md)
