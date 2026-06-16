
#!/usr/bin/env python3
"""
Скрипт для проверки и исправления commit messages с некорректной кодировкой.
Проверяет последние N коммитов и предлагает исправления.
"""

import re
import subprocess
import sys


def get_commit_messages(count=30):
    """Получить список commit messages"""
    result = subprocess.run(
        ['git', 'log', '--format=%H|%s', f'-{count}'],
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

def has_encoding_issue(text):
    """Проверить, есть ли проблемы с кодировкой (кракозябры)"""
    # Проверяем на наличие последовательностей типа "СѓС‚Рѕ" или "РєРѕРЅС‚РµРєСЃС‚"
    # Это признаки того, что UTF-8 был прочитан как Windows-1251 или наоборот
    
    # Если текст содержит только латиницу - все ОК
    if re.match(r'^[a-zA-Z0-9\s\-_.,:;!?@#$%^&*()\[\]{}<>/\\|`~]+$', text):
        return False
    
    # Проверяем на типичные кракозябры от неправильной кодировки
    # Паттерны: последовательности из 2+ кириллических символов, которые выглядят как мусор
    suspicious_sequences = [
        'СѓС‚Рѕ',  # "уточнить" в неправильной кодировке
        'РєРѕРЅС‚РµРєСЃС‚',  # "контекст"
        'Р±СЌРєР»РѕРі',  # "бэклог"
        'СЃРёРЅС…СЂРѕРЅРёР·РёСЂРѕРІР°С‚СЊ',  # "синхронизировать"
        'СЃС‚Р°Р±РёР»РёР·РёСЂРѕРІР°С‚СЊ',  # "стабилизировать"
        'Р·Р°РіР»СѓС€РєРё',  # "заглушки"
        'РѕРєСЂСѓР¶РµРЅРёРµ',  # "окружение"
    ]
    
    # Проверяем наличие известных кракозябр
    for seq in suspicious_sequences:
        if seq in text:
            return True
    
    # Проверяем на последовательности из 3+ кириллических символов подряд,
    # которые не являются нормальными словами (эвристика)
    # Если текст содержит много кириллицы, но выглядит как мусор - проблема
    cyrillic_count = len(re.findall(r'[А-Яа-я]', text))
    if cyrillic_count > 5:
        # Если много кириллицы, но текст короткий и содержит подозрительные символы
        if len(text) < 100 and '?' in text:
            return True
    
    return False

def fix_commit_message(message):
    """Попытаться исправить commit message"""
    # Если сообщение уже на английском или не содержит проблем - вернуть как есть
    if not has_encoding_issue(message):
        return message
    
    # Попытка исправить: если это кракозябры от неправильной кодировки,
    # мы не можем автоматически восстановить оригинал
    # Но можем предложить переписать на английском
    return None  # Требует ручного исправления

def main():
    print("Проверка commit messages на проблемы с кодировкой...\n")
    
    commits = get_commit_messages(30)
    issues = []
    
    for commit_hash, message in commits:
        if has_encoding_issue(message):
            issues.append((commit_hash, message))
            print(f"[ISSUE] {commit_hash[:8]}: {message[:60]}...")
    
    if not issues:
        print("[OK] All commit messages are fine!")
        return 0
    
    print(f"\nFound {len(issues)} commits with encoding issues.")
    print("\nРекомендации:")
    print("1. Для последних коммитов (еще не запушенных): используйте 'git commit --amend'")
    print("2. Для старых коммитов: рассмотрите interactive rebase (git rebase -i)")
    print("3. В будущем: используйте английский для commit messages или настройте git:")
    print("   git config --global i18n.commitencoding utf-8")
    print("   git config --global core.quotepath false")
    
    return len(issues)

if __name__ == '__main__':
    sys.exit(main())

