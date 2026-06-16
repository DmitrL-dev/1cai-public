# GitHub Integration Module

Clean Architecture implementation for GitHub webhook integration and automated code reviews.

## Structure

```
src/modules/github_integration/
├── domain/
│   ├── models.py          # Pydantic models for GitHub events
│   └── __init__.py
├── services/
│   ├── github_client.py   # GitHub API client with retry logic
│   ├── webhook_handler.py # Webhook event processing
│   ├── review_service.py  # Code review orchestration
│   └── __init__.py
├── api/
│   ├── routes.py          # FastAPI endpoints
│   └── __init__.py
└── __init__.py
```

## Features

- **Webhook Processing**: Handles GitHub PR events (opened, synchronize, reopened)
- **Signature Verification**: Validates webhook signatures for security
- **AI Code Review**: Integrates with AICodeReviewer for automated reviews
- **Retry Logic**: Exponential backoff for GitHub API calls
- **Input Validation**: Comprehensive validation using Pydantic models
- **Error Handling**: Robust error handling with structured logging

## Usage

### Import Router

```python
from src.modules.github_integration import router

app.include_router(router)
```

### Manual Code Review

```python
from src.modules.github_integration import ReviewService, GitHubClient

github_client = GitHubClient()
review_service = ReviewService(github_client)

result = await review_service.review_code(code, "example.bsl")
```

## API Endpoints

- `POST /api/github/webhook` - GitHub webhook endpoint
- `POST /api/github/review` - Manual code review (testing)

## Environment Variables

- `GITHUB_TOKEN` - GitHub API token (required)
- `GITHUB_WEBHOOK_SECRET` - Webhook secret for signature verification (optional)

## Migration from Legacy

The old monolithic `src/api/github_integration.py` (856 lines) has been refactored into this modular structure. The legacy file now serves as a backward compatibility proxy.

All existing imports will continue to work:

```python
# Old import (still works)
from src.api.github_integration import router

# New import (recommended)
from src.modules.github_integration import router
```

---

## 🚀 8. Unified Intelligence (v3.0)

**Мы совершили квантовый скачок. Платформа превратилась в Единую Интеллектуальную ОС.**
Больше никаких разрозненных инструментов. Только **Single Pane of Glass**.

### 1. 🚀 Unified Workspace (Единое Окно)
Мы объединили **VS Code**, **NocoBase**, **Portainer** и **Gitea** в один бесшовный портал.
Вы пишете код, управляете задачами и следите за серверами, не переключая вкладки.

![Unified Dashboard](../../../docs/assets/images/portal_dashboard_v3.png)

### 2. 🧠 RLTF (Reinforcement Learning from Task Feedback)
Система перешла от "выполнения команд" к **самообучению**.
*   **Feedback Loop:** Каждое ваше действие (Save, Commit, Run) — это сигнал для обучения.
*   **Action Prediction:** ИИ предугадывает ваш следующий шаг (например, предлагает "Commit" после успешного теста).
*   **Context Awareness:** "Глаза" системы видят, что происходит в браузере в реальном времени.

### 3. 🔍 Global Search (Brain Index)
Мгновенный поиск по всему:
*   📦 **Код** (Git)
*   ✅ **Задачи** (NocoBase)
*   📄 **Документация** (Wiki)

![Global Search](../../../docs/assets/images/portal_global_search.png)

**Итог:** Это больше не набор скриптов. Это **Secure Enterprise OS**, которая думает вместе с вами.
