# Checklists

Автоматизированные чек-листы, которые стоит выполнять перед релизом/деплоем.

| Скрипт | Описание |
|--------|----------|
| `preflight.sh` | Запускает ключевые проверки (lint, тесты, policy-check, audit), формирует отчёт. Используется make-таргетом `make preflight`.

## Запуск
```bash
make preflight
```

Логи складываются в `output/preflight/`. Список проверок синхронизирован с [`docs/research/constitution.md`](../../docs/research/constitution.md).
