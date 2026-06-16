# 🛡 BA-05 Traceability & Compliance Guide

**Статус:** ✅ Реализовано  
**Версия:** 1.0.0  
**Дата:** Январь 2025  
**Связанные файлы:** 
- `src/ai/agents/business_analyst_agent_extended.py`
- `src/ai/agents/traceability_with_graph.py`
- `src/api/ba_sessions.py`

---

## 1. Цель BA-05

Помочь BA‑агенту закрыть вопросы трассируемости и соответствия требованиям:

- реестр требований ↔ задач ↔ тестов ↔ релизов (traceability matrix);
- реестр рисков с приоритизацией (risk register, heatmap);
- соответствие регуляторным/внутренним требованиям (compliance checklist).

---

## 2. Планируемые возможности

1. **Traceability Matrix Builder**
   - из списка требований и задач формирует:
     - связь «требование → user story → task → тест → релиз»;
     - таблицу/матрицу для выгрузки в Jira/Confluence.

2. **Risk Register & Heatmap**
   - на основе описания проекта/фичи:
     - выделяет риски (по областям: бизнес, техдолг, безопасность, данные);
     - назначает likelihood/impact, формирует risk score;
     - предлагает heatmap‑представление и mitigation‑планы.

3. **Compliance Checklist**
   - помогает собрать чек‑лист по:
     - регуляторике (152‑ФЗ/GDPR и т.п. — на уровне high‑level требований),
     - внутренним политикам (security, observability, DR).

---

## 3. Как это будет встраиваться

- BA‑агент принимает:
  - список требований/фич (например, из BA‑02),
  - информацию о тестах/релизах (в перспективе — интеграции с Jira/CI),
  - контекст по регуляторике/политикам.
- Возвращает:
  - traceability matrix (JSON/табличное представление),
  - risk register с приоритетами и mitigation,
  - draft compliance‑чек‑лист.

---

## 4. Реализованная функциональность

### ✅ Traceability Matrix с Unified Change Graph

Реализован `TraceabilityWithGraph` (`src/ai/agents/traceability_with_graph.py`), который использует Unified Change Graph для полного traceability:

- **requirements → code** (через `IMPLEMENTS`)
- **code → tests** (через `TESTED_BY`)
- **code → incidents** (через `TRIGGERS_INCIDENT`)

### ✅ Risk Register & Heatmap

Автоматическое построение Risk Register на основе:
- Отсутствие тестов для требований → **high risk**
- Отсутствие кода, реализующего требование → **high risk**
- Наличие инцидентов, связанных с требованием → **high risk**
- Только код без тестов → **high risk**
- Только тесты без кода → **medium risk**

### ✅ Compliance Status

Автоматическое определение compliance status:
- **compliant** — все требования имеют полное покрытие (код + тесты)
- **partially_compliant** — есть требования с частичным покрытием
- **non_compliant** — есть требования без покрытия

### ✅ API Endpoints

Добавлены REST API endpoints в `src/api/ba_sessions.py`:

- `POST /ba-sessions/traceability/matrix` — построить traceability matrix
- `POST /ba-sessions/traceability/risk-register` — построить Risk Register
- `POST /ba-sessions/traceability/full-report` — полный отчёт traceability & compliance

## 5. Использование

### Python API

```python
from src.ai.agents.business_analyst_agent_extended import BusinessAnalystAgentExtended

agent = BusinessAnalystAgentExtended()

requirements = [
    {"id": "REQ001", "title": "Требование 1"},
    {"id": "REQ002", "title": "Требование 2"},
]
test_cases = []

# Построить traceability & risks с использованием графа
result = await agent.build_traceability_and_risks(
    requirements,
    test_cases,
    use_graph=True,  # Использовать Unified Change Graph
)

# Результат содержит:
# - traceability: матрица прослеживаемости
# - risk_register: реестр рисков
# - risk_heatmap: карта рисков (high/medium/low)
# - compliance: статус соответствия
```

### REST API

```bash
# Построить traceability matrix
curl -X POST http://localhost:8000/ba-sessions/traceability/matrix \
    -H "Content-Type: application/json" \
    -d '{
        "requirement_ids": ["REQ001", "REQ002"],
        "include_code": true,
        "include_tests": true,
        "use_graph": true
    }'

# Построить Risk Register
curl -X POST http://localhost:8000/ba-sessions/traceability/risk-register \
    -H "Content-Type: application/json" \
    -d '{
        "requirement_ids": ["REQ001", "REQ002"],
        "include_incidents": true
    }'

# Полный отчёт
curl -X POST http://localhost:8000/ba-sessions/traceability/full-report \
    -H "Content-Type: application/json" \
    -d '{
        "requirement_ids": ["REQ001", "REQ002"]
    }'
```

## 6. Интеграция с Unified Change Graph

BA-05 автоматически использует Unified Change Graph для:
- Автоматического обнаружения связей между требованиями, кодом, тестами и инцидентами
- Построения полной цепочки traceability без ручной настройки
- Impact-анализа изменений требований

Если граф недоступен, используется базовый `TraceabilityMatrixGenerator` (fallback).

## 7. Тестирование

```bash
# Запустить unit-тесты
pytest tests/unit/test_traceability_with_graph.py -v
pytest tests/unit/test_ba_traceability_api.py -v
```

## 8. См. также

- [`BUSINESS_ANALYST_GUIDE.md`](BUSINESS_ANALYST_GUIDE.md) — общий гайд по BA агенту
- [`CODE_GRAPH_REFERENCE.md`](../architecture/CODE_GRAPH_REFERENCE.md) — спецификация Unified Change Graph
- [`1C_CODE_GRAPH_BUILDER_GUIDE.md`](1C_CODE_GRAPH_BUILDER_GUIDE.md) — построение графа из кода 1С


