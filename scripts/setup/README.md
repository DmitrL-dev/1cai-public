# Setup Helpers

| Скрипт | Назначение |
|--------|-----------|
| `check_runtime.py` | Проверяет, что Python 3.11 установлен и доступен в PATH. Запускается make-таргетом `make check-runtime`.

## Запуск
```bash
make check-runtime
```

Если версия Python не найдена — скрипт подскажет, как установить её (см. [`docs/setup/python_311.md`](../../docs/setup/python_311.md)).
