
#!/usr/bin/env python3
"""
Скрипт для автоматического исправления всех commit messages с проблемами кодировки.
Использует git filter-branch для переписывания истории.
"""

import re
import subprocess
import sys
from pathlib import Path

# Маппинг проблемных сообщений на правильные (на английском)
COMMIT_FIXES = {
    # Паттерны для поиска и замены
    r'ci: СЃРёРЅС…СЂРѕРЅРёР·РёСЂРѕРІР°С‚СЊ.*': 'ci: sync coverage threshold with .coveragerc in perfect-ci-cd',
    r'tests: СЃС‚Р°Р±РёР»РёР·РёСЂРѕРІР°С‚СЊ.*': 'tests: stabilize environment and stubs for unit/integration',
    r'tests: РїРѕРґРіРѕС‚РѕРІРёС‚СЊ.*': 'tests: prepare environment and fix basic errors',
    r'policy & observability: РґРѕР±Р°РІРёС‚СЊ.*': 'policy & observability: add quick entry navigation',
    r'src: Р·Р°РґРѕРєСѓРјРµРЅС‚РёСЂРѕРІР°С‚СЊ.*': 'src: document key modules and layers',
    r'infrastructure: РґРѕР±Р°РІРёС‚СЊ РЅР°РІРёРіР°С†РёСЋ.*': 'infrastructure: add navigation and README for components',
    r'scripts: РґРѕР±Р°РІРёС‚СЊ РЅР°РІРёРіР°С†РёСЋ.*': 'scripts: add navigation and README for subdirectories',
    r'README: СЃРґРµР»Р°С‚СЊ СЃСЃС‹Р»РєСѓ.*': 'README: make render_uml.py link clickable',
    r'README: СЃРґРµР»Р°С‚СЊ РєР»СЋС‡РµРІС‹Рµ.*': 'README: make key links clickable',
    r'docs: РїРµСЂРµСЂР°Р±РѕС‚Р°С‚СЊ.*': 'docs: rework onboarding and navigation',
    r'docs: РґРѕР±Р°РІРёС‚СЊ РїСЂРµРІСЊСЋ.*': 'docs: add diagram previews in UML catalogs',
    r'docs: РґРѕР±Р°РІРёС‚СЊ РЅР°РІРёРіР°С†РёСЋ.*': 'docs: add navigation for UML diagrams',
    r'README: РґРѕР±Р°РІРёС‚СЊ СЏРІРЅС‹Р№.*': 'README: add explicit diagram generation step',
    r'README: СЃРґРµР»Р°С‚СЊ СЃСЃС‹Р»РєРё.*': 'README: make links in quick overview clickable',
    r'README: РґРѕР±Р°РІРёС‚СЊ Р±С‹СЃС‚СЂС‹Р№.*': 'README: add quick 30-second overview',
    r'README: РІРµСЂРЅСѓС‚СЊ.*': 'README: restore content block and clarify quickstart',
    r'README: СЃР±Р°Р»Р°РЅСЃРёСЂРѕРІР°С‚СЊ.*': 'README: balance introduction and motivation',
    r'README: РґРѕР±Р°РІРёС‚СЊ Р¶РёРІРѕРµ.*': 'README: add vivid description of motivation',
    r'README: РґРѕР±Р°РІРёС‚СЊ РЅРµРјРЅРѕРіРѕ.*': 'README: add some self-irony to introduction',
}

def get_all_commits():
    """Получить все коммиты с их сообщениями"""
    result = subprocess.run(
        ['git', 'log', '--format=%H|%s', '--all'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    commits = []
    for line in result.stdout.strip().split('\n'):
        if '|' in line:
            commit_hash, message = line.split('|', 1)
            commits.append((commit_hash, message))
    return commits

def find_matching_fix(message):
    """Найти подходящее исправление для сообщения"""
    for pattern, replacement in COMMIT_FIXES.items():
        if re.search(pattern, message):
            return replacement
    return None

def main():
    print("Checking commits for encoding issues...\n")
    
    commits = get_all_commits()
    fixes_needed = []
    
    for commit_hash, message in commits:
        fix = find_matching_fix(message)
        if fix:
            fixes_needed.append((commit_hash, message, fix))
            print(f"Found: {commit_hash[:8]} - {message[:50]}...")
            print(f"  -> {fix}\n")
    
    if not fixes_needed:
        print("No commits need fixing!")
        return 0
    
    print(f"\nTotal commits to fix: {len(fixes_needed)}")
    print("\n⚠️  WARNING: This will rewrite git history!")
    print("This script will use 'git filter-branch' to fix commit messages.")
    print("\nProceed? (yes/no): ", end='')
    
    response = input().strip().lower()
    if response != 'yes':
        print("Aborted.")
        return 1
    
    # Используем git filter-branch для исправления
    # Создаем скрипт для замены сообщений
    script_content = "#!/bin/sh\n"
    script_content += "# Auto-generated script for fixing commit messages\n\n"
    
    for commit_hash, old_msg, new_msg in fixes_needed:
        # Экранируем специальные символы для sed
        old_escaped = old_msg.replace('/', '\\/').replace('&', '\\&')
        new_escaped = new_msg.replace('/', '\\/').replace('&', '\\&')
        script_content += f"if [ \"$GIT_COMMIT\" = \"{commit_hash}\" ]; then\n"
        script_content += f"  echo \"{new_escaped}\"\n"
        script_content += "  exit\n"
        script_content += "fi\n\n"
    
    script_content += "cat\n"  # Для остальных коммитов оставляем как есть
    
    # Сохраняем скрипт
    script_path = Path('.git-rewrite-msg.sh')
    script_path.write_text(script_content, encoding='utf-8')
    script_path.chmod(0o755)
    
    print("\nRunning git filter-branch...")
    print("This may take a while for large repositories.\n")
    
    # Запускаем filter-branch
    result = subprocess.run(
        ['git', 'filter-branch', '--msg-filter', str(script_path.absolute()), '--', '--all'],
        cwd=Path.cwd()
    )
    
    # Удаляем временный скрипт
    script_path.unlink()
    
    if result.returncode == 0:
        print("\n✅ Successfully fixed commit messages!")
        print("\nNext steps:")
        print("1. Review changes: git log --oneline -20")
        print("2. If satisfied, force push: git push --force-with-lease origin main")
        print("3. Clean up backup refs: git for-each-ref --format='%(refname)' refs/original/ | xargs -n 1 git update-ref -d")
    else:
        print("\n❌ Error during filter-branch. Check output above.")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

