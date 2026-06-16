# Переход от MCP-центричного подхода к сценариям и протокол-независимым инструментам

> Статус: **экспериментальный архитектурный слой**  
> Цель: уменьшить зависимость рантайма от MCP и IDE, сохранив удобство работы разработчикам.

---

## 1. Зачем пересматривать MCP-цепочку

Изначально стек опирался на MCP как на «универсальный транспорт»:

- IDE ↔ MCP server ↔ AI-инструменты (генерация кода, тесты, анализ).

Проблемы такого подхода:

- **Жёсткая связка с IDE и конкретным протоколом** — сложнее запускать те же сценарии из CI, CLI, GitOps.
- **Сложнее контролировать риск** — MCP видит только «инструменты», но не бизнес-сценарий целиком.
- **Runtime-зависимость от LLM/MCP** — даже для повторяющихся операций нужен онлайн-контур.

Цель изменений: оставить MCP как **один из каналов доступа** (IDE, интерактив), но вывести основное выполнение
в более предсказуемый, протокол-независимый контур.

---

## 2. Что именно сделано

### 2.1. Scenario Hub и двухконтурный режим

Реализован reference-слой Scenario Hub (`src/ai/scenario_hub.py`, `docs/architecture/AI_SCENARIO_HUB_REFERENCE.md`):

- явные модели `ScenarioGoal`, `ScenarioStep`, `ScenarioPlan`;
- уровни риска (`ScenarioRiskLevel`) и автономности (`AutonomyLevel A0–A3`);
- `ScenarioExecutionReport` и `TrustScore` как каркас для понятных отчётов.

Это позволяет:

- в online-контуре (IDE, MCP, чат-агенты) **планировать** сценарий на высоком уровне;
- в offline-контуре (скрипты, HTTP API, playbooks) **детерминированно выполнять** шаги без участия LLM/MCP.

### 2.2. Tool / Skill Registry (протокол-независимый слой)

В `src/ai/tool_registry.py` и `src/ai/tool_registry_examples.py` описан реестр инструментов:

- `ToolDescriptor` знает о категории (`BA/DR/SECURITY/DEV`), уровне риска и эндпоинтах (HTTP, CLI, script, MCP);
- отдельные usage-примеры можно использовать для семантического поиска и документации;
- endpoint `/api/tools/registry/examples` (`src/ai/orchestrator.py`) даёт витрину доступных skills.

Зачем это нужно:

- Orchestrator и Scenario Hub опираются не на «сырые» MCP-инструменты, а на **описанные способности** платформы;
- один и тот же инструмент может быть вызван через MCP, HTTP или CLI, не меняя архитектуру сценария.

### 2.3. YAML/JSON-плейбуки и dry-run вместо «размытых» шагов

Добавлены реальные YAML-плейбуки в `playbooks/`:

- `playbooks/ba_dev_qa_example.yaml` — сценарий BA→Dev→QA;
- `playbooks/dr_vault_example.yaml` — DR rehearsal для Vault;
- `playbooks/security_audit_example.yaml` — сценарий комплексного security-audit.

Исполнитель:

- `src/ai/playbook_executor.py` — загрузка плейбука, маппинг в `ScenarioPlan`, dry-run с применением `ScenarioPolicy`;
- `scripts/runbooks/run_playbook.py` — CLI для локального dry-run (без реальных действий).

API:

- `GET /api/scenarios/examples` — примеры `ScenarioPlan` (BA→Dev→QA, DR rehearsal) с возможностью применения `ScenarioPolicy`;
- `GET /api/scenarios/dry-run?path=...&autonomy=...` — dry-run YAML-плейбука через HTTP, без участия LLM/MCP в рантайме.

### 2.4. Интеграция с Orchestrator и агентами (без жёсткой MCP-зависимости)

В `src/ai/orchestrator.py`:

- `QueryClassifier` теперь не только выдаёт `QueryType` и список сервисов, но и:
  - формирует `suggested_tools` — id инструментов из ToolRegistry, подходящих под intent;
- `AIOrchestrator.process_query` обогащает каждый ответ блоком:
  - `_meta.intent` (тип запроса, confidence, ключевые слова, предпочитаемые сервисы);
  - `_meta.suggested_tools` (рекомендованные инструменты/skills).

Практический эффект:

- MCP/IDE могут использовать Orchestrator как простой HTTP endpoint, не зная деталей сценариев;
- сами сценарии и политика риска описаны на уровне YAML/ToolRegistry/Scenario Hub и могут выполняться также из CI/CLI.

---

## 3. Что это даёт по сравнению с MCP-only

### 3.1. Надёжность и предсказуемость

- Сценарий фиксируется в YAML/JSON и `ScenarioPlan`, а не только в «памяти» LLM и цепочках MCP-вызовов.
- Dry-run и Policy (AutonomyLevel + ScenarioRiskLevel) позволяют заранее увидеть, какие шаги:
  - будут автоматизированы;
  - потребуют approval;
  - запрещены при текущем уровне автономности.

### 3.2. Безопасность

- Риск описан на уровне **шага** и сценария, а не только на уровне «tool call».
- Для сложных операций (DR, security-audit, изменения в infra) плейбуки выполняются в offline-режиме
  через проверенные скрипты, а не напрямую из LLM.

### 3.3. Гибкость по протоколам

- MCP становится одним из фронтов:
  - IDE ↔ MCP ↔ HTTP/CLI/Scenario Hub;
- те же сценарии доступны из:
  - CLI (`scripts/runbooks/run_playbook.py`),
  - HTTP API (`/api/scenarios/*`),
  - GitOps/CI (запуск playbooks и policy-checks в pipeline).

---

## 4. Что остаётся MCP и что ещё планируется

Что остаётся за MCP:

- интерактивная работа в IDE (Context, quick-fix, code actions);
- удобная интеграция с редакторами (CursorExt, MCP server).

Что ещё открыто в бэклоге:

- полная интеграция плейбуков и ToolRegistry в основной API/агентов (автоматический выбор сценариев по метрикам);
- CI-интеграция для прогонов сценариев (BA→Dev→QA, DR, security-audit) без необходимости MCP/IDE.

Главная идея: **думать сценариями, риском и политиками**, а не только набором MCP-инструментов. MCP остаётся
полезным интерфейсом, но не единственной «точкой правды» и не ядром рантайма.



