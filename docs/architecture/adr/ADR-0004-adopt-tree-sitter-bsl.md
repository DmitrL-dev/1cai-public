# ADR-0004: Adopt tree-sitter BSL for AST-based analysis

- **Date:** 2025-11-10
- **Status:** Proposed
- **Supersedes:** None
- **Superseded by:** _n/a_

## Context

Аналитические скрипты (анализ объёмов, зависимостей, best practices) полагаются на JSON/regex обработку и не имеют доступа к полноценному AST. Это ограничивает качество метрик:

- сложнее выявлять точные вызовы функций, цикломатическую сложность, паттерны/антипаттерны;
- невозможно строить структурные диаграммы из кода;
- разные скрипты содержат дублирующие regex-фрагменты.

Проект [alkoleft/tree-sitter-bsl](https://github.com/alkoleft/tree-sitter-bsl) предоставляет grammar для BSL, позволяя использовать tree-sitter API.

## Decision

1. Добавлен модуль `scripts/analysis/tree_sitter_adapter.py`, который пытается загрузить `tools/tree-sitter-bsl.so` (если доступно) и предоставляет утилиты `extract_calls`, `iter_identifiers`.
2. `analyze_dependencies.py` и `analyze_architecture.py` интегрируют AST-аналитику:
   - если parser доступен, обогащают результаты списком вызовов (`call` edges, статистика вызовов);
   - при отсутствии — gracefully fallback (возвращают пустые данные и пишут warning).
3. В документации (HLD, README) добавлены указания по установке парсера и благодарность автору @alkoleft.

## Consequences

- ✅ улучшаем точность анализа зависимостей, получаем новые метрики (частота вызовов, уникальные функции);
- ✅ готовим почву для расширенной визуализации (структурные диаграммы, code smell detection);
- ⛏ требуются инструкции по сборке `tree-sitter-bsl.so` (помещается в `tools/`), возможен недоступный AST на CI, но мы аккуратно fallback.

## Notes

- Благодарим @alkoleft за открытие `tree-sitter-bsl`; без него AST-интеграция была бы существенно сложнее.
- Следующий шаг — использовать AST для вычисления цикломатической сложности по функциям и генерации Mermaid/PlantUML диаграмм.

