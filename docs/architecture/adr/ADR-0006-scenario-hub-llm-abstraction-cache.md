# ADR-0006: Scenario Hub, LLM Provider Abstraction, Intelligent Cache

- **Date:** 2025-11-17
- **Status:** Accepted
- **Supersedes:** None
- **Superseded by:** _n/a_

## Context

Платформа развивается как платформа для AI-ассистированной разработки на 1С. Требуется:

1. **Протокол-независимый слой сценариев** — пользователям сложно видеть AI-агентов как целостные сценарии, получается "зоопарк инструментов" и протоколов (HTTP, MCP, скрипты).
2. **Унификация LLM провайдеров** — необходимо единообразно работать с разными провайдерами (Kimi, Qwen, GigaChat, YandexGPT) с автоматическим выбором на основе типа запроса, рисков, стоимости и compliance требований.
3. **Интеллектуальное кэширование** — требуется контекстно-зависимое кэширование с TTL на основе типа запроса, автоматической инвалидацией и метриками производительности.

## Decision

### 1. Scenario Hub & Unified Change Graph

1. Создан протокол-независимый слой **Scenario Hub** (`src/ai/scenario_hub.py`, `src/ai/scenario_recommender.py`) для определения и выполнения сценариев (BA→Dev→QA, Code Review, DR Rehearsal).
2. Реализован **Scenario Recommender** для автоматического предложения релевантных сценариев на основе запроса пользователя и узлов Unified Change Graph.
3. Реализован **Impact Analyzer** для анализа влияния изменений через граф, определения затронутых компонентов, тестов и генерации рекомендаций.
4. Интегрирован **Unified Change Graph** (`src/ai/code_graph*.py`) как централизованный граф знаний для всех артефактов проекта.
5. Создан **OneCCodeGraphBuilder** (`src/ai/code_graph_1c_builder.py`) для автоматического построения графа из BSL модулей.

### 2. LLM Provider Abstraction

1. Создан **LLM Provider Abstraction Layer** (`src/ai/llm_provider_abstraction.py`) для унификации работы с разными LLM провайдерами.
2. Реализован **ModelProfile** с описанием рисков, стоимости, latency и поддерживаемых типов запросов.
3. Интегрирован с **QueryClassifier** для автоматического выбора провайдера на основе типа запроса и compliance требований.
4. Добавлены REST API endpoints (`/api/llm/providers`, `/api/llm/select-provider`) для управления провайдерами.

### 3. Intelligent Cache

1. Создан **IntelligentCache** (`src/ai/intelligent_cache.py`) с TTL на основе типа запроса, инвалидацией по тегам и типу запроса, LRU eviction.
2. Интегрирован в **AI Orchestrator** с fallback на простой dict для обратной совместимости.
3. Добавлены метрики производительности (hit rate, размер кэша, статистика) и автоматическая отправка в Prometheus.
4. Добавлены REST API endpoints (`/api/cache/metrics`, `/api/cache/invalidate`) для управления кэшем.

### 4. Unified CLI Tool

1. Создан унифицированный CLI инструмент (`scripts/cli/1cai_cli.py`) для работы со всеми компонентами платформы.
2. Добавлены make-таргеты в `Makefile` для удобного использования.
3. Создана документация `docs/01-getting-started/CLI_GUIDE.md` с примерами использования.

### 5. Observability & Performance

1. Добавлены Prometheus метрики для всех новых компонентов в `src/monitoring/prometheus_metrics.py`.
2. Интегрированы метрики в компоненты через helper-функции (`track_scenario_recommendation`, `track_impact_analysis`, `track_llm_provider_selection`, `track_intelligent_cache_operation`).
3. Созданы performance benchmarks (`tests/performance/test_new_components_performance.py`) с целевыми метриками производительности.
4. Создана документация `docs/05-development/PERFORMANCE_BENCHMARKS.md`.

### 6. Architecture Documentation

1. Созданы UML-схемы для новых компонентов:
   - Sequence-диаграммы: `scenario-recommender-flow.puml`, `llm-provider-selection.puml`, `intelligent-cache-flow.puml`
   - Component-диаграмма: `cli-tool-overview.puml`
2. Обновлена C4 component-диаграмма `component-analysis.puml` с новыми компонентами.
3. Обновлён HLD документ (`docs/architecture/01-high-level-design.md`) с информацией о новых компонентах.

## Consequences

### Положительные

- ✅ **Протокол-независимость** — сценарии доступны из CI, CLI и GitOps, не только через MCP/LLM.
- ✅ **Унификация LLM провайдеров** — единый интерфейс для работы с разными провайдерами, автоматический выбор оптимального.
- ✅ **Производительность** — интеллектуальное кэширование значительно улучшает производительность и снижает нагрузку на LLM провайдеры.
- ✅ **Observability** — полная observability в production через Prometheus метрики.
- ✅ **DevEx** — унифицированный CLI инструмент улучшает developer experience.
- ✅ **Архитектурная документация** — полная документация на уровне UML-схем и HLD.

### Отрицательные / Требует внимания

- ⛏ **Сложность** — добавлены новые абстракции, требуется обучение команды.
- ⛏ **Зависимости** — новые компоненты зависят от Unified Change Graph, что требует его поддержки.
- ⛏ **Производительность** — Scenario Recommender и Impact Analyzer требуют запросов к графу, что может быть узким местом при больших графах.

## Notes

- Все новые компоненты имеют E2E тесты (`tests/system/test_e2e_*.py`).
- Performance benchmarks определены с целевыми метриками (p95 < 50ms для малого графа, p95 < 1ms для cache hit).
- UML-схемы созданы и готовы к рендерингу через `make render-uml`.
- Документация обновлена в README.md, HLD и созданы специализированные гайды.

## References

- [Scenario Hub Reference](../AI_SCENARIO_HUB_REFERENCE.md)
- [Unified Change Graph Reference](../CODE_GRAPH_REFERENCE.md)
- [Performance Benchmarks](../../05-development/PERFORMANCE_BENCHMARKS.md)
- [CLI Guide](../../01-getting-started/CLI_GUIDE.md)
- UML Diagrams: `docs/architecture/uml/dynamics/*.puml`, `docs/architecture/uml/integrations/cli-tool-overview.puml`

