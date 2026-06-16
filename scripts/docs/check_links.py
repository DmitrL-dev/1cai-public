
#!/usr/bin/env python3
"""
Скрипт для проверки всех markdown ссылок в проекте.

Проверяет:
- Существование файлов по относительным путям
- Внешние ссылки (http/https) - только отмечает
- Якоря (#) - только отмечает

Использование:
    python scripts/docs/check_links.py [путь_к_файлу_или_директории]
    
Примеры:
    python scripts/docs/check_links.py README.md
    python scripts/docs/check_links.py docs/
    python scripts/docs/check_links.py  # проверяет весь проект
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def extract_links(content: str) -> List[Tuple[str, str]]:
    """Извлекает все markdown ссылки из текста."""
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    return re.findall(pattern, content)


def check_link(link_path: str, base_dir: Path) -> Tuple[bool, str]:
    """
    Проверяет существование файла по ссылке.
    
    Returns:
        (exists, status) где status: 'external', 'anchor', 'file', 'missing'
    """
    # Убираем якоря
    clean_path = link_path.split('#')[0]
    
    if not clean_path:
        return True, 'empty'
    
    # Внешние ссылки
    if clean_path.startswith('http://') or clean_path.startswith('https://'):
        return True, 'external'
    
    # Якоря без пути
    if clean_path.startswith('#'):
        return True, 'anchor'
    
    # Проверяем относительные пути
    full_path = base_dir / clean_path
    
    # Проверяем существование файла или директории
    if full_path.exists():
        return True, 'file'
    else:
        return False, 'missing'


def check_file(file_path: Path, base_dir: Path) -> Dict:
    """Проверяет все ссылки в одном файле."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return {
            'file': str(file_path),
            'error': str(e),
            'links': [],
            'missing': []
        }
    
    links = extract_links(content)
    missing = []
    stats = {
        'external': 0,
        'anchor': 0,
        'file': 0,
        'missing': 0
    }
    
    for text, link in links:
        exists, status = check_link(link, file_path.parent)
        if not exists and status == 'missing':
            missing.append((text, link))
            stats['missing'] += 1
        elif status in stats:
            stats[status] += 1
    
    return {
        'file': str(file_path),
        'links': links,
        'missing': missing,
        'stats': stats
    }


def find_markdown_files(root: Path) -> List[Path]:
    """Находит все .md файлы в директории."""
    md_files = []
    for path in root.rglob('*.md'):
        # Пропускаем некоторые директории
        if any(skip in str(path) for skip in ['node_modules', '.git', 'venv', '__pycache__']):
            continue
        md_files.append(path)
    return sorted(md_files)


def main():
    """Главная функция."""
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
    else:
        target = Path('.')
    
    if not target.exists():
        print(f"❌ Путь не существует: {target}")
        sys.exit(1)
    
    # Определяем файлы для проверки
    if target.is_file() and target.suffix == '.md':
        files_to_check = [target]
        base_dir = target.parent
    elif target.is_dir():
        files_to_check = find_markdown_files(target)
        base_dir = target
    else:
        print(f"❌ Неподдерживаемый тип: {target}")
        sys.exit(1)
    
    if not files_to_check:
        print(f"ℹ️  Markdown файлы не найдены в {target}")
        sys.exit(0)
    
    print(f"🔍 Проверка ссылок в {len(files_to_check)} файлах...")
    print("=" * 80)
    
    all_missing = []
    total_stats = {
        'external': 0,
        'anchor': 0,
        'file': 0,
        'missing': 0,
        'total_links': 0
    }
    
    for file_path in files_to_check:
        result = check_file(file_path, base_dir)
        
        if 'error' in result:
            print(f"❌ ОШИБКА в {result['file']}: {result['error']}")
            continue
        
        if result['missing']:
            print(f"\n📄 {result['file']}")
            for text, link in result['missing']:
                print(f"   ❌ MISSING: [{text}]({link})")
            all_missing.extend([(result['file'], text, link) for text, link in result['missing']])
        
        # Обновляем статистику
        for key in total_stats:
            if key in result['stats']:
                total_stats[key] += result['stats'][key]
        total_stats['total_links'] += len(result['links'])
    
    print("=" * 80)
    print(f"\n📊 Статистика:")
    print(f"   Всего файлов: {len(files_to_check)}")
    print(f"   Всего ссылок: {total_stats['total_links']}")
    print(f"   ✅ Внешние ссылки: {total_stats['external']}")
    print(f"   🔗 Якоря: {total_stats['anchor']}")
    print(f"   ✅ Существующие файлы: {total_stats['file']}")
    print(f"   ❌ Отсутствующие файлы: {total_stats['missing']}")
    
    if all_missing:
        print(f"\n❌ Найдено {len(all_missing)} битых ссылок:")
        for file_path, text, link in all_missing:
            print(f"   - {file_path}: [{text}]({link})")
        sys.exit(1)
    else:
        print("\n✅ Все ссылки проверены - битых ссылок не найдено!")
        sys.exit(0)


if __name__ == '__main__':
    main()

