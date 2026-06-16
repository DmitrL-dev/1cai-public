
#!/usr/bin/env python3
"""Перемещение временных файлов из корня в docs/reports/"""

import shutil
from pathlib import Path

# Список временных файлов из анализа
temp_files = [
    'AIRFLOW_DECISION_SUMMARY.md',
    'EDT_PARSER_ГОТОВ.md',
    'FINAL_PRAGMATIC_SUMMARY.md',
    'FINAL_SUMMARY.md',
    'LICENSE_AUDIT_SUMMARY.md',
    'P0_ЗАДАЧИ_ВЫПОЛНЕНЫ.md',
    'PARSER_OPTIMIZATION_SUMMARY.md',
    'RESUME_CHANGES_SUMMARY.md',
    'REVOLUTIONARY_SUMMARY.md',
    'ROADMAP_EXECUTIVE_SUMMARY.md',
    'SESSION_COMPLETE_SUMMARY.md',
    'TECHNOLOGY_COMPARISON_SUMMARY.md',
    'VISUAL_SUMMARY.md',
    'АУДИТ_ЗАВЕРШЕН_SUMMARY.md',
    'ВИЗУАЛЬНАЯ_СВОДКА_РЕЗУЛЬТАТОВ.md',
    'ВСЕ_ШАГИ_ВЫПОЛНЕНЫ.md',
    'НАЧНИТЕ_ОТСЮДА.md',
    'ПЕРЕД_ПУБЛИКАЦИЕЙ_НА_GITHUB.md',
    'ПЛАН_ГЛУБОКОГО_ИССЛЕДОВАНИЯ.md',
    'ПЛАН_ТЩАТЕЛЬНОЙ_ПРОВЕРКИ_ПРОЕКТА.md',
    'ПОЛНЫЙ_АУДИТ_ВИЗУАЛЬНАЯ_СВОДКА.md',
    'ПОЛНЫЙ_АУДИТ_ПРОЕКТА_ФИНАЛЬНЫЙ_ОТЧЕТ.md',
    'ПОЛНЫЙ_ПАРСИНГ_ЗАВЕРШЕН.md',
    'ПРОЕКТ_ЗАВЕРШЕН.txt',
    'РЕЗУЛЬТАТЫ_ГЛУБОКОГО_АНАЛИЗА.md',
    'РЕЗУЛЬТАТЫ_ТЕСТИРОВАНИЯ_EDT_PARSER.md',
    'СПИСОК_ФАЙЛОВ_ПРОЕКТА.txt',
    'СТРУКТУРА_XML_АНАЛИЗ.md',
    'ФИНАЛЬНЫЙ_ОТЧЕТ_EDT_PARSER.md',
    'ФИНАЛЬНЫЙ_ОТЧЕТ_СЕССИИ.md',
    'ФИНАЛЬНЫЙ_SUMMARY.md',
    'ЛИЦЕНЗИОННЫЙ_АУДИТ_КРИТИЧНО.md',
    'ЧЕСТНЫЙ_АНАЛИЗ.md',
    'ИТОГ_РАБОТЫ.md',
    'ИТОГОВЫЙ_ОТЧЕТ_ЧЕСТНЫЙ.md'
]

def main():
    target_dir = Path("docs/reports/session_2025_11_06")
    target_dir.mkdir(parents=True, exist_ok=True)
    
    moved = 0
    not_found = 0
    
    print("Перемещение временных файлов...")
    print()
    
    for filename in temp_files:
        source = Path(filename)
        if source.exists():
            destination = target_dir / filename
            shutil.move(str(source), str(destination))
            print(f"[OK] {filename}")
            moved += 1
        else:
            not_found += 1
    
    print()
    print(f"Перемещено: {moved} файлов")
    print(f"Не найдено: {not_found} файлов")
    print(f"Целевая папка: {target_dir}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

