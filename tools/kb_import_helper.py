
#!/usr/bin/env python3
"""
Помощник для импорта данных в базу знаний
Версия: 1.0.0
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.configuration_knowledge_base import get_knowledge_base


def import_from_file(file_path: str, config_name: str):
    """Импорт из JSON файла"""
    kb = get_knowledge_base()
    
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"[ERROR] Файл не найден: {file_path}")
        return
    
    print(f"[INFO] Чтение файла: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    imported_modules = 0
    imported_practices = 0
    
    # Импортируем модули
    for module_data in data.get("modules", []):
        try:
            kb.add_module_documentation(
                config_name=config_name.lower(),
                module_name=module_data.get("name", "Unknown"),
                documentation={
                    "description": module_data.get("description", ""),
                    "code": module_data.get("code", ""),
                    "functions": module_data.get("functions", []),
                    "object_type": module_data.get("object_type"),
                    "object_name": module_data.get("object_name"),
                    "module_type": module_data.get("module_type"),
                    "source": data.get("source", "cli_import")
                }
            )
            imported_modules += 1
            print(f"  [OK] Модуль: {module_data.get('name', 'Unknown')}")
        except Exception as e:
            print(f"  [ERROR] Ошибка импорта модуля: {e}")
    
    # Импортируем best practices
    for practice_data in data.get("best_practices", []):
        try:
            kb.add_best_practice(
                config_name=config_name.lower(),
                category=practice_data.get("category", "general"),
                practice={
                    "title": practice_data.get("title", ""),
                    "description": practice_data.get("description", ""),
                    "code_examples": practice_data.get("code_examples", []),
                    "tags": practice_data.get("tags", []),
                    "source": data.get("source", "cli_import")
                }
            )
            imported_practices += 1
            print(f"  [OK] Practice: {practice_data.get('title', 'Unknown')}")
        except Exception as e:
            print(f"  [ERROR] Ошибка импорта practice: {e}")
    
    print("\n" + "=" * 70)
    print("ИТОГИ ИМПОРТА:")
    print("=" * 70)
    print(f"Конфигурация: {config_name}")
    print(f"Импортировано модулей: {imported_modules}")
    print(f"Импортировано best practices: {imported_practices}")
    print("=" * 70)


def create_template(output_path: str, config_name: str = "erp"):
    """Создание шаблона для импорта"""
    template = {
        "source": "manual",
        "config_name": config_name,
        "modules": [
            {
                "name": "ОбщийМодуль_Пример",
                "description": "Описание модуля",
                "code": "// Пример кода BSL\nФункция ПримерФункции(Параметр)\n\tВозврат Истина;\nКонецФункции",
                "functions": [
                    {
                        "name": "ПримерФункции",
                        "type": "Функция",
                        "params": ["Параметр"],
                        "description": "Описание функции",
                        "code_snippet": "Функция ПримерФункции(Параметр)\n\tВозврат Истина;\nКонецФункции"
                    }
                ],
                "object_type": "CommonModule",
                "object_name": "Пример",
                "module_type": "Module"
            }
        ],
        "best_practices": [
            {
                "title": "Пример Best Practice",
                "description": "Подробное описание best practice",
                "category": "performance",
                "code_examples": [
                    "// Пример кода\nЗапрос.УстановитьПараметр(\"Лимит\", 100);"
                ],
                "tags": ["performance", "query", "optimization"]
            }
        ]
    }
    
    output_path = Path(output_path)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] Шаблон создан: {output_path}")
    print(f"[INFO] Заполните шаблон и импортируйте командой:")
    print(f"  python tools/kb_import_helper.py --import {output_path} --config {config_name}")


def main():
    parser = argparse.ArgumentParser(description="Помощник для импорта данных в базу знаний")
    parser.add_argument('--import', dest='import_file', help='Файл для импорта (JSON)')
    parser.add_argument('--config', default='erp', help='Название конфигурации')
    parser.add_argument('--template', help='Создать шаблон (укажите путь к файлу)')
    parser.add_argument('--list', action='store_true', help='Показать список конфигураций')
    
    args = parser.parse_args()
    
    if args.template:
        create_template(args.template, args.config)
    elif args.import_file:
        import_from_file(args.import_file, args.config)
    elif args.list:
        kb = get_knowledge_base()
        print("Доступные конфигурации:")
        for config in kb.SUPPORTED_CONFIGURATIONS:
            config_info = kb.get_configuration_info(config)
            config_name = config_info.get("name", config) if config_info else config
            modules_count = len(config_info.get("modules", [])) if config_info else 0
            practices_count = len(config_info.get("best_practices", [])) if config_info else 0
            print(f"  - {config}: {config_name}")
            if modules_count > 0 or practices_count > 0:
                print(f"    Модулей: {modules_count}, Best practices: {practices_count}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

