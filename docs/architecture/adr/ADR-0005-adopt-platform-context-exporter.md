# ADR-0005: Export platform context and auto-generate docs

- **Date:** 2025-11-10
- **Status:** Proposed
- **Supersedes:** None
- **Superseded by:** _n/a_

## Context

RAG-пайплайн и документация зависят от актуального описания платформенного контекста (объектная модель 1С). Сейчас мы вручную готовим структуры; хотелось бы автоматизировать:

- экспорт контекста (метаданные, объекты, параметры) для последующей загрузки в Neo4j/Qdrant;
- генерацию пользовательской документации на базе ReStructuredText/Markdown для внутренних и внешних команд.

Проекты @alkoleft предоставляют:

- [`platform-context-exporter`](https://github.com/alkoleft/platform-context-exporter) — Java-утилита, которая выгружает полный контекст конфигурации;
- [`ones_doc_gen`](https://github.com/alkoleft/ones_doc_gen) — генератор документации из конфигураций 1С.

Интегрируя их, мы ускорим подготовку RAG данных и сведём к минимуму ручной труд.

## Decision

1. Добавлен скрипт `scripts/context/export_platform_context.py`, который вызывает внешний бинарь/скрипт `platform-context-exporter` (через переменную `PLATFORM_CONTEXT_EXPORTER_CMD`) и сохраняет результаты в `output/context/platform_context.json`.
2. Добавлен скрипт `scripts/context/generate_docs.py`, который вызывает `ones_doc_gen` (переменная `ONES_DOC_GEN_CMD`) и формирует документацию в `output/docs/generated/`.
3. В `Makefile` появились таргеты `export-context` и `generate-docs`. Если внешний инструмент не настроен, команда выводит инструкции и завершает работу без ошибки.
4. `docs/architecture/01-high-level-design.md`, README и `docs/architecture/README.md` обновлены: описан новый этап в Data Lifecycle, добавлена благодарность @alkoleft и ссылки на репозитории.
5. `.gitignore` дополнен исключениями `output/context/` и `output/docs/generated/`.

## Consequences

- ✅ Актуальный платформенный контекст и документация доступны по `make export-context` и `make generate-docs`, готово для RAG/аналитики.
- ✅ Подготовлены инструкции и скрипты, легко добавлять публикацию/CI.
- ⛏ Требуется установить внешний инструмент (Java-утилита); скрипт проверяет наличие и сообщает, что делать.
- ⛏ Нужна поддержка Windows/CI окружений (поставить JRE/OneScript по необходимости).

## Notes

- Благодарим @alkoleft за `platform-context-exporter` и `ones_doc_gen`.
- Следующий ADR (после интеграции doc generator) зафиксирует полный pipeline выгрузка → документация → RAG.

