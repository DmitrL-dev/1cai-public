
#!/usr/bin/env python3
"""
Проверка актуальности архитектурных файлов
"""

import json
from datetime import datetime
from pathlib import Path


def check_architecture_files():
    """Проверка архитектурных файлов"""
    print("=" * 80)
    print("ПРОВЕРКА АКТУАЛЬНОСТИ АРХИТЕКТУРНЫХ ФАЙЛОВ")
    print("=" * 80)
    print()
    
    # Список архитектурных файлов
    arch_dirs = [
        "docs/architecture",
        "docs/02-architecture",
        "analysis/project_architecture"
    ]
    
    # Новые компоненты добавленные 6 ноября
    new_components = [
        "scripts/parsers/edt/edt_parser.py",
        "scripts/parsers/edt/edt_parser_with_metadata.py",
        "scripts/analysis/analyze_architecture.py",
        "scripts/dataset/create_ml_dataset.py",
        "scripts/analysis/analyze_dependencies.py",
        "scripts/analysis/analyze_data_types.py",
        "scripts/analysis/extract_best_practices.py",
        "scripts/analysis/generate_documentation.py",
        "scripts/audit/project_structure_audit.py",
        "scripts/audit/code_quality_audit.py",
        "scripts/audit/architecture_audit.py",
        "scripts/audit/comprehensive_project_audit.py"
    ]
    
    # Проверяем архитектурные файлы
    arch_files = []
    for arch_dir in arch_dirs:
        dir_path = Path(arch_dir)
        if dir_path.exists():
            for file in dir_path.rglob("*.md"):
                arch_files.append(file)
    
    print(f"Найдено архитектурных файлов: {len(arch_files)}")
    print()
    
    # Группируем по дате
    today = datetime.now().date()
    
    outdated = []
    recent = []
    
    for file in arch_files:
        mtime = datetime.fromtimestamp(file.stat().st_mtime)
        age_days = (datetime.now() - mtime).days
        
        file_info = {
            'path': str(file),
            'modified': mtime.strftime("%Y-%m-%d %H:%M:%S"),
            'age_days': age_days,
            'size_kb': file.stat().st_size / 1024
        }
        
        if age_days >= 1:
            outdated.append(file_info)
        else:
            recent.append(file_info)
    
    # Вывод
    if outdated:
        print(f"\n[!] УСТАРЕВШИЕ ФАЙЛЫ (старше 1 дня): {len(outdated)}")
        print("-" * 80)
        for f in sorted(outdated, key=lambda x: x['age_days'], reverse=True):
            print(f"  {f['path']}")
            print(f"    Изменен: {f['modified']} ({f['age_days']} дней назад)")
            print()
    
    if recent:
        print(f"\n[OK] АКТУАЛЬНЫЕ ФАЙЛЫ (менее 1 дня): {len(recent)}")
        print("-" * 80)
        for f in recent:
            print(f"  {f['path']} (изменен: {f['modified']})")
    
    # Проверяем упоминание новых компонентов
    print("\n" + "=" * 80)
    print("ПРОВЕРКА УПОМИНАНИЯ НОВЫХ КОМПОНЕНТОВ")
    print("=" * 80)
    
    keywords = [
        'EDT-Parser', 'edt_parser', 'edt_parser_with_metadata',
        'analyze_architecture', 'create_ml_dataset', 
        'analyze_dependencies', 'analyze_data_types',
        'extract_best_practices', 'generate_documentation',
        'project_structure_audit', 'code_quality_audit',
        'architecture_audit', 'comprehensive_project_audit'
    ]
    
    mentioned = {}
    
    for file in arch_files:
        content = file.read_text(encoding='utf-8', errors='ignore')
        found_keywords = [kw for kw in keywords if kw in content]
        if found_keywords:
            mentioned[str(file)] = found_keywords
    
    if mentioned:
        print("\n[OK] Файлы с упоминанием новых компонентов:")
        for file, kws in mentioned.items():
            print(f"\n  {file}:")
            for kw in kws:
                print(f"    - {kw}")
    else:
        print("\n[!] НИ ОДИН архитектурный файл НЕ упоминает новые компоненты!")
    
    # Итоговый вердикт
    print("\n" + "=" * 80)
    print("ВЕРДИКТ")
    print("=" * 80)
    
    total_outdated = len(outdated)
    has_new_components = len(mentioned) > 0
    
    if total_outdated > 0 and not has_new_components:
        print("\n[!] АРХИТЕКТУРА УСТАРЕЛА!")
        print(f"    - {total_outdated} файлов старше 1 дня")
        print("    - Новые компоненты НЕ упомянуты")
        print("\n[РЕКОМЕНДАЦИЯ] Обновить архитектурную документацию")
        status = "OUTDATED"
    elif total_outdated > 0:
        print("\n[~] ЧАСТИЧНО АКТУАЛЬНА")
        print(f"    - {total_outdated} файлов старше 1 дня")
        print("    - Но некоторые новые компоненты упомянуты")
        status = "PARTIALLY_UPDATED"
    else:
        print("\n[OK] АКТУАЛЬНА")
        print("    - Все файлы свежие")
        print("    - Новые компоненты упомянуты")
        status = "UP_TO_DATE"
    
    # Сохранение отчета
    report = {
        'status': status,
        'total_files': len(arch_files),
        'outdated_files': len(outdated),
        'recent_files': len(recent),
        'new_components_mentioned': len(mentioned),
        'outdated_list': [f['path'] for f in outdated],
        'files_with_new_components': list(mentioned.keys())
    }
    
    output_dir = Path("output/audit")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "architecture_files_check.json", 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n[*] Отчет сохранен: {output_dir / 'architecture_files_check.json'}")
    
    return status

def main():
    status = check_architecture_files()
    
    if status == "OUTDATED":
        return 1
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())



