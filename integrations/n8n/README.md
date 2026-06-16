# @onecai/n8n-nodes-onec-ai

n8n community node, добавляющий доступ к API 1C AI Stack (semantic search, зависимости, код-ревью и др.).

## Установка

```bash
npm install @onecai/n8n-nodes-onec-ai
```

Добавьте путь к ноде в `N8N_CUSTOM_EXTENSIONS` или скопируйте `dist/` в каталог кастомных нод.

## Настройка

1. Создайте креденшал "1C AI Stack API":
   - Base URL (например `http://localhost:8080`)
   - API Key (при необходимости)
2. В workflows используйте ресурс `Custom` или pre-configured endpoints.

## Разработка

```bash
npm install
npm run build
npm run smoke
```

Smoke-тест требует запущенный n8n (`N8N_BASE_URL`, `N8N_USER_EMAIL`, `N8N_USER_PASSWORD`).

