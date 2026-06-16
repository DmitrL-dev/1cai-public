# 🧭 BA-03 Process & Journey Modelling Guide

**Статус:** ✅ Реализовано  
**Версия:** 1.0.0  
**Дата:** Январь 2025  
**Связанные файлы:** 
- `src/ai/agents/business_analyst_agent_extended.py`
- `src/ai/agents/process_modelling_with_graph.py`
- `src/api/ba_sessions.py`

---

## 1. Цель BA-03

Сделать для бизнес-аналитика «цифрового напарника» по моделированию процессов:

- построение BPMN 2.0 / CJM / простых IDEF0 по текстовому описанию;
- валидация сценариев (где нет данных, где нет ответственных, где нет KPI);
- подготовка артефактов для публикации в Confluence/Jira.

---

## 2. Планируемые возможности

1. **Process Drafting**
   - из описания фичи/процесса формировать черновик:
     - список шагов (as‑is / to‑be),
     - роли/актеры,
     - события/результаты;
   - выдавать структуру, пригодную для BPMN‑редактора или draw.io.

2. **Journey Mapping**
   - генерация customer journey map:
     - стадии (awareness → consideration → purchase → retention),
     - действия, эмоции, pain points,
     - точки интеграции с 1С/внешними системами.

3. **Validation & Checklist**
   - подсказки: где нет владельца, нет входов/выходов, нет измеримого результата;
   - чек‑лист для ревью процесса перед автоматизацией.

---

## 3. Как это будет встраиваться

- BA‑агент (`business_analyst_agent_extended.py`) получает input:
  - описание процесса / фичи,
  - контекст (конфигурация 1С, подсистема, стейкхолдеры),
  - целевую нотацию (BPMN / CJM).
- Возвращает:
  - структурированный JSON (steps, actors, flows),
  - черновики диаграмм (например, PlantUML/Mermaid блоки),
  - список замечаний/рисков.

Интеграция с текущими BA‑инструментами (Requirements Intelligence, Integrations) будет описана в отдельных итерациях BA‑roadmap.

---

## 4. Реализованная функциональность

### ✅ Process Modeller с Unified Change Graph

Реализован `ProcessModellerWithGraph` (`src/ai/agents/process_modelling_with_graph.py`), который автоматически связывает процессы с кодом, требованиями и тестами через Unified Change Graph:

**BPMN Generation:**
- Генерация BPMN моделей из текстового описания
- Автоматическая связь с требованиями (BA_REQUIREMENT)
- Автоматическая связь с кодом (MODULE, FUNCTION) и тестами (TEST_CASE)
- Экспорт в форматы: Mermaid, PlantUML, JSON

**Journey Mapping:**
- Генерация Customer Journey Maps
- Автоматический поиск touchpoints в графе (API endpoints, модули)
- Стандартные стадии: Awareness → Consideration → Purchase → Retention → Advocacy

**Validation:**
- Проверка наличия владельцев для шагов
- Проверка наличия входов/выходов
- Проверка наличия измеримых результатов (KPI)
- Проверка связей с кодом/тестами через граф

### ✅ API Endpoints

Добавлены REST API endpoints в `src/api/ba_sessions.py`:

- `POST /ba-sessions/process/model` — сгенерировать BPMN модель процесса
- `POST /ba-sessions/process/journey-map` — сгенерировать Customer Journey Map
- `POST /ba-sessions/process/validate` — валидировать модель процесса

## 5. Использование

### Python API

```python
from src.ai.agents.business_analyst_agent_extended import BusinessAnalystAgentExtended

agent = BusinessAnalystAgentExtended()

# Сгенерировать BPMN модель с использованием графа
result = await agent.generate_process_model(
    description="Step 1. Start\nStep 2. Process\nStep 3. End",
    requirement_id="REQ001",
    format="mermaid",
    use_graph=True,  # Использовать Unified Change Graph
)

# Сгенерировать Journey Map
journey = await agent.generate_journey_map(
    journey_description="Customer journey from awareness to purchase",
    format="mermaid",
    use_graph=True,
)

# Валидировать процесс
validation = await agent.validate_process_model(result)
```

### REST API

```bash
# Сгенерировать BPMN модель
curl -X POST http://localhost:8000/ba-sessions/process/model \
    -H "Content-Type: application/json" \
    -d '{
        "description": "Step 1. Start\nStep 2. Process\nStep 3. End",
        "requirement_id": "REQ001",
        "format": "mermaid",
        "use_graph": true
    }'

# Сгенерировать Journey Map
curl -X POST http://localhost:8000/ba-sessions/process/journey-map \
    -H "Content-Type: application/json" \
    -d '{
        "journey_description": "Customer journey from awareness to purchase",
        "format": "mermaid",
        "use_graph": true
    }'

# Валидировать процесс
curl -X POST http://localhost:8000/ba-sessions/process/validate \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test Process",
        "steps": [{"id": "step1", "name": "Step 1"}]
    }'
```

## 6. Интеграция с Unified Change Graph

BA-03 автоматически использует Unified Change Graph для:
- Автоматической связи процессов с требованиями, кодом и тестами
- Поиска touchpoints (API endpoints, модули) для Journey Maps
- Валидации связей процесса с кодом/тестами

Если граф недоступен, используется базовый `BPMNGenerator` (fallback).

## 7. Тестирование

```bash
# Запустить unit-тесты
pytest tests/unit/test_process_modelling_with_graph.py -v
```

## 8. См. также

- [`BUSINESS_ANALYST_GUIDE.md`](BUSINESS_ANALYST_GUIDE.md) — общий гайд по BA агенту
- [`BA_ANALYTICS_KPI_GUIDE.md`](BA_ANALYTICS_KPI_GUIDE.md) — BA-04 Analytics & KPI Toolkit
- [`BA_TRACEABILITY_COMPLIANCE_GUIDE.md`](BA_TRACEABILITY_COMPLIANCE_GUIDE.md) — BA-05 Traceability & Compliance
- [`CODE_GRAPH_REFERENCE.md`](../architecture/CODE_GRAPH_REFERENCE.md) — спецификация Unified Change Graph


