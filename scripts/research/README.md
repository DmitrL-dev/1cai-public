# Spec-driven & Research Workflow

Сценарии для работы с фичами в стиле GitHub Spec Kit: создание каркасов, проверки заполненности и аудит исследовательских артефактов.

| Скрипт | Назначение |
|--------|-----------|
| `init_feature.py` | Создаёт структуру `docs/research/features/<slug>/`, копирует шаблоны, обновляет индексы. Запускается `make feature-init FEATURE=...`. |
| `check_feature.py` | Проверяет, что спецификация заполнена, нет `TODO`/шаблонных текстов. Используется `make feature-validate`. |

## Использование
```bash
make feature-init FEATURE=smart-cache
make feature-validate FEATURE=smart-cache
```

Связанные документы:
- [`docs/research/constitution.md`](../../docs/research/constitution.md)
- [`docs/research/spec_kit_analysis.md`](../../docs/research/spec_kit_analysis.md)
- [`templates/`](../../templates/)
