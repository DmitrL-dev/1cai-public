# Audits & Quality Checks

Автоматизированные проверки структуры репозитория, лицензий и безопасности. Обязательны перед публикацией (см. [`docs/research/constitution.md`](../../docs/research/constitution.md)).

| Скрипт | Назначение |
|--------|-----------|
| `comprehensive_project_audit.py` | Полный аудит (структура, документация, зависимости, секреты). Используйте перед релизом. |
| `project_structure_audit.py` | Проверяет соответствие структуре каталогов и обязательных файлов. |
| `architecture_audit.py` | Валидирует архитектурные артефакты, наличие актуальных диаграмм/ADR. |
| `check_architecture_files.py` | Быстрая сверка, что упомянутые архитектурные файлы существуют. |
| `code_quality_audit.py` | Собирает линт/тест результаты, проверяет отчёты. |
| `license_compliance_audit.py` | Проверяет лицензии зависимостей. |
| `check_git_safety.py` | Убеждается, что чувствительные файлы не попали в репозиторий. |
| `check_hidden_dirs.py` | Ищет неожиданные скрытые директории (`/.folder`) с использованием `git ls-files`. |
| `check_secrets.py` | Лёгкий поиск возможных секретов по эвристикам (`sk-…`, `ghp_…`, `API_KEY=…`, `secret_key=…`, `token=\"…\"`). Результат — `analysis/secret_scan_report.json`. |
| `check_unused_files.py` | Экспериментальный поиск кандидатов на неиспользуемые файлы на основе отсутствия ссылок в коде/документации (НЕ удаляет, только печатает список для ручного ревью). |

## Запуск
```bash
# Полный аудит
python scripts/audit/comprehensive_project_audit.py

# Проверка структуры
python scripts/audit/project_structure_audit.py

# Проверка скрытых директорий (.folder rule)
make audit-hidden-dirs

# Локальный скан возможных секретов
make audit-secrets

# Полный security-аудит (hidden dirs + secrets + git safety + comprehensive)
make security-audit
```

Результаты складываются в `output/audit/` и `analysis/secret_scan_report.json`. Используйте их в `make preflight` и перед синхронизацией с публичным репозиторием.
