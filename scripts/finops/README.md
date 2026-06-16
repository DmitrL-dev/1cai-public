# FinOps Automation

Скрипты для мониторинга затрат AWS/Azure и рассылки отчётов в Slack/Teams. Используются локально и в workflow `.github/workflows/finops-report.yml`.

| Скрипт | Функция |
|--------|---------|
| `aws_cost_report.py` | Запрашивает AWS Cost Explorer, формирует ежедневный отчёт (CSV/JSON). |
| `aws_cost_to_slack.py` | Отправляет сводку AWS в Slack webhook. |
| `aws_budget_check.py` | Проверяет превышение бюджетов AWS. |
| `azure_cost_to_slack.py` | Аналогичная отправка для Azure. |
| `azure_budget_check.py` | Проверка Azure budgets. |
| `teams_notify.py` | Универсальный отправщик в Microsoft Teams. |

## Переменные окружения
- AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`.
- Azure: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- Slack: `SLACK_WEBHOOK_URL`.
- Teams: `TEAMS_WEBHOOK_URL`.

## Запуск
```bash
# Разовая отправка в Slack
make finops-slack

# Локальная проверка бюджета
python scripts/finops/aws_budget_check.py --threshold 80
```

Результаты и логи сохраняются в `output/finops/`. Не забудьте обновить документацию (`docs/ops/finops.md`) при изменении логики отчётов.
