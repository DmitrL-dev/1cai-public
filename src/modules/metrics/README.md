# Metrics Module

## Overview

The Metrics module provides a system for collecting, storing, and analyzing metrics from various components of the 1C AI ecosystem. It supports collecting custom metrics, performance tracking, dashboard generation, and alerting.

## Architecture

Refactored from `src/api/metrics.py` into Clean Architecture:

- **Domain**: Pydantic models (`models.py`) for metrics (`MetricRecord`, `MetricCollectionRequest`).
- **Services**:
  - `MetricsService`: Singleton service that manages in-memory storage of metrics. Handles collection, retrieval, aggregation, and alerting logic.
- **API**: FastAPI routes (`routes.py`) exposing endpoints.

## Features

- **Collection**: Accepts metrics from any service via REST API.
- **Performance Tracking**: Automatically tracks latency and processing times.
- **Dashboard**: Provides aggregated overview of system health.
- **Alerting**: Detects anomalies like error spikes or high latency.
- **Management**: Supports clearing old metrics to manage memory usage.

## Usage

The module is exposed via `src.modules.metrics.api.routes`.
Legacy imports from `src.api.metrics` are supported via a proxy file.

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
