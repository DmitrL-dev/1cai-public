
#!/usr/bin/env python3
"""
Извлечение best practices из кода
Шаг 5: Извлечение best practices

Анализирует:
- Паттерны кодирования
- Обработка ошибок
- Документирование
- Именование
- Структура кода
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List


def load_parse_results():
    """Загрузка результатов парсинга"""
    results_file = Path("./output/edt_parser/full_parse_with_metadata.json")
    
    print("Загрузка результатов парсинга...")
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Загружено успешно!")
    return data

def analyze_error_handling(data: Dict) -> Dict:
    """Анализ обработки ошибок"""
    print("\n" + "=" * 80)
    print("1. ОБРАБОТКА ОШИБОК")
    print("=" * 80)
    
    total_functions = 0
    with_try_catch = 0
    try_catch_examples = []
    
    # Общие модули
    for module in data.get('common_modules', []):
        for func in module.get('functions', []):
            total_functions += 1
            body = func.get('body', '')
            
            if re.search(r'\bПопытка\b', body, re.IGNORECASE):
                with_try_catch += 1
                if len(try_catch_examples) < 5:
                    try_catch_examples.append({
                        'module': module['name'],
                        'function': func['name']
                    })
    
    pct = with_try_catch / total_functions * 100 if total_functions > 0 else 0
    
    print(f"\nВсего функций проанализировано: {total_functions:,}")
    print(f"С обработкой ошибок (Попытка...Исключение): {with_try_catch:,} ({pct:.1f}%)")
    
    if try_catch_examples:
        print(f"\nПримеры функций с обработкой ошибок:")
        for i, ex in enumerate(try_catch_examples, 1):
            print(f"  {i}. {ex['module']}.{ex['function']}")
    
    return {
        'total_functions': total_functions,
        'with_error_handling': with_try_catch,
        'percentage': pct,
        'examples': try_catch_examples
    }

def analyze_documentation(data: Dict) -> Dict:
    """Анализ документирования кода"""
    print("\n" + "=" * 80)
    print("2. ДОКУМЕНТИРОВАНИЕ")
    print("=" * 80)
    
    total_functions = 0
    with_comments = 0
    export_functions = 0
    export_with_comments = 0
    
    comment_patterns = [
        r'^\s*//\s*Функция',
        r'^\s*//\s*Параметры:',
        r'^\s*//\s*Возвращаемое значение:',
        r'^\s*//\s*Описание:'
    ]
    
    for module in data.get('common_modules', []):
        module_code = module.get('code', '')
        lines = module_code.split('\n')
        
        for i, func in enumerate(module.get('functions', [])):
            total_functions += 1
            
            if func.get('is_export'):
                export_functions += 1
            
            # Проверяем комментарии перед функцией
            # Ищем позицию функции в коде
            func_name = func.get('name', '')
            func_pattern = rf'Функция\s+{re.escape(func_name)}\s*\('
            
            match = re.search(func_pattern, module_code, re.IGNORECASE)
            if match:
                # Берем 10 строк перед функцией
                pos = match.start()
                code_before = module_code[:pos]
                lines_before = code_before.split('\n')[-10:]
                
                # Проверяем наличие документации
                has_doc = False
                for line in lines_before:
                    for pattern in comment_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            has_doc = True
                            break
                    if has_doc:
                        break
                
                if has_doc:
                    with_comments += 1
                    if func.get('is_export'):
                        export_with_comments += 1
    
    pct_all = with_comments / total_functions * 100 if total_functions > 0 else 0
    pct_export = export_with_comments / export_functions * 100 if export_functions > 0 else 0
    
    print(f"\nВсего функций: {total_functions:,}")
    print(f"С документацией: {with_comments:,} ({pct_all:.1f}%)")
    print(f"\nЭкспортных функций: {export_functions:,}")
    print(f"Экспортных с документацией: {export_with_comments:,} ({pct_export:.1f}%)")
    
    return {
        'total_functions': total_functions,
        'with_documentation': with_comments,
        'percentage': pct_all,
        'export_functions': export_functions,
        'export_with_documentation': export_with_comments,
        'export_percentage': pct_export
    }

def analyze_naming_conventions(data: Dict) -> Dict:
    """Анализ соглашений по именованию"""
    print("\n" + "=" * 80)
    print("3. СОГЛАШЕНИЯ ПО ИМЕНОВАНИЮ")
    print("=" * 80)
    
    function_prefixes = Counter()
    procedure_prefixes = Counter()
    
    for module in data.get('common_modules', []):
        for func in module.get('functions', []):
            name = func.get('name', '')
            # Извлекаем первое слово (префикс)
            match = re.match(r'^([А-Яа-яA-Za-z]+)', name)
            if match:
                prefix = match.group(1)
                function_prefixes[prefix] += 1
        
        for proc in module.get('procedures', []):
            name = proc.get('name', '')
            match = re.match(r'^([А-Яа-яA-Za-z]+)', name)
            if match:
                prefix = match.group(1)
                procedure_prefixes[prefix] += 1
    
    print(f"\nТОП-20 префиксов функций:")
    for i, (prefix, count) in enumerate(function_prefixes.most_common(20), 1):
        print(f"  {i:2d}. {prefix:<30} {count:>5} функций")
    
    print(f"\nТОП-20 префиксов процедур:")
    for i, (prefix, count) in enumerate(procedure_prefixes.most_common(20), 1):
        print(f"  {i:2d}. {prefix:<30} {count:>5} процедур")
    
    return {
        'function_prefixes': dict(function_prefixes.most_common(50)),
        'procedure_prefixes': dict(procedure_prefixes.most_common(50))
    }

def analyze_code_patterns(data: Dict) -> Dict:
    """Анализ паттернов кодирования"""
    print("\n" + "=" * 80)
    print("4. ПАТТЕРНЫ КОДИРОВАНИЯ")
    print("=" * 80)
    
    patterns = {
        'query_usage': 0,
        'table_value_usage': 0,
        'structure_usage': 0,
        'array_usage': 0,
        'map_usage': 0,
        'for_each_usage': 0,
        'while_usage': 0,
        'region_usage': 0
    }
    
    pattern_checks = {
        'query_usage': r'\bЗапрос\b',
        'table_value_usage': r'\bТаблицаЗначений\b',
        'structure_usage': r'\bСтруктура\b',
        'array_usage': r'\bМассив\b',
        'map_usage': r'\bСоответствие\b',
        'for_each_usage': r'\bДля\s+Каждого\b',
        'while_usage': r'\bПока\b',
        'region_usage': r'#Область\b'
    }
    
    modules_analyzed = 0
    
    for module in data.get('common_modules', []):
        modules_analyzed += 1
        code = module.get('code', '')
        
        for key, pattern in pattern_checks.items():
            if re.search(pattern, code, re.IGNORECASE):
                patterns[key] += 1
    
    print(f"\nМодулей проанализировано: {modules_analyzed:,}")
    print(f"\nИспользование паттернов:")
    for key, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
        pct = count / modules_analyzed * 100 if modules_analyzed > 0 else 0
        print(f"  {key:<30} {count:>5} модулей ({pct:>5.1f}%)")
    
    return patterns

def extract_best_practices_examples(data: Dict) -> List[Dict]:
    """Извлечение примеров best practices"""
    print("\n" + "=" * 80)
    print("5. ПРИМЕРЫ BEST PRACTICES")
    print("=" * 80)
    
    examples = []
    
    # Ищем хорошо документированные функции
    for module in data.get('common_modules', [])[:50]:
        module_code = module.get('code', '')
        
        for func in module.get('functions', []):
            if not func.get('is_export'):
                continue
            
            func_name = func.get('name', '')
            func_pattern = rf'Функция\s+{re.escape(func_name)}\s*\('
            
            match = re.search(func_pattern, module_code, re.IGNORECASE)
            if not match:
                continue
            
            # Проверяем документацию
            pos = match.start()
            code_before = module_code[:pos]
            lines_before = code_before.split('\n')[-15:]
            
            has_description = False
            has_params = False
            has_return = False
            
            for line in lines_before:
                if re.search(r'//\s*(?:Описание|Description)', line, re.IGNORECASE):
                    has_description = True
                if re.search(r'//\s*Параметры:', line, re.IGNORECASE):
                    has_params = True
                if re.search(r'//\s*Возвращаемое\s+значение:', line, re.IGNORECASE):
                    has_return = True
            
            # Если хорошо документирована
            if has_description and has_params and has_return:
                examples.append({
                    'module': module['name'],
                    'function': func_name,
                    'type': 'well_documented',
                    'has_description': has_description,
                    'has_params': has_params,
                    'has_return': has_return
                })
                
                if len(examples) >= 10:
                    break
        
        if len(examples) >= 10:
            break
    
    print(f"\nНайдено примеров хорошо документированных функций: {len(examples)}")
    for i, ex in enumerate(examples, 1):
        print(f"  {i:2d}. {ex['module']}.{ex['function']}")
    
    return examples

def main():
    """Главная функция"""
    print("=" * 80)
    print("ИЗВЛЕЧЕНИЕ BEST PRACTICES")
    print("=" * 80)
    
    # Загрузка данных
    data = load_parse_results()
    
    # Анализ
    error_handling = analyze_error_handling(data)
    documentation = analyze_documentation(data)
    naming = analyze_naming_conventions(data)
    patterns = analyze_code_patterns(data)
    examples = extract_best_practices_examples(data)
    
    # Сохранение
    output_dir = Path("./output/analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        'error_handling': error_handling,
        'documentation': documentation,
        'naming_conventions': naming,
        'code_patterns': patterns,
        'examples': examples
    }
    
    output_file = output_dir / "best_practices.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print("ИЗВЛЕЧЕНИЕ ЗАВЕРШЕНО!")
    print("=" * 80)
    print(f"\nРезультаты сохранены: {output_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())




