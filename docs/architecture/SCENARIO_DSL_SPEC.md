# Scenario DSL Spec (Draft)

> Статус: **draft / experimental**  
> Цель: задать единый формат описания сценариев (ScenarioPlan), чтобы ими могли
> пользоваться разные реализации (Orchestrator, CLI, внешние агенты, MCP‑серверы)
> и внешние продукты (CodeAlive‑подобные системы, GitOps‑платформы и др.).

---

## 1. Базовые сущности

### 1.1. ScenarioGoal

```yaml
goal:
  id: "ba-dev-qa-DEMO_FEATURE"        # стабильный идентификатор
  title: "BA → Dev → QA для фичи DEMO_FEATURE"
  description: "Согласовать требования, реализовать фичу и покрыть её тестами."
  constraints:
    environment: "staging"            # произвольные ограничения (k/v)
  success_criteria:
    - "BA-спецификация согласована"
    - "Автотесты по фиче зелёные"
```

Обязательные поля:

- `id` — строковый стабильный идентификатор (используется в ссылках/отчётах);
- `title` — краткое человекочитаемое название;
- `description` — развёрнутое описание цели;
- `constraints` — словарь произвольных ограничений (окружения, окна времени, регламенты);
- `success_criteria` — список проверок высокого уровня.

### 1.2. ScenarioStep

```yaml
- id: "ba-spec"
  title: "Уточнение и фиксация требований BA"
  description: "BA-агент готовит и согласует спецификацию по фиче."
  risk_level: "read_only"               # read_only | non_prod_change | prod_low | prod_high
  autonomy_required: "A1_safe_automation" # A0_propose_only | A1_safe_automation | A2_non_prod_changes | A3_restricted_prod
  checks:
    - "BA-спецификация сохранена в Wiki/Docflow"
    - "Есть явное согласие ответственного BA/PO"
  executor: "agent:BA"                  # формат: <kind>:<id>
  metadata:
    feature_id: "DEMO_FEATURE"
    graph_refs:
      services: ["svc-api-gateway", "svc-ba-api"]
      docs: ["confluence://BA-123"]
```

Обязательные поля:

- `id` — уникальный идентификатор шага в рамках плана;
- `title` — краткое название шага;
- `description` — что делает шаг;
- `risk_level` — уровень риска (`read_only`, `non_prod_change`, `prod_low`, `prod_high`);
- `autonomy_required` — минимальный уровень автономности для автоматического выполнения (`A0…A3`);
- `checks` — список формальных проверок, которые должны быть истинны после шага;
- `executor` — строковый идентификатор исполнителя (`agent:*`, `script:*`, `playbook:*`, `human:*`);
- `metadata` — произвольные доп. поля (в том числе привязка к Unified Change Graph через `graph_refs`).

### 1.3. ScenarioPlan

```yaml
id: "plan-ba-dev-qa-DEMO_FEATURE"
version: "1.0.0"
spec: "scenario-dsl/v1"
goal: { ... }               # см. выше
steps:                      # список ScenarioStep
  - { ... }
  - { ... }
required_autonomy: "A2_non_prod_changes"
overall_risk: "non_prod_change"
context:
  kind: "ba-dev-qa"
  feature_id: "DEMO_FEATURE"
artifacts:
  runbook: "docs/08-e2e-tests/BA_DEV_QA_E2E.md"
  playbook: "playbooks/ba_dev_qa_example.yaml"
```

Обязательные поля:

- `id` — идентификатор плана;
- `goal` — `ScenarioGoal`;
- `steps` — список `ScenarioStep` (упорядоченный);
- `required_autonomy` — минимальный уровень автономности для запуска всего плана;
- `overall_risk` — общий риск‑профиль сценария;
- `context` — произвольный контекст (тип сценария, целевые сервисы, окружение);
- `version` / `spec` — версия схемы (для обратной совместимости);
- `artifacts` — ссылки на внешние артефакты (runbooks, docs, playbooks).

---

## 2. Требования к исполнителям и протоколам

Scenario DSL **не привязан** к конкретному протоколу. `executor` — лишь логический идентификатор:

- `agent:*` — логический AI‑агент (BA/Dev/QA/DevOps/DR);
- `script:*` — локальный/удалённый скрипт (Python/PowerShell/Bash);
- `playbook:*` — другой ScenarioPlan или внешний плейбук (Ansible, Argo Workflow, etc.);
- `human:*` — явное участие человека (approval, ручная проверка).

Каждая конкретная платформа (наш Orchestrator, внешние системы) маппит эти идентификаторы
на реальные вызовы: HTTP, MCP, CLI, K8s Job, GitHub Actions и т.п.

---

## 3. Риск и автономия

Scenario DSL использует два измерения:

- `ScenarioRiskLevel`:
  - `read_only` — без изменения состояния;
  - `non_prod_change` — изменения только в test/staging;
  - `prod_low` — ограниченный риск в проде (конфигурация, non‑destructive операции);
  - `prod_high` — высокорисковые операции (DR, миграции, массовые изменения).
- `AutonomyLevel`:
  - `A0_propose_only` — только предложения, без действий;
  - `A1_safe_automation` — read‑only + безопасные проверки;
  - `A2_non_prod_changes` — изменения в non‑prod;
  - `A3_restricted_prod` — ограниченный прод при строгой политике.

Сопоставление этих уровней с разрешёнными действиями выполняется в `Scenario Policy`
(см. `src/ai/scenario_policy.py` и `docs/architecture/AUTONOMY_POLICY_SPEC.md`).

---

## 4. Связь с Unified Change Graph

Scenario DSL не хранит полную структуру графа, но предусматривает ссылки:

- `metadata.graph_refs` на уровне шагов;
- `context` / `artifacts` на уровне плана.

Рекомендуется:

- использовать стабильные идентификаторы узлов из Unified Change Graph (`svc:*`, `db:*`, `alert:*`, `test:*`);
- поддерживать на стороне Code Graph обратную навигацию:
  - узел знает, в каких ScenarioPlan/ScenarioStep он фигурирует.

Это позволяет:

- делать impact‑анализ изменений (какие сценарии затрагиваются);
- строить отчёты и визуаализации «сценарии ↔ код ↔ инфраструктура ↔ риски».

---

## 5. Требования к совместимости и JSON Schema

- Любая реализация Scenario Hub должна:
  - уметь загружать/валидировать YAML/JSON, соответствующий этой спецификации;
  - отдавать сценарии в формате этой же DSL через API (например, `/api/scenarios/*`);
  - не добавлять несовместимые поля без указания новой версии `spec`.
- Внешние продукты (MCP‑серверы, IDE, CodeAlive‑подобные решения) могут:
  - читать ScenarioPlan’ы в этом формате;
  - генерировать свои планы, соблюдая базовую схему;
  - использовать `metadata`/`context`/`artifacts` для собственных нужд.

### 5.1. JSON Schema

Для формальной валидации публикуется JSON Schema:

- файл: `docs/architecture/SCENARIO_DSL_SCHEMA.json`;
- `$id`: `https://1c-ai-stack.example.com/schemas/scenario-dsl/v1`;
- целевой JSON‑объект: целиком `ScenarioPlan` (после загрузки YAML).

Рекомендуемый способ проверки совместимости:

- валидировать все сценарии против схемы в CI;
- использовать наш примерный скрипт `scripts/validation/validate_scenarios_against_schema.py`;
- при расширении DSL (новые поля/enum‑значения) публиковать новую версию `spec`
  и отдельный файл схемы.


