# Mega implementation plan: 1cAI enterprise 1C platform

Дата старта: 2026-06-15.

Цель: довести 1cAI от набора сильных 1C-анализаторов до on-prem enterprise platform полного цикла разработки 1C: требования, архитектура, change sets, код/метаданные, проверки, тесты, релизы, approvals, эксплуатация, аудит и AI-ускорение поверх детерминированного ядра.

Исходная стратегия: см. `docs/PRODUCT_RESEARCH_2026-06-15.md`.

## Непереговорные правила реализации

1. Все новые продуктовые слои должны давать ценность без LLM.
2. AI/agent layer может ускорять, объяснять и генерировать, но не должен быть единственным источником истины.
3. Истина продукта: локальные артефакты, графы, политики, approvals, test evidence и audit trail.
4. BA core внутренний. Jira/Confluence/ADO/DOORS/Polarion/TestRail/ServiceNow только optional adapters.
5. EDT, Конфигуратор, BSL LS, Sonar, Vanessa, YAxUnit, OneScript, v8unpack не переписываем без нужды, а оборачиваем адаптерами.
6. Любой рискованный write/apply/deploy/run-execute путь проходит через policy gate и approval.
7. После каждого значимого слоя выполняется полное ревью: scope, code, tests, API, UI, docs, risk, backward compatibility.
8. Нельзя оставлять "готово" без критериев: endpoint, unit tests, smoke path, markdown/evidence output.
9. Новые JSON-хранилища должны быть атомарными, переносимыми и понятными для on-prem эксплуатации.
10. Никаких скрытых сетевых зависимостей в baseline profile.

## Definition of Done для каждого слоя

1. Service/API контракт реализован и покрыт unit tests.
2. Есть markdown/evidence output для CI, ревью или управленческого отчета.
3. Есть health/list/detail сценарии, где это уместно.
4. Ошибки отсутствующего Rentgen store/данных возвращаются явно.
5. MCP tool добавлен для сценариев, где слой нужен агенту/IDE.
6. UI добавлен или обновлен, если слой является пользовательским workflow.
7. Документация обновлена: что делает слой, как запускать, как проверить.
8. Проведен review с findings/open risks/actions.

## Review protocol

Каждый review фиксируется в `docs/reviews/` отдельным файлом вида:

`YYYY-MM-DD_LAYER_REVIEW.md`

Структура:

1. **Scope reviewed**: какие файлы, endpoint-ы, UI, тесты.
2. **Findings**: баги/риски/недоделки, по severity.
3. **Product fit**: закрывает ли слой роль/сценарий.
4. **Enterprise readiness**: audit, access, evidence, policy, offline.
5. **Test evidence**: команды и результат.
6. **Residual risk**: что осталось и почему не блокирует следующий шаг.
7. **Next actions**: конкретные продолжения.

Для кода review stance строгий: сначала bugs/risks/missing tests, потом краткая сводка.

## Target product skeleton

```
Stakeholder Need
  -> Requirement
  -> Capability / Process / Architecture Element
  -> Work Item
  -> Change Set
  -> 1C Metadata / BSL / Form / Role / Query / Integration
  -> Test Case / Test Run / Evidence
  -> Approval / Waiver / Gate Decision
  -> Release Baseline
  -> Incident / Feedback / DORA
```

## Phase 0: hardening the current ground

Цель: убрать красные флаги evidence trail и зафиксировать живое состояние.

### 0.1 Evidence hygiene

Файлы:

- `docs/status/dora_history.md`
- `docs/PRODUCT_RESEARCH_2026-06-15.md`
- `docs/IMPLEMENTATION_MEGA_PLAN_2026-06-15.md`

Работы:

1. Убрать conflict markers из DORA history.
2. Добавить формат append-only DORA history.
3. Зафиксировать, что текущий research doc является source for implementation priorities.

Критерии:

- `rg -n "^(<<<<<<< .+|=======$|>>>>>>> .+)" docs src tests` не находит conflict markers.
- Review `docs/reviews/2026-06-15_PHASE_0_REVIEW.md`.

## Phase 1: Internal ALM / Governance Core

Цель: сделать system of record внутри 1cAI, не завязанный на внешние BA/ALM продукты.

### 1.1 Artifact Graph service

Новый service:

- `src/services/rentgen/artifact_graph.py`

Хранилище:

- `data/artifact_graph.json`

Сущности:

- `need`
- `requirement`
- `capability`
- `architecture_element`
- `work_item`
- `change_set`
- `metadata_object`
- `bsl_module`
- `form`
- `role`
- `query`
- `test_case`
- `test_run`
- `defect`
- `release`
- `incident`
- `approval`
- `waiver`

Общие поля:

- `id`
- `type`
- `title`
- `description`
- `status`
- `owner`
- `risk`
- `priority`
- `tags`
- `created_at`
- `updated_at`
- `version`
- `attributes`

Связи:

- `source_id`
- `target_id`
- `type`
- `status`
- `suspect`
- `created_at`
- `updated_at`
- `rationale`

API:

- `POST /api/v1/artifacts`
- `GET /api/v1/artifacts`
- `GET /api/v1/artifacts/{id}`
- `PATCH /api/v1/artifacts/{id}`
- `POST /api/v1/artifacts/links`
- `GET /api/v1/artifacts/{id}/trace`
- `GET /api/v1/artifacts/matrix`
- `GET /api/v1/artifacts/health`

MCP:

- `artifact_create`
- `artifact_link`
- `artifact_trace`
- `artifact_matrix`

Tests:

- `tests/unit/test_artifact_graph.py`
- `tests/unit/test_artifact_api.py`

Review:

- `docs/reviews/2026-06-15_PHASE_1_ARTIFACT_GRAPH_REVIEW.md`

### 1.2 Requirements repository upgrade

Текущие файлы:

- `src/services/rentgen/requirements_traceability.py`
- `src/api/requirements_api.py`
- `portal/src/routes/_authenticated/requirements.tsx`

Работы:

1. При создании trace record автоматически создавать/обновлять `requirement` artifact.
2. Link requirement -> candidate modules/tests/metadata.
3. Добавить статусный workflow: `draft -> reviewed -> approved -> baselined -> changed -> deprecated`.
4. Добавить suspect links при изменении upstream requirement или linked module.
5. Добавить owner/priority/risk/source/rationale.

API:

- `POST /api/v1/requirements/{id}/transition`
- `POST /api/v1/requirements/{id}/baseline`
- `GET /api/v1/requirements/{id}/trace`

Tests:

- Расширить `tests/unit/test_requirements_traceability.py`

Review:

- `docs/reviews/2026-06-15_PHASE_1_REQUIREMENTS_REVIEW.md`

### 1.3 Change Set core

Новый service:

- `src/services/rentgen/change_sets.py`

Хранилище:

- `data/change_sets.json`

Change set поля:

- `id`
- `title`
- `description`
- `status`
- `owner`
- `source_requirement_ids`
- `changed_modules`
- `diff`
- `risk_summary`
- `release_readiness`
- `test_matrix`
- `approval_ids`
- `waiver_ids`
- `decision_log`
- `created_at`
- `updated_at`

Статусы:

- `draft`
- `impact_analyzed`
- `tests_selected`
- `review_ready`
- `approved`
- `merged`
- `released`
- `rejected`

API:

- `POST /api/v1/change-sets`
- `GET /api/v1/change-sets`
- `GET /api/v1/change-sets/{id}`
- `POST /api/v1/change-sets/{id}/analyze`
- `POST /api/v1/change-sets/{id}/select-tests`
- `POST /api/v1/change-sets/{id}/release-readiness`
- `POST /api/v1/change-sets/{id}/transition`
- `POST /api/v1/change-sets/{id}/decision`

MCP:

- `change_set_create`
- `change_set_analyze`
- `change_set_release_readiness`

UI:

- New or updated page: `/change-sets`
- Link from existing `/change`, `/requirements`, `/release-readiness`.

Tests:

- `tests/unit/test_change_sets.py`
- `tests/unit/test_change_sets_api.py`

Review:

- `docs/reviews/2026-06-15_PHASE_1_CHANGE_SETS_REVIEW.md`

### 1.4 Baselines and review packs

Новый service:

- `src/services/rentgen/baselines.py`

Хранилища:

- `data/baselines.json`
- `data/review_packs.json`

Baseline:

- immutable snapshot of requirement ids, architecture ids, change set ids, test evidence ids, release decision.

Review Pack:

- fixed artifact set for human review;
- comments/resolutions;
- approve/reject;
- evidence hash.

API:

- `POST /api/v1/baselines`
- `GET /api/v1/baselines`
- `GET /api/v1/baselines/{id}`
- `POST /api/v1/review-packs`
- `GET /api/v1/review-packs/{id}`
- `POST /api/v1/review-packs/{id}/comment`
- `POST /api/v1/review-packs/{id}/approve`
- `POST /api/v1/review-packs/{id}/reject`

Review:

- `docs/reviews/2026-06-15_PHASE_1_BASELINES_REVIEW.md`

## Phase 2: Policy & Gates Engine

Цель: централизовать все fail/warn/pass решения и approvals.

### 2.1 Policy-as-code core

Новый service:

- `src/services/rentgen/policy_engine.py`

Файлы:

- `policy/1cai-default-policy.json`
- `data/policy_evaluations.json`
- `data/policy_waivers.json`

Policy domains:

- quality
- impact
- security
- standards
- tests
- metadata
- release
- operations
- edt_mcp

API:

- `POST /api/v1/policies/evaluate`
- `GET /api/v1/policies`
- `POST /api/v1/policies/waivers`
- `POST /api/v1/policies/waivers/{id}/approve`
- `GET /api/v1/policies/evaluations/{id}`

Integrations:

- `release_readiness` uses policy engine.
- `ci_gate` uses policy engine.
- `edt_mcp_bridge` uses policy engine for risky tools.
- `approval_workflow` links to policy evaluation ids.

Review:

- `docs/reviews/2026-06-15_PHASE_2_POLICY_ENGINE_REVIEW.md`

### 2.2 CI evidence and PR/MR reports

Файлы:

- `tools/rentgen/ci_gate.py`
- new templates under `.github/workflows/`, `.gitlab-ci.yml.example`, `azure-pipelines.1cai.yml`, `jenkins/`

Работы:

1. Markdown report includes policy evaluation id, change set id, baseline id.
2. JSON output stable schema.
3. Exit codes documented.
4. Trend storage in `data/ci_gate_history.json`.

Review:

- `docs/reviews/2026-06-15_PHASE_2_CI_PACK_REVIEW.md`

## Phase 3: Test Execution & Evidence

Цель: перейти от "какие тесты нужны" к "тесты запущены, evidence сохранен".

### 3.1 Test evidence store

Новый service:

- `src/services/rentgen/test_evidence.py`

Хранилище:

- `data/test_runs.json`

Сущности:

- test case
- test suite
- test run
- test result
- evidence attachment
- flaky marker

API:

- `POST /api/v1/testing/runs`
- `GET /api/v1/testing/runs`
- `GET /api/v1/testing/runs/{id}`
- `POST /api/v1/testing/runs/import`

### 3.2 Runner adapters

Adapters:

- YAxUnit command runner.
- Vanessa runner.
- 1C:Тестировщик result import.
- JUnit/Allure/JSON import.

Constraints:

- Dry-run by default.
- Actual external command execution requires explicit local config and approval where risky.

Review:

- `docs/reviews/2026-06-15_PHASE_3_TEST_EVIDENCE_REVIEW.md`

## Phase 4: Canonical 1C Metadata Model

Цель: перейти от module-path эвристик к общей модели метаданных.

Новый/расширяемый service:

- `src/services/rentgen/canonical_metadata.py`

Inputs:

- EDT XML
- v8unpack JSON/XML
- live DB metadata export
- `.cf/.dt` extraction
- extensions `.cfe`
- Rights.xml

Entities:

- catalog/document/register/report/processor/common module
- forms
- commands
- roles/RLS
- subscriptions
- scheduled jobs
- exchanges/integrations
- queries

API:

- `POST /api/v1/metadata/import`
- `GET /api/v1/metadata/objects`
- `GET /api/v1/metadata/objects/{id}`
- `GET /api/v1/metadata/drift`
- `GET /api/v1/metadata/rights/diff`

Review:

- `docs/reviews/2026-06-15_PHASE_4_METADATA_REVIEW.md`

## Phase 5: Enterprise IAM, audit and operations

Цель: подготовить продукт к большим компаниям.

### 5.1 Audit log

Новый service:

- `src/services/audit_log.py`

Хранилище:

- `data/audit_log.ndjson`

Events:

- artifact changes
- policy evaluations
- approvals
- waivers
- MCP tool calls
- external command attempts
- release decisions
- baseline creation

API:

- `GET /api/v1/audit/events`
- `GET /api/v1/audit/export`

### 5.2 IAM roadmap implementation

Baseline:

- keep existing JWT/RBAC.

Next:

- OIDC/SAML adapter config.
- LDAP/SCIM user/group sync abstraction.
- project/tenant boundaries.

Review:

- `docs/reviews/2026-06-15_PHASE_5_ENTERPRISE_REVIEW.md`

## Phase 6: UX consolidation

Цель: убрать ощущение набора страниц и собрать основной workflow.

Primary flows:

1. BA creates requirement.
2. System builds trace and candidate impact.
3. Architect reviews blast radius and architecture links.
4. Developer creates change set.
5. System selects tests and evaluates gates.
6. Approver approves risky actions.
7. CI runs and stores evidence.
8. Release readiness creates baseline.
9. Operations incidents link back to release/change/code.

UI routes:

- `/workbench`
- `/artifacts`
- `/change-sets`
- `/baselines`
- `/policies`
- `/testing/runs`
- existing pages linked into the workflow.

Review:

- `docs/reviews/2026-06-15_PHASE_6_UX_REVIEW.md`

## Phase 7: Agentic layer

Цель: AI becomes accelerator, not the product's truth layer.

Modes:

- Ask
- Plan
- Act
- Review

Rules:

- Act mode requires plan.
- Risky action requires approval.
- Every generated change links to change set.
- Every recommendation cites graph/policy/evidence sources.

Agents:

- BA agent
- Architect agent
- 1C developer agent
- QA agent
- Release manager agent
- Ops incident agent
- Security reviewer agent

Review:

- `docs/reviews/2026-06-15_PHASE_7_AGENTIC_REVIEW.md`

## Phase 8: Packaging and enterprise readiness

Deliverables:

- Offline installer or signed artifact bundle.
- Support matrix.
- Deployment guide.
- Security whitepaper.
- Admin guide.
- Backup/restore guide.
- Upgrade guide.
- Customer adapter guide.

Review:

- `docs/reviews/2026-06-15_PHASE_8_PRODUCTIZATION_REVIEW.md`

## Autonomous execution order

1. Phase 0 evidence hygiene.
2. Phase 1.1 Artifact Graph.
3. Review Phase 1.1.
4. Phase 1.2 Requirements repository upgrade.
5. Review Phase 1.2.
6. Phase 1.3 Change Set core.
7. Review Phase 1.3.
8. Phase 1.4 Baselines/review packs.
9. Review Phase 1.4.
10. Phase 2 Policy & Gates Engine.
11. Review Phase 2.
12. Phase 3 Test Evidence.
13. Review Phase 3.
14. Phase 4 Canonical Metadata Model.
15. Review Phase 4.
16. Phase 5 Audit/IAM.
17. Review Phase 5.
18. Phase 6 UX consolidation.
19. Review Phase 6.
20. Phase 7 Agentic layer.
21. Review Phase 7.
22. Phase 8 Productization.
23. Mega review: whole product, docs, tests, UX, enterprise readiness.

## Immediate next implementation slice

Start with Phase 0 and Phase 1.1 because all later work needs a common artifact graph and clean evidence trail.

Concrete first files:

- fix `docs/status/dora_history.md`;
- add `src/services/rentgen/artifact_graph.py`;
- add `src/api/artifacts_api.py`;
- mount router in `src/app/routers.py`;
- add tests `tests/unit/test_artifact_graph.py` and `tests/unit/test_artifact_api.py`;
- add review `docs/reviews/2026-06-15_PHASE_1_ARTIFACT_GRAPH_REVIEW.md`.
