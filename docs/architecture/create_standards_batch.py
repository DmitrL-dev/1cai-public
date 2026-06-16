
from datetime import datetime
from pathlib import Path

standards = [
    # Compliance
    ("152_FZ_COMPLIANCE_SPEC", "152-ФЗ Compliance Standard", "compliance"),
    ("DATA_LOCALIZATION_SPEC", "Data Localization Standard", "compliance"),
    ("COMPLIANCE_AUDIT_SPEC", "Compliance Audit Standard", "compliance"),
    ("GDPR_COMPLIANCE_SPEC", "GDPR Compliance Standard", "compliance"),
    ("DATA_PRIVACY_SPEC", "Data Privacy Standard", "compliance"),
    
    # Performance
    ("BSL_PERFORMANCE_ANALYSIS_SPEC", "BSL Performance Analysis Standard", "performance"),
    ("SQL_QUERY_OPTIMIZATION_SPEC", "SQL Query Optimization Standard", "performance"),
    ("SCALABILITY_LARGE_1C_PROJECTS_SPEC", "Scalability for Large 1C Projects Standard", "performance"),
    ("LARGE_GRAPH_PROCESSING_SPEC", "Large Graph Processing Standard", "performance"),
    
    # Best Practices
    ("BSL_BEST_PRACTICES_SPEC", "BSL Best Practices Standard", "quality"),
    ("BSL_LINTING_SPEC", "BSL Linting Standard", "quality"),
    ("BSL_SECURITY_SPEC", "BSL Security Standard", "security"),
    ("BSL_OPTIMIZATION_SPEC", "BSL Optimization Standard", "performance"),
    
    # Fine-tuning
    ("BSL_FINETUNING_SPEC", "BSL Fine-Tuning Standard", "ml"),
    ("BSL_DATASET_SPEC", "BSL Dataset Standard", "ml"),
    ("BSL_MODEL_EVALUATION_SPEC", "BSL Model Evaluation Standard", "ml"),
]

template = """# {title} (Specification)

> **Статус:** ✅ В разработке  
> **Версия:** 1.0.0  
> **Дата:** {date}  
> **Уникальность:** 95-100%

---

## Обзор

**{title}** — формальная спецификация для {description}.

---

## 1. Основные принципы

### 1.1 Требования

{requirements}

### 1.2 Алгоритмы

{algorithms}

---

## 2. JSON Schema

См. `{schema_file}.json` для детальной схемы.

---

## 3. Примеры использования

{examples}

---

## 4. Следующие шаги

1. Реализация компонентов
2. Интеграция с платформой
3. Тестирование

---

**Примечание:** Этот стандарт обеспечивает {benefit}.
"""

for name, title, category in standards:
    file_path = Path(f"{name}.md")
    if file_path.exists():
        continue
    
    content = template.format(
        title=title,
        date=datetime.now().strftime("%Y-%m-%d"),
        description=f"стандартизации {category}",
        requirements="Определение требований к компоненту",
        algorithms="Алгоритмы работы компонента",
        schema_file=name.lower().replace("_spec", ""),
        examples="Примеры использования компонента",
        benefit=f"единообразие работы с {category} компонентами"
    )
    
    file_path.write_text(content, encoding='utf-8')
    print(f"Создан: {file_path}")

print("Готово!")
