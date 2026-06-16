# Unified Change Graph Reference (Draft)

> Статус: **draft / experimental**  
> Цель: описать общую модель графа изменений (Unified Change Graph), который
> объединяет код, инфраструктуру, тесты, алерты, инциденты и бизнес‑требования.

---

## 1. Общая идея

Unified Change Graph — это не просто граф кода, а «карта изменений»:

- каждый узел отражает важный артефакт системы (сервис, модуль, таблицу, тест, алерт, инцидент, требование);
- каждое ребро — зависимость, влияние или принадлежность к сценарию;
- любые сценарии (Scenario Hub) и политики (Autonomy Policy) опираются на этот граф.

Ключевые задачи:

- impact‑анализ: «что затронет изменение X?»;
- coverage‑анализ: «какие тесты/алерты/DR‑планы покрывают этот узел?»;
- traceability: «какие требования/тикеты/инциденты связаны с этим кодом/сервисом?».

---

## 2. Типы узлов (Node kinds)

Минимальный набор типов (может расширяться):

- `service` — логический сервис/приложение (API, worker, batch job).
- `module` — логический модуль/пакет/namespace внутри сервиса.
- `file` — исходный код/конфигурационный файл.
- `function` / `procedure` — единица логики (функция/процедура/метод).
- `db_table` / `db_view` — таблицы/представления БД.
- `queue` / `topic` — очереди/топики/стримы.
- `api_endpoint` — HTTP/gRPC/RPC‑эндпоинт.
- `k8s_deployment` / `k8s_service` / `ingress` / `job` — K8s‑ресурсы.
- `helm_chart` / `argo_app` / `tf_resource` — инфраструктурные артефакты (Helm/ArgoCD/Terraform).
- `test_case` / `test_suite` — тесты (unit/integration/system/performance).
- `alert` / `slo` — алерты и соглашения об уровне сервиса.
- `incident` — инцидент/постмортем.
- `ba_requirement` — бизнес‑требование/feature/epic.
- `ticket` — задача в Jira/YouTrack/другой системе.

Каждый тип может уточняться (через `subtype`), но базовый `kind` должен быть одним из перечисленных.

---

## 3. Структура узла (Node)

Базовая схема:

```json
{
  "id": "service:ai-orchestrator",
  "kind": "service",
  "display_name": "AI Orchestrator API",
  "labels": ["python", "fastapi", "ai", "orchestrator"],
  "props": {
    "owner": "platform-team",
    "repo": "github://org/1cai",
    "path": "src/ai/orchestrator.py",
    "environment": ["dev", "staging", "prod"],
    "risk_level": "prod_low"
  }
}
```

Обязательные поля:

- `id` — глобально уникальный идентификатор (строка, стабильная); рекомендуемый формат:
  - `service:...`, `module:...`, `file:...`, `db:...`, `alert:...`, `incident:...` и т.п.
- `kind` — тип узла (см. раздел 2).
- `display_name` — человекочитаемое название.
- `labels` — список тегов (язык, домен, слой, команда).
- `props` — словарь свойств (owner, repo, path, env, риск, метаданные).

---

## 4. Типы связей (Edges)

Типы рёбер (минимальный набор):

- `DEPENDS_ON` — «использует» / «зависит от»:
  - модуль → модуль, сервис → сервис, сервис → БД/очередь, код → библиотека.
- `DEPLOYED_AS` — как логический узел проецируется на infra:
  - сервис → k8s_deployment / helm_chart / argo_app / tf_resource.
- `EXPOSES` — сервис → api_endpoint.
- `OWNS` — связь владения:
  - команда → сервис/модуль, сервис → тесты, сервис → алерты.
- `TESTED_BY` — код/сервис → тесты.
- `MONITORED_BY` — сервис/ресурс → алерты/SLO.
- `IMPLEMENTS` — код/сервис → бизнес‑требование (`ba_requirement`), тикет.
- `TRIGGERS_INCIDENT` — код/ресурс → инцидент.
- `PART_OF_SCENARIO` — узел участвует в ScenarioPlan/ScenarioStep.

---

## 5. Формат экспорта/импорта и JSON Schema

Минимальный формат обмена графом:

- список узлов (`nodes: [Node]`);
- список связей (`edges: [Edge]`).

Для формализации формата публикуется JSON Schema:

- файл: `docs/architecture/CODE_GRAPH_SCHEMA.json`;
- `$id`: `https://1c-ai-stack.example.com/schemas/code-graph/v1`;
- пример: `docs/architecture/examples/code_graph_minimal.json`.

Рекомендуется:

- экспортировать граф в формате, совместимом со схемой (для обмена с другими системами);
- валидировать хотя бы один пример экспорта в CI (см. `scripts/validation/validate_code_graph_against_schema.py`
  и make-таргет `validate-standards`).
