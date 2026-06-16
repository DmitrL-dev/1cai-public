# Checklist соответствия стандартам 1C AI Stack

> Цель: дать внешней системе простой, бинарный список проверок, по которому
> можно сказать «мы совместимы со стандартами 1C AI Stack» (Scenario DSL,
> Autonomy Policy, Unified Change Graph).

---

## 1. Scenario DSL

- [ ] **Формат ScenarioPlan**  
  - Сценарии хранятся в формате, совместимом с `SCENARIO_DSL_SPEC.md` (поля `goal`, `steps`, `required_autonomy`, `overall_risk`, `context`, `version`, `spec`).
- [ ] **JSON Schema валидация**  
  - Все сценарии проходят валидацию по `docs/architecture/SCENARIO_DSL_SCHEMA.json`.  
  - В CI настроен автоматический прогон валидации (аналог `make validate-standards`).
- [ ] **API для сценариев**  
  - Платформа предоставляет API (например, `/api/scenarios/*`), отдающее сценарии в формате Scenario DSL.

## 2. Autonomy & Policy

- [ ] **Уровни автономии и риска**  
  - Используются уровни `AutonomyLevel` (`A0_propose_only`…`A3_restricted_prod`) и `ScenarioRiskLevel` (`read_only`…`prod_high`) или их прямые аналоги.
- [ ] **Конфигурация политики по схеме**  
  - Конфигурация политики хранится в JSON, совместимом с `AUTONOMY_POLICY_SCHEMA.json`.
  - В CI настроена валидация этой конфигурации.
- [ ] **Алгоритм принятия решений**  
  - Реализован алгоритм принятия решений по шагу (AUTO / NEEDS_APPROVAL / FORBIDDEN) по логике, эквивалентной `decide_step_execution`/`assess_plan_execution`.

## 3. Unified Change Graph

- [ ] **Базовые типы узлов/связей**  
  - Поддерживаются основные типы из `CODE_GRAPH_REFERENCE.md` (service/module/file/test_case/alert и т.п.) или их сопоставимые аналоги.
- [ ] **Привязка сценариев к графу**  
  - `ScenarioStep.metadata.graph_refs` используются для ссылок на узлы графа (службы, тесты, алерты, runbooks).
  - Граф позволяет по узлу определить, в каких сценариях/шагах он участвует.

## 4. BSL Code Graph (для 1C проектов)

- [ ] **BSL-специфичные типы узлов**  
  - Поддерживаются BSL-специфичные типы из `BSL_CODE_GRAPH_SPEC.md` (bsl_document, bsl_catalog, bsl_register_*, bsl_query, bsl_object_module и т.п.) или их сопоставимые аналоги.
- [ ] **BSL-специфичные типы связей**  
  - Поддерживаются BSL-специфичные связи (BSL_CALLS, BSL_USES_METADATA, BSL_READS_TABLE, BSL_WRITES_TABLE, BSL_EXECUTES_QUERY, BSL_HAS_MODULE и т.п.).
- [ ] **Автоматическое построение графа**  
  - Граф строится автоматически из BSL кода без ручной настройки (через OneCCodeGraphBuilder или аналог).
- [ ] **JSON Schema валидация**  
  - Экспорт графа валиден по `BSL_CODE_GRAPH_SCHEMA.json`.
- [ ] **Интеграция с парсерами**  
  - Используются парсеры, совместимые с `BSL_PARSER_STANDARD.md` (AST, regex-based или neural).

## 5. Тесты и CI

- [ ] **Юнит-тесты схем**  
  - Есть тесты, аналогичные `tests/unit/test_scenario_dsl_schema.py` и `tests/unit/test_autonomy_policy_schema.py`, валидирующие примеры по схемам.
- [ ] **Интеграция в CI**  
  - В CI есть job, аналогичная `spec-driven-validation` из `.github/workflows/comprehensive-testing.yml`, которая:
    - валидирует feature-спеки;
    - валидирует сценарии и политики по JSON Schema.

## 6. Документация

- [ ] **Публичное описание стандартов**  
  - Есть раздел документации, описывающий, как платформа реализует Scenario DSL, Autonomy Policy и Unified Change Graph (со ссылками на схемы и API).
- [ ] **Гид по внедрению**  
  - Для сторонних команд есть краткий гид (по аналогии с `STANDARDS_ADOPTION_GUIDE.md`), объясняющий, как использовать ваши сценарии/политику как стандарт.

---

## 7. Уровни соответствия (рекомендуемая градация)

- **Level 1 — Scenario‑aware**  
  - Выполнены пункты раздела 1 (Scenario DSL) и есть базовая документация (первый пункт раздела 6).
- **Level 2 — Policy‑aware**  
  - Level 1 + полностью выполнен раздел 2 (Autonomy & Policy Model) и есть юнит‑тесты схем (раздел 5).
- **Level 3 — Graph‑aware**  
  - Level 2 + выполнен раздел 3 (Unified Change Graph) и экспорт графа валиден по `CODE_GRAPH_SCHEMA.json`.
- **Level 4 — BSL‑aware** (для 1C проектов)  
  - Level 3 + выполнен раздел 4 (BSL Code Graph) и экспорт графа валиден по `BSL_CODE_GRAPH_SCHEMA.json`.

Такой уровень можно указывать публично, например:  
«Совместимость с 1C AI Stack Standards: Level 2 (Scenario+Policy)».


