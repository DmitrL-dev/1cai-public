# Code Review Module

## Overview

The Code Review module provides real-time code analysis and automated fixing capabilities for multiple programming languages, with a focus on BSL (1C:Enterprise).

## Architecture

Refactored from `src/api/code_review.py` into Clean Architecture:

- **Domain**: Pydantic models (`models.py`) for requests, responses, and metrics.
- **Services**:
  - `CodeAnalyzer`: Core analysis logic, including BSL static analysis.
  - `CodeFixer`: "SMART Auto-Fix" logic for applying automated corrections.
- **API**: FastAPI routes (`routes.py`) exposing `/analyze` and `/auto-fix` endpoints.

## Features

- **Multi-language Support**: BSL, TypeScript, JavaScript, Python.
- **Static Analysis**: Detection of performance issues, security vulnerabilities, and best practice violations.
- **AI Integration**: Optional integration with OpenAI for advanced analysis.
- **Auto-Fix**: Automated correction of common issues (e.g., type checking, null safety).
- **Caching**: Results are cached to improve performance.

## Usage

The module is exposed via `src.modules.code_review.api.routes`.
Legacy imports from `src.api.code_review` are supported via a proxy file.

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
