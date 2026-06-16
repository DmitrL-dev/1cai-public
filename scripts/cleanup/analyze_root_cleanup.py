
#!/usr/bin/env python3
"""
Анализ корневой папки для очистки
Проверка что нужно, а что можно удалить/переместить
"""

import sys
from pathlib import Path


def analyze_root_files():
    """Анализ файлов в корне"""
    project_root = Path(".")
    
    print("=" * 80)
    print("АНАЛИЗ КОРНЕВОЙ ПАПКИ ПРОЕКТА")
    print("=" * 80)
    print()
    
    # Получаем все файлы в корне
    root_files = [f for f in project_root.iterdir() if f.is_file()]
    
    print(f"Всего файлов в корне: {len(root_files)}")
    print()
    
    # Категоризация
    categories = {
        'essential': [],          # Необходимые
        'config': [],            # Конфигурационные
        'documentation': [],     # Документация (отчеты)
        'temporary': [],         # Временные/отчеты сессии
        'unknown': []            # Неизвестные
    }
    
    # Необходимые файлы
    essential_files = {
        'README.md', 'LICENSE', '.gitignore', 'Makefile',
        'requirements.txt', 'pytest.ini', 'alembic.ini',
        'docker-compose.yml'
    }
    
    # Паттерны для категоризации
    for file in root_files:
        name = file.name
        
        if name in essential_files or name.startswith('requirements') or name.startswith('docker-compose') or name.startswith('Dockerfile'):
            categories['essential'].append((name, file.stat().st_size / 1024))
        
        elif name.endswith('.ini') or name.endswith('.yml') or name.endswith('.yaml'):
            categories['config'].append((name, file.stat().st_size / 1024))
        
        elif name.endswith('.md') or name.endswith('.txt'):
            # Проверяем на временные отчеты
            temp_keywords = ['ОТЧЕТ', 'SUMMARY', 'РЕЗУЛЬТАТ', 'АНАЛИЗ', 'АУДИТ', 
                           'ЗАВЕРШЕН', 'ГОТОВ', 'ФИНАЛЬНЫЙ', 'ПОЛНЫЙ', 'ВИЗУАЛЬНАЯ',
                           'ШАГИ', 'ПАРСИНГ', 'СПИСОК', 'СВОДКА', 'ПЛАН', 'ЗАДАЧИ']
            
            if any(keyword in name.upper() for keyword in temp_keywords):
                categories['temporary'].append((name, file.stat().st_size / 1024))
            elif name in ['README.md', 'LICENSE', 'CONTRIBUTING.md', 'CHANGELOG.md']:
                categories['essential'].append((name, file.stat().st_size / 1024))
            else:
                categories['documentation'].append((name, file.stat().st_size / 1024))
        
        else:
            categories['unknown'].append((name, file.stat().st_size / 1024))
    
    # Вывод результатов
    for category, files in categories.items():
        if not files:
            continue
        
        total_size = sum(size for _, size in files)
        print(f"\n{'='*80}")
        print(f"{category.upper()}: {len(files)} файлов ({total_size:.2f} KB)")
        print(f"{'='*80}")
        
        for name, size in sorted(files, key=lambda x: x[1], reverse=True):
            print(f"  {name:<70} {size:>8.2f} KB")
    
    # Рекомендации
    print("\n" + "=" * 80)
    print("РЕКОМЕНДАЦИИ ПО ОЧИСТКЕ")
    print("=" * 80)
    
    temp_files = categories['temporary']
    if temp_files:
        total_temp = sum(size for _, size in temp_files)
        print(f"\nТЕМПОРАРНЫЕ/ОТЧЕТЫ СЕССИИ: {len(temp_files)} файлов ({total_temp:.2f} KB)")
        print("РЕКОМЕНДАЦИЯ: Переместить в docs/reports/ или удалить")
        print("\nФайлы:")
        for name, size in temp_files:
            print(f"  - {name}")
    
    # Генерация команд очистки
    return categories

def generate_cleanup_plan(categories):
    """Генерация плана очистки"""
    print("\n" + "=" * 80)
    print("ПЛАН ОЧИСТКИ")
    print("=" * 80)
    
    temp_files = categories['temporary']
    
    if temp_files:
        print("\nШаг 1: Создать папку для отчетов")
        print("  mkdir -p docs/reports/session_2025_11_06")
        
        print("\nШаг 2: Переместить временные файлы")
        for name, _ in temp_files:
            print(f"  mv '{name}' docs/reports/session_2025_11_06/")
        
        print(f"\nЭкономия: {len(temp_files)} файлов уберутся из корня")
    
    return temp_files

def main():
    """Главная функция"""
    categories = analyze_root_files()
    temp_files = generate_cleanup_plan(categories)
    
    # Сохранение отчета
    output_dir = Path("./output/audit")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    import json
    with open(output_dir / "root_cleanup_analysis.json", 'w', encoding='utf-8') as f:
        json.dump({
            'total_files': sum(len(files) for files in categories.values()),
            'categories': {k: len(v) for k, v in categories.items()},
            'temporary_files': [name for name, _ in categories['temporary']],
            'recommendation': f'Move {len(temp_files)} temporary files to docs/reports/'
        }, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 80)
    print(f"Отчет сохранен: {output_dir / 'root_cleanup_analysis.json'}")
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())



