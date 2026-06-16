# Cleanup Utilities

Скрипты, которые приводят репозиторий в порядок перед публикацией: удаляют временные файлы, перемещают артефакты в архив и проверяют `.gitignore`.

| Скрипт | Назначение |
|--------|-----------|
| `cleanup_archive_package.py` | Убирает устаревшие архивы/пакеты из `docs/09-archive/`. |
| `move_research_files.py` | Переносит research черновики из корня в архивные каталоги. |
| `move_temp_files.py` | Находит и перемещает временные файлы (`*.tmp`, `notes`, `drafts`). |
| `analyze_root_cleanup.py` | Анализирует корень проекта, рекомендует что удалить/переместить. |

## Запуск
```bash
python scripts/cleanup/analyze_root_cleanup.py --fix
python scripts/cleanup/move_research_files.py
```

Запускайте cleanup перед экспортом в публичный репозиторий и после крупных экспериментов. Связан с `make preflight`.
