# Architecture Documentation

Раздел содержит актуальные архитектурные артефакты 1C AI Stack: HLD, C4-модель, доменные диаграммы, ADR и автоматизацию генерации.

## Структура каталога

```
docs/architecture/
├── 00-methodology.md           # (опционально) расширенные договоренности
├── 01-high-level-design.md     # Основной HLD-документ
├── README.md                   # Текущее руководство
├── c4/
│   ├── workspace.dsl           # Structurizr DSL (источник правды)
│   └── png/                    # Рендеры Structurizr (дополнительно, если экспортируем)
├── uml/
│   ├── c4/
│   │   ├── *.puml
│   │   └── png/*.png
│   ├── data/
│   │   ├── *.puml
│   │   └── png/*.png
│   ├── dynamics/
│   │   ├── *.puml
│   │   └── png/*.png
│   ├── integrations/
│   │   ├── *.puml
│   │   └── png/*.png
│   ├── operations/
│   │   ├── *.puml
│   │   └── png/*.png
│   ├── performance/
│   │   ├── *.puml
│   │   └── png/*.png
│   ├── security/
│   │   ├── *.puml
│   │   └── png/*.png
│   └── includes/               # Локальные include'ы (при необходимости)
├── context/
│   ├── export_platform_context.py  # Обёртка для platform-context-exporter
│   └── generate_docs.py            # Обёртка для ones_doc_gen
├── checksums/                  # SHA256-файлы для PNG/SVG (генерируются автоматически)
├── adr/
│   ├── README.md               # Реестр решений
│   ├── ADR-0001-*.md           # Отдельные ADR
│   ├── ADR-0002-*.md           # Решение по BSL-тестам
│   └── ADR-0004-*.md           # Adopt tree-sitter для AST-анализа
├── scripts/docs/*.py           # Утилиты генерации (render_uml, create_adr)
├── research/                   # Дополнительные обзоры (например, alkoleft_inventory.md)
├── SCENARIO_DSL_SPEC.md        # Спецификация Scenario DSL (описание сценариев изменений)
├── CODE_GRAPH_REFERENCE.md     # Unified Change Graph (модель графа изменений)
├── AUTONOMY_POLICY_SPEC.md     # Спецификация уровней автономности и политик Scenario Policy
├── AI_SCENARIO_HUB_REFERENCE.md # AI Scenario Hub & Two-Contour Execution (Reference)
└── TOOL_REGISTRY_REFERENCE.md  # Tool Registry Reference (если существует)
```

## Процесс внесения изменений

1. **Изменения в архитектуре** — обновите HLD, соответствующие диаграммы и при необходимости создайте ADR.
2. **Диаграммы** — редактируйте `.puml`. Для C4 используйте `workspace.dsl` (Structurizr → PlantUML), чтобы избежать дрейфа.
3. **Генерация артефактов**:
   - Локально: `make render-uml` (PNG) или `make render-uml-svg` (PNG + SVG).
   - Скрипт скачает PlantUML (`tools/plantuml-<version>.jar`), построит изображения в `png/` подпапках и обновит `checksums/`.
4. **Проверка CI** — workflow `.github/workflows/uml-render-check.yml` вызывает `make render-uml` и падает, если PNG не совпадают с `.puml`.
5. **ADR** — для фиксирования решений: `make adr-new SLUG="my-decision"`. Файлы сохраняются в `docs/architecture/adr/` и автоматически добавляются в реестр.
6. **BSL тесты** — при добавлении новых скриптов/фреймворков обновляйте manifest `tests/bsl/testplan.json`, Makefile (`test-bsl`) и благодарности авторам (например, [alkoleft/yaxunit](https://github.com/alkoleft/yaxunit)).
7. **MCP инструменты** — если используете внешние MCP-сервисы, настройте `MCP_BSL_CONTEXT_*` / `MCP_BSL_TEST_RUNNER_*`, обновите HLD и оставьте ссылку на исходный репозиторий (например, [alkoleft/mcp-bsl-platform-context](https://github.com/alkoleft/mcp-bsl-platform-context)).
8. **AST анализ** — для расширенного анализа кода соберите `tree-sitter-bsl` (инструкции в `scripts/analysis/tree_sitter_adapter.py`), поместите `.so` в `tools/`, упомяните в документации и поблагодарите автора.
9. **Экспорт контекста** — для RAG и документации используйте `make export-context`, предварительно установив [alkoleft/platform-context-exporter](https://github.com/alkoleft/platform-context-exporter) и настроив `PLATFORM_CONTEXT_EXPORTER_CMD`; артефакты сохраняются в `output/context/`.
10. **Автогенерация документации** — `make generate-docs` вызывает [alkoleft/ones_doc_gen](https://github.com/alkoleft/ones_doc_gen) (`ONES_DOC_GEN_CMD`). Результат — `output/docs/generated/`. Благодарите автора в README/HLD при публикации.
11. **Публикация** — после обновления диаграмм обязательно зафиксируйте изменения в `README.md`/`CHANGELOG.md` и в корневом `README` (секция «Что нового»).

## Интерактивная карта архитектуры

Интерактивная HTML карта (`interactive-architecture.html`) позволяет визуально исследовать архитектуру с возможностью фильтрации, поиска и перехода к документации.

**Как открыть:**
- **GitHub Pages** (рекомендуется): https://dmitrl-dev.github.io/1cai-public/architecture/interactive-architecture.html
- Через JSDelivr: https://cdn.jsdelivr.net/gh/DmitrL-dev/1cai-public@main/docs/architecture/interactive-architecture.html
- Через RawGit: https://raw.githack.com/DmitrL-dev/1cai-public/main/docs/architecture/interactive-architecture.html
- Локально: откройте файл в браузере после клонирования репозитория

**Примечание:** GitHub отображает HTML файлы как исходный код при прямом просмотре. Интерактивная карта автоматически публикуется на GitHub Pages при каждом обновлении.

## Практики сопровождения

- Ссылки из документации должны указывать на PNG-версии диаграмм, чтобы GitHub отображал их нативно.
- Каждому домену (данные, безопасность, эксплуатация, интеграции) соответствует собственная подпапка диаграмм и подраздел в HLD.
- Для сценариев «как есть / как будет» храните две версии диаграмм (помечайте в имени `as-is` / `to-be`).
- При обновлении структурных диаграмм обновляйте Structurizr DSL и наоборот; CI будет контролировать рассинхрон.
- Перед релизом загоняйте `make render-uml` и `python scripts/docs/render_uml.py --fail-on-missing` в обязательный чек-лист.

Поддерживайте единообразие: код → HLD → диаграммы → ADR → мониторинг. Это позволяет быстро отследить изменения и доказать их соответствие при аудитах.

