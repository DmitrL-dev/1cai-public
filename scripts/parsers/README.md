# Parsers

Набор парсеров 1C-конфигураций, EDT XML и AST для BSL. Используются анализаторами, MCP-инструментами и пайплайнами генерации документации.

## Категории
| Подкаталог | Что внутри |
|------------|------------|
| Корневые `parse_1c_config*.py` | Последовательные версии парсера `.cf/.cfe`. Отличаются оптимизациями и сценариями использования. |
| `edt/` | Парсеры EDT-проектов, включая работу с `metadata.xml`, структурой модулей и форм. |
| `legacy/` | Исторические версии парсера и документация по обратной совместимости. |
| `neural/` | Экспериментальные нейросетевые парсеры (contrastive, graph-based, meta-learning). |

## Ключевые скрипты
| Скрипт | Назначение |
|--------|-----------|
| `parse_1c_config.py` | Базовый парсер `.cf/.cfe`, формирует JSON-структуру для анализаторов. |
| `parse_1c_config_advanced.py` | Расширенный парсер с дополнительными метриками и контролями. |
| `parse_edt_xml.py` | Читает EDT-проект, преобразует в единый JSON/Graph формат. |
| `bsl_ast_parser.py` | Парсинг модулей BSL, отдаёт AST (используется MCP). |
| `optimized_xml_parser.py` | Быстрый парсер XML с оптимизированными проходами. |
| `improve_bsl_parser.py`, `improve_parser_with_mcp.py` | Эксперименты по улучшению точности AST. |
| `parser_integration.py` | Склеивает результаты парсеров (магистральный вход для анализаторов). |

## Зависимости
- `tree-sitter-bsl` (см. `requirements-parser-optimization.txt`).
- `libxml2/libxslt` или аналоги (для некоторых XML-проходов).
- При использовании `neural/` — дополнительные зависимости из `requirements-neural.txt` и GPU-драйвер.

## Примеры запуска
```bash
# Базовый парсинг конфигурации
python scripts/parsers/parse_1c_config.py --input path/to/conf.cf --output output/parser/conf.json

# EDM → JSON
python scripts/parsers/parse_edt_xml.py --src 1c_configurations/my_project --dest output/parser/edt.json

# AST модулей BSL
python scripts/parsers/bsl_ast_parser.py --module src/bsl/sample.bsl --out output/ast/sample.json
```

## Связанные документы
- [docs/06-features/AST_TOOLING_BSL_LANGUAGE_SERVER.md](../../docs/06-features/AST_TOOLING_BSL_LANGUAGE_SERVER.md)
- [docs/06-features/EDT_PARSER_GUIDE.md](../../docs/06-features/EDT_PARSER_GUIDE.md)
- [docs/research/bsl_language_server_plan.md](../../docs/research/bsl_language_server_plan.md)
