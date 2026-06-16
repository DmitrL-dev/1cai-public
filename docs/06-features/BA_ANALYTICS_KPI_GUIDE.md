# 📊 BA-04 Analytics & KPI Toolkit Guide

**Статус:** ✅ Реализовано  
**Версия:** 1.0.0  
**Дата:** Январь 2025  
**Связанные файлы:** 
- `src/ai/agents/business_analyst_agent_extended.py`
- `src/ai/agents/analytics_kpi_with_graph.py`
- `src/api/ba_sessions.py`

---

## 1. Цель BA-04

Дать BA‑агенту «второй мозг» для аналитики и KPI:

- формирование метрик успеха для фич/инициатив (OKR, KPI, North Star);
- вспомогательные SQL/BI‑запросы к хранилищу (PostgreSQL / ClickHouse);
- связка с Observability (SLO, error budgets) для оценки влияния релизов.

---

## 2. Планируемые возможности

1. **KPI Designer**
   - из описания фичи/процесса предлагает:
     - ключевые бизнес‑метрики (revenue, churn, NPS, lead time и т.п.),
     - технические метрики (latency, error rate, deployment frequency);
   - выдаёт таблицу KPI с:
     - формулой,
     - источником данных,
     - периодичностью.

2. **SQL / BI Helper**
   - генерирует черновики SQL‑запросов под PostgreSQL:
     - отчёты по воронке, retention, cohort analysis;
   - даёт примеры визуализаций для Power BI / DataLens:
     - тип графика,
     - какие поля вывести и как сгруппировать.

3. **SLO & Business Impact Bridge**
   - на основе SLO/инцидентов (из `docs/observability/SLO.md`, DORA) помогает:
     - сопоставить технические метрики с бизнес‑эффектом,
     - сформулировать «Story» для executive‑отчёта.

---

## 3. Как это будет встраиваться

- BA‑агент принимает:
  - описание фичи / процесса / инцидента,
  - контекст (продукт, сегмент, ключевые стейкхолдеры),
  - доступные источники данных (PostgreSQL/ClickHouse, BI‑системы).
- Возвращает:
  - список KPI/OKR,
  - примеры SQL/визуализаций,
  - краткий аналитический summary (для презентации или отчёта).

---

## 4. Реализованная функциональность

### ✅ KPI Generator с Unified Change Graph

Реализован `KPIGeneratorWithGraph` (`src/ai/agents/analytics_kpi_with_graph.py`), который автоматически строит KPI на основе реальных метрик из графа:

**Технические KPI:**
- **Code Coverage** — процент кода, покрытого тестами для фичи
- **Test Coverage** — процент требований, покрытых тестами
- **Incident Rate** — количество инцидентов на модуль
- **Change Failure Rate** — процент изменений, приводящих к инцидентам (DORA metric)

**Бизнес KPI (шаблоны):**
- **Revenue Impact** — влияние фичи на выручку
- **User Adoption** — процент пользователей, использующих фичу
- **Time to Value** — время от релиза до первого использования

### ✅ SQL Query Builder

Автоматическая генерация SQL-запросов для KPI:
- SQL для технических KPI на основе графа (code coverage, incident rate)
- SQL шаблоны для бизнес KPI (требуют внешних данных)

### ✅ Visualizations

Автоматические рекомендации по визуализациям:
- Тип графика (gauge для coverage, bar для rate, line для трендов)
- Рекомендуемый инструмент (Grafana для технических, Power BI для бизнес)

### ✅ API Endpoints

Добавлен REST API endpoint в `src/api/ba_sessions.py`:

- `POST /ba-sessions/analytics/kpi` — сгенерировать KPI для инициативы/фичи

## 5. Использование

### Python API

```python
from src.ai.agents.business_analyst_agent_extended import BusinessAnalystAgentExtended

agent = BusinessAnalystAgentExtended()

# Сгенерировать KPI с использованием графа
result = await agent.design_kpi_blueprint(
    initiative_name="Новая фича",
    feature_id="FEATURE001",
    use_graph=True,  # Использовать Unified Change Graph
)

# Результат содержит:
# - kpis: список KPI с формулами, значениями, целями
# - sql_queries: SQL-запросы для каждого KPI
# - visualizations: рекомендации по визуализациям
```

### REST API

```bash
# Сгенерировать KPI
curl -X POST http://localhost:8000/ba-sessions/analytics/kpi \
    -H "Content-Type: application/json" \
    -d '{
        "initiative_name": "Новая фича",
        "feature_id": "FEATURE001",
        "include_technical": true,
        "include_business": true,
        "use_graph": true
    }'
```

## 6. Интеграция с Unified Change Graph

BA-04 автоматически использует Unified Change Graph для:
- Автоматического построения технических KPI на основе реальных метрик (code, tests, incidents)
- Генерации SQL-запросов для извлечения данных из графа
- Расчёта DORA метрик (Change Failure Rate)

Если граф недоступен, используется базовый `design_kpi_blueprint` с шаблонными KPI.

## 7. Тестирование

```bash
# Запустить unit-тесты
pytest tests/unit/test_analytics_kpi_with_graph.py -v
```

## 8. См. также

- [`BUSINESS_ANALYST_GUIDE.md`](BUSINESS_ANALYST_GUIDE.md) — общий гайд по BA агенту
- [`BA_TRACEABILITY_COMPLIANCE_GUIDE.md`](BA_TRACEABILITY_COMPLIANCE_GUIDE.md) — BA-05 Traceability & Compliance
- [`CODE_GRAPH_REFERENCE.md`](../architecture/CODE_GRAPH_REFERENCE.md) — спецификация Unified Change Graph


