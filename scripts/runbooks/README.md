# Runbook Automation

Скрипты, автоматизирующие тренировки и проверки runbook'ов.

| Скрипт | Описание |
|--------|----------|
| `dr_rehearsal_runner.py` | Запускает сценарии Disaster Recovery, логирует шаги и результат. Используется workflow `dr-rehearsal.yml`.

## Запуск
```bash
python scripts/runbooks/dr_rehearsal_runner.py --plan docs/runbooks/dr_rehearsal_plan.md
```

Результаты сохраняются в `output/runbooks/`. После выполнения обновите [`docs/runbooks/dr_rehearsal_plan.md`](../../docs/runbooks/dr_rehearsal_plan.md) и зафиксируйте вывод в postmortem/runbook history.
