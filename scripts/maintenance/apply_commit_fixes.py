
#!/usr/bin/env python3
"""
Скрипт для исправления commit messages через git filter-branch.
Исправляет все коммиты с проблемами кодировки.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Маппинг полных хешей на правильные сообщения
COMMIT_FIXES = {
    "1d328ff3d9bb6202cd0e8fb4529c949fc12b97a0": "ci: sync coverage threshold with .coveragerc in perfect-ci-cd",
    "fd0f5bbb4dc6e470f1e51124cb174c66fc59bea2": "tests: stabilize environment and stubs for unit/integration",
    "82f3db07dd1f7b6d70f47a2283b926fa21c2fbf2": "tests: prepare environment and fix basic errors",
    "b94d4d4727f367191b72ea42efc27942bfced034": "policy & observability: add quick entry navigation",
    "2632117c9995edb2fe8dfcb12edd5ce03cdd0e7f": "src: document key modules and layers",
    "3537ec80dc7185d8dda8f1c71b8bba7992236997": "infrastructure: add navigation and README for components",
    "48cc2c4503b3e9acb907cccc03ebc8f572d1fd2d": "scripts: add navigation and README for subdirectories",
    "9cc94d102b00d12ccc1ed19f38f810338b05a478": "README: make render_uml.py link clickable",
    "3a2f5328c1ca47c0cee0b7c76bc6619cc7dbe14f": "README: make key links clickable",
    "c077cfb176bfd26aaf7650857303fd90c527d890": "docs: rework onboarding and navigation",
    "ddcdad1484a686be26d134b7177e4badb819f0a4": "docs: add diagram previews in UML catalogs",
    "2ff1dca9f22fec2f94a785068e9c1e0770205885": "docs: add navigation for UML diagrams",
    "b491791645aa2b23d1a948e02e4c292902b2450b": "README: add explicit diagram generation step",
    "58036855390e7d15695bbd130f95bfb67ed2b049": "README: make links in quick overview clickable",
    "e86fc8c615c5e1e9c87e476b506aa4c66207e6a3": "README: add quick 30-second overview",
    "31ba4cd020de978bc659bee82374b04969bb88fe": "README: restore content block and clarify quickstart",
    "22660da62be54e07518e343998395e4b3db93b51": "README: balance introduction and motivation",
    "312b8db730a983f6c31876c8af6ef98ba5af654a": "README: add vivid description of motivation",
    "397144afea59836978d3011c54e7a4609cef8585": "README: add some self-irony to introduction",
    "174c300249930ac70331b2172e0ddb9af4053d9d": "README: improve quickstart and motivation",
    "1291975b21162d6b59bd78ba6d3e7684972d65b5": "README: add quickstart and motivation improvements",
    "30b7340a9c12717dcaddb2901b524feba5ff0b6c": "README: improve quickstart and motivation",
    "e1731cd5c37b1a3df5395849bf9c932d6df7f545": "README: clarify benefits and warmup for quickstart",
    "c693571498a1831d4cdbabbb2a978ee93012b662": "docs: improve README: add quick overview and motivation",
    "3f06288f1660b0728a7e68ec6ac59cdc8f511c42": "docs: improve README: add quick overview",
}

def create_filter_script():
    """Создать скрипт для git filter-branch (работает на Windows и Unix)"""
    # Используем Python скрипт вместо bash для кроссплатформенности
    script_lines = ["#!/usr/bin/env python3"]
    script_lines.append("import sys")
    script_lines.append("import os")
    script_lines.append("")
    script_lines.append("commit_hash = os.environ.get('GIT_COMMIT', '')")
    script_lines.append("")
    
    script_lines.append("fixes = {")
    for commit_hash, new_message in COMMIT_FIXES.items():
        # Экранируем для Python строки
        escaped_msg = new_message.replace('\\', '\\\\').replace('"', '\\"')
        script_lines.append(f'    "{commit_hash}": "{escaped_msg}",')
    script_lines.append("}")
    script_lines.append("")
    script_lines.append("if commit_hash in fixes:")
    script_lines.append("    print(fixes[commit_hash])")
    script_lines.append("else:")
    script_lines.append("    # Для остальных коммитов оставляем как есть")
    script_lines.append("    sys.stdout.write(sys.stdin.read())")
    
    return "\n".join(script_lines)

def main():
    print("=" * 70)
    print("Git Commit Message Fixer")
    print("=" * 70)
    print(f"\nWill fix {len(COMMIT_FIXES)} commits with encoding issues.\n")
    
    # Показываем что будет исправлено
    result = subprocess.run(
        ['git', 'log', '--format=%H|%s', '--all'],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    print("Commits to be fixed:")
    for line in result.stdout.strip().split('\n'):
        if '|' in line:
            commit_hash, message = line.split('|', 1)
            if commit_hash in COMMIT_FIXES:
                print(f"  {commit_hash[:8]}: {message[:50]}...")
                print(f"    -> {COMMIT_FIXES[commit_hash]}")
    
    print("\n" + "=" * 70)
    print("WARNING: This will rewrite git history!")
    print("Make sure you have a backup or are working on a feature branch.")
    print("=" * 70)
    
    # Проверяем флаг --yes для автоматического выполнения
    auto_yes = '--yes' in sys.argv or '-y' in sys.argv
    
    if not auto_yes:
        response = input("\nProceed? (type 'yes' to continue): ").strip().lower()
        if response != 'yes':
            print("Aborted.")
            return 1
    else:
        print("\nAuto-proceeding with --yes flag...")
    
    # Создаем временный скрипт
    filter_script = create_filter_script()
    
    # Используем .py для Python скрипта
    suffix = '.py' if os.name == 'nt' else '.sh'
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
        f.write(filter_script)
        script_path = f.name
    
    # Делаем скрипт исполняемым
    if os.name != 'nt':
        os.chmod(script_path, 0o755)
    else:
        # На Windows используем python для запуска скрипта
        script_path = f'python {script_path}'
    
    try:
        print("\nRunning git filter-branch...")
        print("This may take a while for large repositories.\n")
        
        # Запускаем filter-branch
        result = subprocess.run(
            ['git', 'filter-branch', '--msg-filter', script_path, '--', '--all'],
            cwd=Path.cwd()
        )
        
        if result.returncode == 0:
            print("\n" + "=" * 70)
            print("SUCCESS! Commit messages have been fixed.")
            print("=" * 70)
            print("\nNext steps:")
            print("1. Review changes: git log --oneline -30")
            print("2. If satisfied, force push: git push --force-with-lease origin main")
            print("3. Clean up backup refs:")
            print("   git for-each-ref --format='%(refname)' refs/original/ | xargs -n 1 git update-ref -d")
            return 0
        else:
            print("\nERROR: git filter-branch failed. Check output above.")
            return 1
    
    finally:
        # Удаляем временный скрипт
        try:
            os.unlink(script_path)
        except:
            pass

if __name__ == '__main__':
    sys.exit(main())

