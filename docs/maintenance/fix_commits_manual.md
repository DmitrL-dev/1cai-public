# Инструкция по исправлению commit messages вручную

## Проблема

Из-за ограничений Windows/PowerShell с `git filter-branch`, автоматическое исправление не сработало. Но все необходимые данные подготовлены.

## Решение: Использовать Git Bash

1. Откройте **Git Bash** (не PowerShell!)

2. Перейдите в директорию репозитория:
   ```bash
   cd "/c/Users/user/Desktop/package (1)/1cai"
   ```

3. Запустите исправление:
   ```bash
   export FILTER_BRANCH_SQUELCH_WARNING=1
   git filter-branch --msg-filter "python scripts/maintenance/git_msg_filter.py" -- --all
   ```

4. Проверьте результат:
   ```bash
   git log --oneline -30
   ```

5. Если все ОК, выполните force push:
   ```bash
   git push --force-with-lease origin main
   ```

6. Очистите backup refs:
   ```bash
   git for-each-ref --format='%(refname)' refs/original/ | xargs -n 1 git update-ref -d
   ```

## Альтернатива: Git Filter Repo

Если установлен `git-filter-repo` (рекомендуется):

```bash
# Установка (если нужно)
pip install git-filter-repo

# Исправление
git filter-repo --message-callback '
import os
fixes = {
    "1d328ff3d9bb6202cd0e8fb4529c949fc12b97a0": "ci: sync coverage threshold with .coveragerc in perfect-ci-cd",
    # ... остальные из scripts/maintenance/git_msg_filter.py
}
commit_hash = os.environ.get("GIT_COMMIT", "")
return fixes.get(commit_hash, message)
'
```

## Список коммитов для исправления

Все маппинги находятся в `scripts/maintenance/git_msg_filter.py` и `scripts/maintenance/apply_commit_fixes.py`.

Всего нужно исправить **25 коммитов**.

## Важно

⚠️ **Переписывание истории** - убедитесь, что:
- Вы работаете один с репозиторием, ИЛИ
- Все остальные разработчики знают о переписывании истории
- У вас есть backup

После force push все остальные должны выполнить:
```bash
git fetch origin
git reset --hard origin/main
```

