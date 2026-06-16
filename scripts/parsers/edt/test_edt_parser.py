
#!/usr/bin/env python3
"""
Тестирование EDT-Parser на первых 100 модулях
"""

import sys
from pathlib import Path

from edt_parser import EDTConfigurationParser


def main():
    """Тестирование парсера"""
    # Путь относительно корня проекта
    project_root = Path(__file__).parent.parent.parent.parent
    edt_path = project_root / "1c_configurations" / "ERPCPM"
    
    if not edt_path.exists():
        print(f"[ERROR] Папка не найдена: {edt_path}")
        return 1
    
    # Создаем парсер
    parser = EDTConfigurationParser(edt_path)
    
    # Тест: парсим первые 100 модулей
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ EDT-PARSER")
    print("=" * 80)
    print("Парсинг первых 100 общих модулей...\n")
    
    results = parser.parse_common_modules(limit=100)
    
    # Выводим статистику
    print("\n" + "=" * 80)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 80)
    print(f"Обработано модулей: {len(results)}")
    print(f"Найдено функций: {parser.stats['functions']}")
    print(f"Найдено процедур: {parser.stats['procedures']}")
    print(f"Ошибок: {len(parser.errors)}")
    
    if results:
        print("\nПримеры модулей:")
        for i, module in enumerate(results[:5], 1):
            print(f"\n  {i}. {module['name']}")
            print(f"     Функций: {module['functions_count']}")
            print(f"     Процедур: {module['procedures_count']}")
            print(f"     Размер кода: {module['code_length']:,} символов")
            if module.get('functions'):
                print(f"     Пример функции: {module['functions'][0]['name']}")
    
    # Сохраняем результаты
    project_root = Path(__file__).parent.parent.parent.parent
    output_dir = project_root / "output" / "edt_parser"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "test_100_modules.json"
    
    test_results = {
        'test_mode': True,
        'limit': 100,
        'common_modules': results,
        'stats': dict(parser.stats),
        'errors': parser.errors
    }
    
    parser.save_results(test_results, output_file)
    
    print("\n" + "=" * 80)
    print("[SUCCESS] ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 80)
    print(f"Результаты: {output_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

