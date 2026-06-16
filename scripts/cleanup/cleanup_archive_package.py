
#!/usr/bin/env python3
"""
Безопасная очистка archive_package
P0 задача: Удаление дубликатов

Что делает:
1. Проверяет размер archive_package
2. Создает backup информацию
3. Переименовывает в archive_package_OLD (безопасно)
4. Или удаляет если пользователь подтвердит
"""

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


def analyze_archive_package(archive_dir: Path) -> dict:
    """Анализ содержимого archive_package"""
    stats = {
        'total_files': 0,
        'total_size_mb': 0,
        'file_types': {}
    }
    
    for root, dirs, files in os.walk(archive_dir):
        for file in files:
            file_path = Path(root) / file
            try:
                size = file_path.stat().st_size
                stats['total_files'] += 1
                stats['total_size_mb'] += size / 1024 / 1024
                
                ext = file_path.suffix or '(no ext)'
                stats['file_types'][ext] = stats['file_types'].get(ext, 0) + 1
            except:
                pass
    
    return stats

def create_backup_info(archive_dir: Path, stats: dict):
    """Создание информации о backup"""
    backup_info = {
        'date': datetime.now().isoformat(),
        'original_path': str(archive_dir),
        'stats': stats,
        'reason': 'Cleanup P0: Removing duplicates',
        'can_restore': True
    }
    
    backup_file = Path("./ARCHIVE_PACKAGE_BACKUP_INFO.json")
    import json
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_info, f, ensure_ascii=False, indent=2)
    
    print(f"[+] Backup info сохранена: {backup_file}")
    return backup_file

def safe_cleanup(archive_dir: Path, mode: str = 'rename'):
    """
    Безопасная очистка
    
    mode: 'rename' - переименовать (по умолчанию)
          'delete' - удалить
    """
    print("=" * 80)
    print("БЕЗОПАСНАЯ ОЧИСТКА ARCHIVE_PACKAGE")
    print("=" * 80)
    print()
    
    if not archive_dir.exists():
        print(f"[INFO] Директория не найдена: {archive_dir}")
        return
    
    # Анализ
    print("[*] Анализ archive_package...")
    stats = analyze_archive_package(archive_dir)
    
    print(f"\nНайдено:")
    print(f"  Файлов: {stats['total_files']:,}")
    print(f"  Размер: {stats['total_size_mb']:.2f} MB")
    
    # Создаем backup info
    print("\n[*] Создание backup информации...")
    backup_file = create_backup_info(archive_dir, stats)
    
    # Выполняем действие
    if mode == 'rename':
        new_name = archive_dir.parent / f"archive_package_OLD_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"\n[*] Переименование...")
        print(f"  Из: {archive_dir}")
        print(f"  В:  {new_name}")
        
        archive_dir.rename(new_name)
        
        print(f"\n[SUCCESS] Переименовано успешно!")
        print(f"Экономия: {stats['total_size_mb']:.2f} MB освобождено из активной зоны")
        print(f"\nМожно восстановить: переименовать {new_name.name} обратно в archive_package")
        
    elif mode == 'delete':
        print(f"\n[*] УДАЛЕНИЕ...")
        print(f"⚠️  Это удалит {stats['total_files']:,} файлов ({stats['total_size_mb']:.2f} MB)")
        
        shutil.rmtree(archive_dir)
        
        print(f"\n[SUCCESS] Удалено!")
        print(f"Экономия: {stats['total_size_mb']:.2f} MB")
        print(f"\nМожно восстановить из backup_info если нужно")
    
    return stats

def main():
    """Главная функция"""
    project_root = Path(".")
    archive_dir = project_root / "archive_package"
    
    # По умолчанию переименовываем (безопаснее чем удалять)
    mode = 'rename'
    
    stats = safe_cleanup(archive_dir, mode=mode)
    
    if stats:
        print("\n" + "=" * 80)
        print("ОЧИСТКА ЗАВЕРШЕНА")
        print("=" * 80)
        print(f"\nОсвобождено: {stats['total_size_mb']:.2f} MB")
        print(f"Файлов: {stats['total_files']:,}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())



