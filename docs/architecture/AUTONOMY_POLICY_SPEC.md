# Autonomy & Scenario Policy Spec (Draft)

> Статус: **draft / experimental**  
> Цель: задать общий стандарт уровней автономности (A0–A3), риск‑профилей
> и политики выполнения шагов, чтобы любые агенты/оркестраторы могли
> согласованно решать, что можно делать автоматически, а что нет.

---

## 1. Уровни автономности (AutonomyLevel)

Уровни автономности описывают **максимально допустимую степень автоматизации**
в данном окружении/организации/сценарии.

Стандартные уровни:

- `A0_propose_only`  
  - Только предложения и отчёты, без автоматического исполнения действий.  
  - Типичный случай: начальная интеграция AI, аудит, обучение, sandbox.

- `A1_safe_automation`  
  - Разрешены автоматические действия, не меняющие состояние системы (`read_only`).  
  - Примеры: парсинг, анализ, отчёты, генерация предложений, dry‑run.

- `A2_non_prod_changes`  
  - Разрешены изменения в non‑prod окружениях (dev/test/staging), если есть:
    - описанные сценарии,
    - тесты и проверки,
    - возможность отката.  
  - Примеры: применение миграций в staging, запуск DR rehearsal, auto‑fix в test‑окружении.

- `A3_restricted_prod`  
  - Разрешены ограниченные изменения в проде, строго по утверждённым плейбукам и политикам.  
  - Примеры: запуск DR‑сценария по заранее согласованному плану, включение/выключение feature‑flags для части трафика, ротация ключей по расписанию.

Уровень автономности задаётся:

- глобально для инсталляции/организации;
- по окружениям (dev/test/stage/prod);
- по конкретным сценариям (можно запретить A2/A3 для некоторых сценариев).

---

## 2. Уровни риска (ScenarioRiskLevel)

Риск‑профиль шага/сценария определяет, как он взаимодействует с состоянием системы:

- `read_only` — чтение, анализ, логирование, генерация отчётов. Нет изменений состояния.
- `non_prod_change` — изменения ограничены non‑prod окружениями.
- `prod_low` — низкий риск в проде (конфигурация, неразрушающие операции, ограниченные изменения).
- `prod_high` — высокорисковые действия (DR, миграции, массовые изменения данных/конфигураций).

Rиск задаётся:

- на уровне `ScenarioStep` (минимальная деталь);
- агрегируется на уровне `ScenarioPlan.overall_risk` (максимум риска по шагам).

---

## 3. Политика выполнения шагов (Scenario Policy)

Политика описывает, **как интерпретировать** `AutonomyLevel` и `ScenarioRiskLevel`:

### 3.1. Модель AutonomyPolicy

```python
@dataclass
class AutonomyPolicy:
    # Максимальный риск, который можно выполнять автоматически
    max_auto_risk: ScenarioRiskLevel
    # Максимальный риск, который вообще допускается (выше — FORBIDDEN)
    max_allowed_risk: ScenarioRiskLevel
```

Стандартные политики (см. `src/ai/scenario_policy.py:DEFAULT_POLICIES`):

- `A0_propose_only`:
  - `max_auto_risk = read_only`
  - `max_allowed_risk = read_only`
- `A1_safe_automation`:
  - `max_auto_risk = read_only`
  - `max_allowed_risk = non_prod_change`
- `A2_non_prod_changes`:
  - `max_auto_risk = non_prod_change`
  - `max_allowed_risk = non_prod_change`
- `A3_restricted_prod`:
  - `max_auto_risk = prod_low`
  - `max_allowed_risk = prod_high`

### 3.2. StepDecision

Результат применения политики к шагу:

- `AUTO` — шаг может быть выполнен автоматически при данном `AutonomyLevel`;
- `NEEDS_APPROVAL` — требуется явное человеческое подтверждение;
- `FORBIDDEN` — шаг запрещён при данном уровне автономности (даже с approval).

### 3.3. Алгоритм (референс)

```python
def decide_step_execution(step, autonomy, policies=DEFAULT_POLICIES) -> StepDecision:
    policy = policies.get(autonomy)
    if policy is None:
        return StepDecision.NEEDS_APPROVAL

    if compare_risk(step.risk_level, policy.max_allowed_risk) > 0:
        return StepDecision.FORBIDDEN
    if compare_risk(step.risk_level, policy.max_auto_risk) <= 0:
        return StepDecision.AUTO
    return StepDecision.NEEDS_APPROVAL
```

И для плана:

```python
def assess_plan_execution(plan, autonomy, policies=DEFAULT_POLICIES) -> Dict[str, StepDecision]:
    return {step.id: decide_step_execution(step, autonomy, policies) for step in plan.steps}
```

---

## 4. Расширение: Evidence‑based Policy

Базовая политика учитывает только объявленный риск. Для стандарт уровня де‑факто
нужна связь с фактами (evidence) из Unified Change Graph:

Примеры сигналов:

- **Тесты**:
  - есть ли тесты для затронутых узлов;
  - coverage ≥ порога;
  - свежесть прогонов (нет ли «красных» тестов по связанным компонентам).
- **Инциденты и DR**:
  - были ли инциденты по связанным узлам в последнее время;
  - есть ли DR‑план и проходили ли недавние rehearsal’ы;
  - есть ли открытые action items из постмортемов.
- **Security / Policy**:
  - проходят ли Conftest/Semgrep/secret‑scan для затронутых артефактов;
  - есть ли активные policy waivers по этим ресурсам.

Расширенная политика может:

- понижать `max_auto_risk` при низком доверии (мало тестов, много инцидентов);
- требовать `NEEDS_APPROVAL` даже для формально `read_only` шагов, если есть риски;
- запрещать (`FORBIDDEN`) шаги, если по связанным узлам стоят жёсткие waivers или красные SLO.

Это логика реализуется поверх базовой `Scenario Policy` и использует Unified Change Graph
как источник метаданных.

---

## 5. Требования к совместимости и JSON Schema

- Любая реализация Autonomy/Policy должна как минимум поддерживать:
  - стандартные значения `AutonomyLevel` и `ScenarioRiskLevel`;
  - базовый алгоритм принятия решений (AUTO / NEEDS_APPROVAL / FORBIDDEN).
- Расширенные политики (evidence‑based) должны:
  - быть детерминированными и воспроизводимыми (одинаковые входные данные → одинаковое решение);
  - использовать явно описанные источники данных (тесты, метрики, инциденты, waivers);
  - быть задокументированы (какие условия влияют на решения).

### 5.1. JSON Schema для конфигурации политики

Для того, чтобы внешние системы могли хранить/валидировать свою политику
в совместимом формате, публикуется JSON Schema:

- файл: `docs/architecture/AUTONOMY_POLICY_SCHEMA.json`;
- `$id`: `https://1c-ai-stack.example.com/schemas/autonomy-policy/v1`;
- целевой JSON‑объект: словарь `AutonomyLevel.value -> {max_auto_risk, max_allowed_risk}`.

Пример валидной конфигурации (эквивалент `DEFAULT_POLICIES`):

```json
{
  "A0_propose_only":   {"max_auto_risk": "read_only",       "max_allowed_risk": "read_only"},
  "A1_safe_automation": {"max_auto_risk": "read_only",       "max_allowed_risk": "non_prod_change"},
  "A2_non_prod_changes": {"max_auto_risk": "non_prod_change","max_allowed_risk": "non_prod_change"},
  "A3_restricted_prod": {"max_auto_risk": "prod_low",        "max_allowed_risk": "prod_high"}
}
```

Любая платформа, использующая наш стандарт, может:

- хранить свою конфигурацию политики в таком JSON;
- валидировать её по схеме в CI;
- маппить значения на свои типы и алгоритм принятия решений.


