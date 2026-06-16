# Release Automation

| Скрипт | Описание |
|--------|----------|
| `create_release.py` | Генерирует release notes, changelog и (опционально) создаёт git-теги. Используется make-таргетами `make release-notes`, `make release-tag`, `make release-push`.

## Пример
```bash
make release-notes VERSION=v5.2.0
make release-tag VERSION=v5.2.0
make release-push VERSION=v5.2.0
```

Workflow `.github/workflows/release.yml` вызывает этот скрипт при пуше тега `v*`.
