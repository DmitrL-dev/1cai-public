# Monitoring Helpers

Скрипты, которые собирают информацию о внешних зависимостях и состояниях.

| Скрипт | Описание |
|--------|----------|
| `github_monitor.py` | Отслеживает обновления репозиториев/зависимостей через GitHub API. Сохраняет снимки в `output/monitoring/github_state.json`. Используется workflow `github-monitor.yml`.

## Запуск
```bash
python scripts/monitoring/github_monitor.py --config config/monitoring/github.yml
```

Параметры (список репозиториев, токен) задаются через конфиг или переменные окружения. Результаты синхронизируются с [`docs/status/dora_history.md`](../../docs/status/dora_history.md) и FinOps отчётами.
