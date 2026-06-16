# BSL Tests

| Скрипт | Описание |
|--------|----------|
| `run_bsl_tests.py` | Запускает YAxUnit/OneScript тесты 1С, использует `tests/bsl/testplan.json`. Связан с `make test-bsl` и CI job `bsl-tests`.

## Запуск
```bash
make test-bsl
```

Логи складываются в `output/bsl-tests/`. Подробнее — в [`docs/06-features/TESTING_GUIDE.md`](../../docs/06-features/TESTING_GUIDE.md).
