
#!/usr/bin/env python3
"""Проверка результатов парсинга всех конфигураций"""

import json
import sys
from pathlib import Path

# Устанавливаем кодировку для вывода
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("ИТОГОВАЯ СТАТИСТИКА ПАРСИНГА КОНФИГУРАЦИЙ")
print("=" * 70)

configs = {
    'DO': 'Документооборот 3',
    'ERP': 'ERP Управление предприятием 2',
    'ZUP': 'Зарплата и управление персоналом',
    'BUH': 'Бухгалтерия предприятия'
}

kb_dir = Path('./knowledge_base')
total_modules = 0
total_functions = 0

for config_key, config_name in configs.items():
    kb_file = kb_dir / f"{config_key.lower()}.json"
    
    if kb_file.exists():
        try:
            data = json.loads(kb_file.read_text(encoding='utf-8'))
            modules = data.get('modules', [])
            
            # Подсчет функций
            func_count = 0
            for m in modules:
                if 'documentation' in m and 'functions' in m['documentation']:
                    func_count += len(m['documentation'].get('functions', []))
            
            total_modules += len(modules)
            total_functions += func_count
            
            print(f"\n{config_key} - {config_name}")
            print(f"  ✅ Модулей: {len(modules):,}")
            print(f"  ✅ Функций: {func_count:,}")
            
            # Топ-3 модуля
            modules_with_funcs = []
            for m in modules:
                if 'documentation' in m and 'functions' in m['documentation']:
                    f_count = len(m['documentation'].get('functions', []))
                    if f_count > 0:
                        modules_with_funcs.append((m['name'], f_count))
            
            if modules_with_funcs:
                modules_with_funcs.sort(key=lambda x: x[1], reverse=True)
                print(f"  Топ-3 модуля:")
                for i, (name, count) in enumerate(modules_with_funcs[:3], 1):
                    print(f"    {i}. {name}: {count} функций")
        except Exception as e:
            print(f"\n{config_key} - {config_name}")
            print(f"  ❌ Ошибка чтения: {e}")
    else:
        print(f"\n{config_key} - {config_name}")
        print(f"  ⚠️  Не найдена база знаний")

print(f"\n{'='*70}")
print(f"ВСЕГО:")
print(f"  Конфигураций: {len([f for f in kb_dir.glob('*.json') if f.stem in ['do', 'erp', 'zup', 'buh']])}")
print(f"  Модулей: {total_modules:,}")
print(f"  Функций: {total_functions:,}")
print(f"{'='*70}")





