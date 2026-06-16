# Platform Context & Docs

Скрипты, которые экспортируют контекст платформы и генерируют документацию. Используются make-таргетами `make export-context` и `make generate-docs`.

## Скрипты
| Скрипт | Назначение |
|--------|-----------|
| `export_platform_context.py` | Прокси над внешним инструментом `platform-context-exporter` (репозиторий alkoleft). Формирует YAML/JSON контекст проекта. |
| `generate_docs.py` | Вызывает генератор `ones_doc_gen`, собирает актуальные Markdown и индексы. |

## Переменные окружения
- `PLATFORM_CONTEXT_EXPORTER_CMD` — команда/путь к `platform-context-exporter`.
- `ONES_DOC_GEN_CMD` — команда запуска `ones_doc_gen`.

Если переменная не задана, скрипт завершится с понятным сообщением и примером настройки.

## Запуск
```bash
# Экспорт платформенного контекста
make export-context

# Генерация документации (использует результаты анализаторов)
make generate-docs
```

Результаты сохраняются в `output/context/` и `docs/`. После генерации стоит прогнать `make render-uml`, чтобы обновить диаграммы.
