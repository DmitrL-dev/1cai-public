
#!/usr/bin/env python3
"""
Комплексное тестирование EDT-Parser
Проверяет все основные функции парсера
"""

import sys
import time
from pathlib import Path

from edt_parser import EDTConfigurationParser


def test_common_modules(parser, limit=50):
    """Тест парсинга общих модулей"""
    print("\n" + "=" * 80)
    print("ТЕСТ 1: ПАРСИНГ ОБЩИХ МОДУЛЕЙ")
    print("=" * 80)
    print(f"Лимит: {limit} модулей\n")
    
    start_time = time.time()
    results = parser.parse_common_modules(limit=limit)
    elapsed = time.time() - start_time
    
    print(f"\n[OK] Завершено за {elapsed:.2f} секунд")
    print(f"Обработано модулей: {len(results)}")
    print(f"Функций: {parser.stats['functions']}")
    print(f"Процедур: {parser.stats['procedures']}")
    
    # Анализ результатов
    if results:
        total_code_size = sum(m['code_length'] for m in results)
        avg_code_size = total_code_size / len(results)
        max_code_module = max(results, key=lambda m: m['code_length'])
        
        print(f"\nСтатистика кода:")
        print(f"  Общий размер: {total_code_size:,} символов")
        print(f"  Средний размер: {avg_code_size:,.0f} символов")
        print(f"  Самый большой: {max_code_module['name']} ({max_code_module['code_length']:,} символов)")
        
        # Примеры
        print("\nПримеры модулей (первые 5):")
        for i, module in enumerate(results[:5], 1):
            print(f"\n  {i}. {module['name']}")
            print(f"     Функций: {module['functions_count']}")
            print(f"     Процедур: {module['procedures_count']}")
            print(f"     Размер: {module['code_length']:,} символов")
            if module.get('functions'):
                func_names = [f['name'] for f in module['functions'][:3]]
                print(f"     Функции: {', '.join(func_names)}")
    
    return {
        'test': 'common_modules',
        'passed': len(results) > 0,
        'modules': len(results),
        'functions': parser.stats['functions'],
        'procedures': parser.stats['procedures'],
        'time': elapsed
    }

def test_catalogs(parser, limit=20):
    """Тест парсинга справочников"""
    print("\n" + "=" * 80)
    print("ТЕСТ 2: ПАРСИНГ СПРАВОЧНИКОВ")
    print("=" * 80)
    print(f"Лимит: {limit} справочников\n")
    
    start_time = time.time()
    results = parser.parse_catalogs(limit=limit)
    elapsed = time.time() - start_time
    
    print(f"\n[OK] Завершено за {elapsed:.2f} секунд")
    print(f"Обработано справочников: {len(results)}")
    
    # Анализ
    if results:
        with_manager = sum(1 for c in results if c.get('manager_module'))
        with_object = sum(1 for c in results if c.get('object_module'))
        with_metadata = sum(1 for c in results if c.get('metadata'))
        
        print(f"\nСтатистика:")
        print(f"  С модулем менеджера: {with_manager}")
        print(f"  С модулем объекта: {with_object}")
        print(f"  С метаданными: {with_metadata}")
        
        # Примеры
        print("\nПримеры справочников (первые 5):")
        for i, catalog in enumerate(results[:5], 1):
            print(f"\n  {i}. {catalog['name']}")
            print(f"     Модуль менеджера: {'+' if catalog.get('manager_module') else '-'}")
            print(f"     Модуль объекта: {'+' if catalog.get('object_module') else '-'}")
            if catalog.get('manager_module'):
                mm = catalog['manager_module']
                print(f"     Функций в менеджере: {mm.get('functions_count', 0)}")
    
    return {
        'test': 'catalogs',
        'passed': len(results) > 0,
        'catalogs': len(results),
        'with_modules': with_manager + with_object,
        'time': elapsed
    }

def test_documents(parser, limit=20):
    """Тест парсинга документов"""
    print("\n" + "=" * 80)
    print("ТЕСТ 3: ПАРСИНГ ДОКУМЕНТОВ")
    print("=" * 80)
    print(f"Лимит: {limit} документов\n")
    
    start_time = time.time()
    results = parser.parse_documents(limit=limit)
    elapsed = time.time() - start_time
    
    print(f"\n[OK] Завершено за {elapsed:.2f} секунд")
    print(f"Обработано документов: {len(results)}")
    
    # Анализ
    if results:
        with_manager = sum(1 for d in results if d.get('manager_module'))
        with_object = sum(1 for d in results if d.get('object_module'))
        with_metadata = sum(1 for d in results if d.get('metadata'))
        
        print(f"\nСтатистика:")
        print(f"  С модулем менеджера: {with_manager}")
        print(f"  С модулем объекта: {with_object}")
        print(f"  С метаданными: {with_metadata}")
        
        # Примеры
        print("\nПримеры документов (первые 5):")
        for i, doc in enumerate(results[:5], 1):
            print(f"\n  {i}. {doc['name']}")
            print(f"     Модуль менеджера: {'+' if doc.get('manager_module') else '-'}")
            print(f"     Модуль объекта: {'+' if doc.get('object_module') else '-'}")
            if doc.get('object_module'):
                om = doc['object_module']
                print(f"     Функций в объекте: {om.get('functions_count', 0)}")
    
    return {
        'test': 'documents',
        'passed': len(results) > 0,
        'documents': len(results),
        'with_modules': with_manager + with_object,
        'time': elapsed
    }

def test_performance(parser):
    """Тест производительности"""
    print("\n" + "=" * 80)
    print("ТЕСТ 4: ПРОИЗВОДИТЕЛЬНОСТЬ")
    print("=" * 80)
    
    tests = [
        ("10 модулей", 10),
        ("50 модулей", 50),
        ("100 модулей", 100)
    ]
    
    results = []
    
    for test_name, limit in tests:
        print(f"\nТест: {test_name}")
        
        # Сброс статистики
        parser.stats.clear()
        parser.errors.clear()
        
        start_time = time.time()
        modules = parser.parse_common_modules(limit=limit)
        elapsed = time.time() - start_time
        
        rate = len(modules) / elapsed if elapsed > 0 else 0
        
        print(f"  Время: {elapsed:.2f} сек")
        print(f"  Скорость: {rate:.2f} модулей/сек")
        
        results.append({
            'test': test_name,
            'limit': limit,
            'processed': len(modules),
            'time': elapsed,
            'rate': rate
        })
    
    return {
        'test': 'performance',
        'passed': True,
        'results': results
    }

def test_error_handling(parser):
    """Тест обработки ошибок"""
    print("\n" + "=" * 80)
    print("ТЕСТ 5: ОБРАБОТКА ОШИБОК")
    print("=" * 80)
    
    # Сброс ошибок
    parser.errors.clear()
    
    # Парсим всю конфигурацию (без лимита)
    print("\nПарсинг всех модулей (для выявления ошибок)...")
    results = parser.parse_common_modules(limit=500)
    
    print(f"\nОбработано модулей: {len(results)}")
    print(f"Ошибок: {len(parser.errors)}")
    
    if parser.errors:
        print("\nПримеры ошибок (первые 5):")
        for i, error in enumerate(parser.errors[:5], 1):
            print(f"  {i}. {error}")
    else:
        print("\n[OK] Ошибок не обнаружено!")
    
    return {
        'test': 'error_handling',
        'passed': len(parser.errors) < len(results) * 0.1,  # < 10% ошибок
        'errors': len(parser.errors),
        'modules': len(results)
    }

def main():
    """Главная функция тестирования"""
    print("=" * 80)
    print("КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ EDT-PARSER")
    print("=" * 80)
    
    # Путь к конфигурации
    project_root = Path(__file__).parent.parent.parent.parent
    edt_path = project_root / "1c_configurations" / "ERPCPM"
    
    if not edt_path.exists():
        print(f"[ERROR] Конфигурация не найдена: {edt_path}")
        return 1
    
    print(f"\nКонфигурация: {edt_path}")
    
    # Создаем парсер
    parser = EDTConfigurationParser(edt_path)
    
    # Запускаем тесты
    test_results = []
    
    try:
        # Тест 1: Общие модули
        result1 = test_common_modules(parser, limit=50)
        test_results.append(result1)
        
        # Сброс статистики
        parser.stats.clear()
        parser.errors.clear()
        
        # Тест 2: Справочники
        result2 = test_catalogs(parser, limit=20)
        test_results.append(result2)
        
        # Сброс статистики
        parser.stats.clear()
        parser.errors.clear()
        
        # Тест 3: Документы
        result3 = test_documents(parser, limit=20)
        test_results.append(result3)
        
        # Сброс статистики
        parser.stats.clear()
        parser.errors.clear()
        
        # Тест 4: Производительность
        result4 = test_performance(parser)
        test_results.append(result4)
        
        # Сброс статистики
        parser.stats.clear()
        parser.errors.clear()
        
        # Тест 5: Обработка ошибок
        result5 = test_error_handling(parser)
        test_results.append(result5)
        
    except Exception as e:
        print(f"\n[ERROR] Ошибка во время тестирования: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Итоговый отчет
    print("\n" + "=" * 80)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 80)
    
    passed = sum(1 for r in test_results if r.get('passed', False))
    total = len(test_results)
    
    print(f"\nПройдено тестов: {passed}/{total}")
    
    for result in test_results:
        status = "[+] PASS" if result.get('passed', False) else "[-] FAIL"
        print(f"\n{status} {result['test']}")
        for key, value in result.items():
            if key not in ['test', 'passed']:
                print(f"  {key}: {value}")
    
    # Сохраняем результаты
    output_dir = project_root / "output" / "edt_parser"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "comprehensive_test_results.json"
    
    import json
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n[+] Результаты сохранены: {output_file}")
    
    print("\n" + "=" * 80)
    if passed == total:
        print("[SUCCESS] ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print(f"[FAILED] НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ ({total - passed}/{total})")
    print("=" * 80)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())

