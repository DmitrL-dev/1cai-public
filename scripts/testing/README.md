# Testing Utilities

Вспомогательные скрипты для smoke/health тестов, интеграционных проверок и демо-сценариев. Используются в `make smoke-tests`, `make test`, CI пайплайнах.

| Скрипт | Назначение |
|--------|-----------|
| `smoke_healthcheck.py` | Основной smoke-тест (используется `make smoke-tests`). |
| `run_demo_tests.py` | Прогон демо-наборов API. |
| `test_its_api.py`, `test_gateway.sh`, `test_ocr_service.py` | Тесты конкретных интеграций/сервисов. |
| `check_all_results.py` | Сводная проверка результатов тестов/логов. |
| `test_kimi_linear_48b.py`, `test_parser_optimization.py` | Эксперименты с LLM/парсерами.

## Как запускать
```bash
# Smoke-проверка (автоматически вызывает docker-compose сервисы)
make smoke-tests

# Индивидуальный тест
python scripts/testing/run_demo_tests.py --suite basic
```

Дополнительно см.:
- [`docs/06-features/TESTING_GUIDE.md`](../../docs/06-features/TESTING_GUIDE.md)
- `tests/` (pytest/YAxUnit сценарии)
