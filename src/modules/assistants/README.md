# Assistants Module

## Overview

The Assistants module provides a REST API for interacting with various AI assistants, primarily the Architect Assistant. It supports chat, requirements analysis, architectural diagram generation, and risk assessment.

## Architecture

Refactored from `src/api/assistants.py` into Clean Architecture:

- **Domain**: Pydantic models (`models.py`) for requests (`ChatRequest`, `AnalyzeRequirementsRequest`, etc.).
- **Services**:
  - `ArchitectService`: Encapsulates logic for interacting with the `ArchitectAssistant`. Handles query processing, analysis, and diagram generation.
- **API**: FastAPI routes (`routes.py`) exposing endpoints.

## Features

- **Chat**: Interactive chat with AI assistants.
- **Requirements Analysis**: Analyzes business requirements for architectural implications.
- **Diagram Generation**: Generates Mermaid diagrams (flowcharts, sequence diagrams, etc.) based on architecture proposals.
- **Comprehensive Analysis**: Performs a full analysis including requirements, architecture, and risks.
- **Risk Assessment**: Identifies potential risks in architectural solutions.
- **Knowledge Management**: Allows adding documents to the assistant's knowledge base.

## Usage

The module is exposed via `src.modules.assistants.api.routes`.
Legacy imports from `src.api.assistants` are supported via a proxy file.

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
