# Scenario DSL — Quick Reference Card

> **Одностраничный справочник** для быстрого доступа к ключевым концепциям Scenario DSL

---

## 🎯 Основные концепции

### Что это?

**Scenario DSL** — формальный язык для описания сценариев выполнения (BA→Dev→QA, Code Review, DR Rehearsal) с уровнями автономности и риска.

---

## 📝 Структура сценария

```yaml
id: "ba-dev-qa-scenario"
name: "BA→Dev→QA Full Cycle"
required_autonomy: "A1_safe_automation"
overall_risk: "medium"
steps:
  - id: "ba-requirements"
    name: "Extract Requirements"
    tool: "ba_requirements_extractor"
    autonomy_level: "A1"
    risk_level: "low"
```

---

## 🔐 Уровни автономности

- **A0** — Manual (требует подтверждения)
- **A1** — Safe Automation (безопасная автоматизация)
- **A2** — Supervised Automation (автоматизация под надзором)
- **A3** — Full Automation (полная автоматизация)

---

## ⚠️ Уровни риска

- **low** — Низкий риск
- **medium** — Средний риск
- **high** — Высокий риск
- **critical** — Критический риск

---

## 💻 Быстрый пример

```python
from src.ai.scenario_hub import ScenarioPlan

scenario = ScenarioPlan(
    id="code-review-scenario",
    name="Code Review",
    required_autonomy="A1_safe_automation",
    overall_risk="low",
    steps=[
        {
            "id": "analyze-code",
            "tool": "code_analyzer",
            "autonomy_level": "A1",
            "risk_level": "low"
        }
    ]
)
```

---

## 🔍 JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "id": {"type": "string"},
    "name": {"type": "string"},
    "required_autonomy": {"type": "string", "enum": ["A0", "A1", "A2", "A3"]},
    "overall_risk": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
    "steps": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "tool": {"type": "string"},
          "autonomy_level": {"type": "string"},
          "risk_level": {"type": "string"}
        }
      }
    }
  }
}
```

---

## 📚 Полная документация

- **Спецификация:** [`../architecture/SCENARIO_DSL_SPEC.md`](../../architecture/SCENARIO_DSL_SPEC.md)
- **JSON Schema:** [`../architecture/SCENARIO_DSL_SCHEMA.json`](../../architecture/SCENARIO_DSL_SCHEMA.json)
- **Примеры:** [`../examples/scenario-dsl/`](../examples/scenario-dsl/)

---

**Версия:** 1.0.0 | **Дата:** 2025-11-17

