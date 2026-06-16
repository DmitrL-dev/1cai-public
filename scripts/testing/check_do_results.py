
#!/usr/bin/env python3
"""Проверка результатов парсинга конфигурации DO"""

import json
import sys
from pathlib import Path

# Устанавливаем кодировку для вывода
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("РЕЗУЛЬТАТЫ ПАРСИНГА КОНФИГУРАЦИИ DO")
print("=" * 70)

# Проверяем базу знаний
kb_path = Path('./knowledge_base/do.json')
if kb_path.exists():
    data = json.loads(kb_path.read_text(encoding='utf-8'))
    modules = data.get('modules', [])
    
    print(f"\nБаза знаний (do.json):")
    print(f"  Модулей: {len(modules)}")
    print(f"  Best practices: {len(data.get('best_practices', []))}")
    print(f"  Паттернов: {len(data.get('common_patterns', []))}")
    
    # Топ-10 модулей по количеству функций
    print(f"\nТоп-10 модулей по количеству функций:")
    modules_with_funcs = []
    for m in modules:
        if 'documentation' in m and 'functions' in m['documentation']:
            func_count = len(m['documentation'].get('functions', []))
            modules_with_funcs.append((m['name'], func_count))
    
    modules_with_funcs.sort(key=lambda x: x[1], reverse=True)
    for i, (name, count) in enumerate(modules_with_funcs[:10], 1):
        print(f"  {i:2}. {name}: {count} функций")
    
    # Статистика по типам модулей
    print(f"\nСтатистика по типам модулей:")
    module_types = {}
    for m in modules:
        if 'documentation' in m:
            obj_type = m['documentation'].get('object_type', 'Unknown')
            module_types[obj_type] = module_types.get(obj_type, 0) + 1
    
    for obj_type, count in sorted(module_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {obj_type}: {count}")
    
else:
    print(f"\nБаза знаний не найдена: {kb_path}")

print(f"\n{'='*70}")





