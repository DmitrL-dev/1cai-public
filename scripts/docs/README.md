# Docs Helpers

Утилиты, связанные с документацией и ADR.

| Скрипт | Описание |
|--------|----------|
| `create_adr.py` | Создаёт новый ADR на основе шаблона `docs/architecture/adr/ADR_TEMPLATE.md`, обновляет индекс. Используется make-таргетом `make adr-new SLUG=...`. |
| `render_uml.py` | Рендерит PlantUML диаграммы (`docs/architecture/uml/**`). Запускается `make render-uml` и GitHub Workflow `uml-render-check.yml`. |

## Использование
```bash
# Новый ADR
make adr-new SLUG=use-new-cache

# Перестроить диаграммы
make render-uml
```

Перед коммитом диаграмм обязательно прогоняйте `make render-uml`, чтобы PNG были синхронизированы с `.puml`.
