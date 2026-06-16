# ML Module

## Overview

Machine Learning Continuous Improvement API - metrics collection, model training, A/B testing.

## Status

✅ **Refactored**: Clean Architecture implementation.
- **Domain**: `domain/models.py`
- **Services**: `services/` (Metrics, Training, ABTest, MLFlow)
- **API**: `api/routes.py`

## Architecture

The module follows Clean Architecture principles:

```
src/modules/ml/
├── domain/
│   └── models.py          # Pydantic models
├── services/
│   ├── metrics_service.py # Metrics collection facade
│   ├── training_service.py# Model training facade
│   ├── ab_test_service.py # A/B testing facade
│   └── mlflow_service.py  # MLflow integration facade
├── api/
│   ├── routes.py          # FastAPI endpoints
│   └── dependencies.py    # Dependency injection
└── tests/                 # Tests
```

## Features

- **Metrics Collection**: Performance tracking for all AI assistants
- **Model Training**: Automated ML model training with MLflow versioning
- **A/B Testing**: Statistical testing framework with traffic splitting
- **MLflow Integration**: Experiment tracking and model registry
- **Predictions**: Real-time model inference with explanations
- **Health Monitoring**: Service health checks

## Endpoints

- `/api/v1/ml/metrics/*` - Metrics collection and retrieval
- `/api/v1/ml/models/*` - Model management (create, train, predict, list)
- `/api/v1/ml/ab-tests/*` - A/B testing (create, predict, analyze)
- `/api/v1/ml/health` - Health check

## Usage

```python
from src.modules.ml import router
app.include_router(router)
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
