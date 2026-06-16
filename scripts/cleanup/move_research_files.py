
#!/usr/bin/env python3
"""Перемещение исследовательских/отчетных файлов из корня"""

import shutil
from pathlib import Path

# Исследовательские файлы (можно переместить в docs/)
research_files = [
    '1C_PARSER_OPTIMIZATION_RESEARCH.md',
    'ADVANCED_PARSER_RESEARCH.md',
    'AIRFLOW_DETAILED_COMPARISON.md',
    'AIRFLOW_VS_CURRENT_COMPARISON.md',
    'ARCHITECTURE_UPDATE_INSTRUCTIONS.md',
    'COMPARISON_INDEX.md',
    'COMPLETE_RESEARCH_REPORT.md',
    'DOCS_INDEX.md',
    'FAQ.md',
    'FILES_CREATED_LIST.md',
    'FULL_TECHNOLOGY_STACK_COMPARISON.md',
    'GETTING_STARTED.md',
    'GREENPLUM_COMPARISON.md',
    'IMPLEMENTATION_COMPLETE.md',
    'INNOVATIVE_APPROACH_FINAL.md',
    'INNOVATIVE_PARSER_ARCHITECTURE.md',
    'INTEGRATION_COMPLETE.md',
    'LICENSE_AUDIT_REPORT.md',
    'NEXT_GEN_PARSER_RESEARCH.md',
    'PARSER_MASTER_RESEARCH.md',
    'PARSER_RESEARCH_INDEX.md',
    'PLAN_QUALITY_DATA_EXTRACTION.md',
    'PROJECT_STATUS.md',
    'QUICK_START_OPTIMIZATION.md',
    'README_PARSER_RESEARCH.md',
    'README_REAL_RESULTS.md',
    'RESUME_IT_DIRECTOR_UPDATED.md',
    'RESUME_IT_DIRECTOR.md',
    'RESUME_UPDATE_RECOMMENDATIONS.md',
    'ROADMAP_INDEX.md',
    'ROADMAP_V4_DETAILED.md',
    'ROADMAP_VISUAL.md',
    'ROADMAP.md',
    'ROOT_CLEANUP_COMPLETE.md',
    'ROOT_CLEANUP_PLAN.md',
    'START_HERE.md',
    'TELEGRAM_SETUP.md',
    'БЫСТРЫЙ_СТАРТ.md',
    'МЕГА_ОТЧЕТ_ИССЛЕДОВАНИЯ.md',
    'НОВЫЙ_ФОКУС_КАЧЕСТВО_ДАННЫХ.md',
    'ОЖИДАНИЕ_ДАННЫХ.md',
    'ПРАКТИЧНЫЙ_ПЛАН_УЛУЧШЕНИЙ.md',
    'РЕАЛЬНЫЕ_ИЗМЕРЕНИЯ.md',
    'ФИНАЛЬНЫЙ_ОТЧЕТ_С_ДАННЫМИ.md',
    'DISCLAIMER_ДЛЯ_README.md'
]

# Временные/служебные файлы (можно удалить или переместить)
temp_files = [
    'baseline_performance.txt',
    'ENV_EXAMPLE.txt',
    'PROJECT_COMPLETED.txt',
    'run_optimization.bat',
    'run_optimization.sh',
    'Architecture_Connections_Diagram.png',
    'ARCHIVE_PACKAGE_BACKUP_INFO.json',
    '.gitignore.recommended'
]

def move_to_docs():
    """Перемещение в docs/research"""
    target = Path("docs/research")
    target.mkdir(parents=True, exist_ok=True)
    
    moved = 0
    for filename in research_files:
        source = Path(filename)
        if source.exists():
            dest = target / filename
            shutil.move(str(source), str(dest))
            moved += 1
    
    return moved

def move_temp_files():
    """Перемещение временных в docs/temp"""
    target = Path("docs/temp")
    target.mkdir(parents=True, exist_ok=True)
    
    moved = 0
    for filename in temp_files:
        source = Path(filename)
        if source.exists():
            dest = target / filename
            shutil.move(str(source), str(dest))
            moved += 1
    
    return moved

def main():
    print("Очистка корневой папки...")
    print()
    
    # Перемещаем исследовательские файлы
    print("[*] Перемещение исследовательских файлов в docs/research...")
    moved_research = move_to_docs()
    print(f"    Перемещено: {moved_research} файлов")
    
    # Перемещаем временные файлы
    print("\n[*] Перемещение временных файлов в docs/temp...")
    moved_temp = move_temp_files()
    print(f"    Перемещено: {moved_temp} файлов")
    
    # Проверяем сколько осталось
    root_files_after = len([f for f in Path('.').iterdir() if f.is_file()])
    
    print()
    print("=" * 80)
    print(f"Всего перемещено: {moved_research + moved_temp} файлов")
    print(f"Осталось в корне: {root_files_after} файлов")
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())



