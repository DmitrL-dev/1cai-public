# Analysis Toolkit

Скрипты для разбора конфигураций 1С, EDT-проектов и артефактов ITS. Используются в `make generate-docs`, spec-driven workflow и внутренних аудитах.

## Основные скрипты
| Скрипт | Назначение |
|--------|-----------|
| `generate_documentation.py` | Формирует отчёты и Markdown на основе собранных метаданных (запускается `make generate-docs`). |
| `analyze_1c_metadata_viewer.py` | Извлекает статистику/инвентарь объектов конфигурации. |
| `analyze_architecture.py` | Проверяет архитектурные артефакты, выявляет несоответствия правилам. |
| `analyze_bsl_extension.py` | Анализ BSL-расширений/модулей. |
| `analyze_dependencies.py` | Строит граф зависимостей между модулями и сервисами. |
| `analyze_its_page.py` | Разбирает статьи ITS для пополнения базы знаний. |
| `deep_edt_structure_analysis.py`, `deep_xml_analysis.py` | Глубокая проверка EDT XML, поиск проблемных узлов. |
| `extract_best_practices.py` | Извлекает best practices из конфигураций/ITS. |
| `find_config_ids.py`, `find_its_api.py`, `find_its_endpoints.py` | Поисковые утилиты для идентификаторов, API и эндпоинтов ITS. |
| `tree_sitter_adapter.py` | Обёртка над `tree-sitter-bsl` с fallback на regex; используется другими анализаторами. |

## Требования
- Python 3.11 и зависимости из `requirements.txt` + `requirements-parser-optimization.txt` (при использовании Tree-Sitter).
- Поднятые сервисы (`make docker-up`), если анализ требует подключения к Neo4j/Qdrant.
- Исходные конфигурации 1С или выгрузки EDT (`data/` или `1c_configurations/`).

## Как запустить
```bash
# Сгенерировать документацию по конфигурации
make generate-docs

# Анализ конкретного файла конфигурации
python scripts/analysis/analyze_1c_metadata_viewer.py --config path/to/config.cfe

# Построить граф зависимостей
python scripts/analysis/analyze_dependencies.py --output output/analysis/dependencies.json
```

## Связанные материалы
- [docs/06-features/EDT_PARSER_GUIDE.md](../../docs/06-features/EDT_PARSER_GUIDE.md)
- [docs/06-features/ML_DATASET_GENERATOR_GUIDE.md](../../docs/06-features/ML_DATASET_GENERATOR_GUIDE.md)
- [docs/research/alkoleft_todo.md](../../docs/research/alkoleft_todo.md) — задачи по развитию анализаторов.
