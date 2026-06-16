# FinOps & Cost Monitoring

## 1. Цели
- Контроль затрат в AWS/Cloud (ежедневные отчёты, бюджет).

## 2. Инструменты
- `scripts/finops/aws_cost_report.py` — использует AWS Cost Explorer API, показывает ежедневные затраты за 7 дней.
- `scripts/finops/aws_cost_to_slack.py` — отправляет отчёт за 3 дня в Slack (`SLACK_WEBHOOK_URL`) и Teams (`TEAMS_WEBHOOK_URL`).
- `scripts/finops/azure_cost_to_slack.py` — аналог для Azure Cost Management.
- Workflow `.github/workflows/finops-report.yml` — ежедневная отправка отчётов AWS/Azure + проверки Budgets (если заданы `AWS_BUDGET_NAMES`).
- Make цель `make finops-slack` — одномоментный запуск локально.

## 3. Требования
```bash
# AWS
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
export TEAMS_WEBHOOK_URL=https://<teams-webhook>
python scripts/finops/aws_cost_to_slack.py
python scripts/finops/aws_budget_check.py

# Azure
task requires: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_SUBSCRIPTION_ID, SLACK_WEBHOOK_URL/TEAMS_WEBHOOK_URL.
export TEAMS_WEBHOOK_URL=...
python scripts/finops/azure_cost_to_slack.py
```

## 4. Roadmap
- Azure Budgets / Teams оповещения.
- Grafana dashboards с Cost Explorer.

## 4. Grafana
- Дашборд `observability/grafana/dashboards/finops_cost.json` — отображает AWS EstimatedCharges и кастомные Azure метрики (не забудьте настроить datasources `aws-cost`, `azure-cost`).

## 5. Roadmap
- Azure Budgets (API) → Teams уведомления (реализовано в `azure_budget_check.py`).
- Grafana dashboards (частично, нужно подключить источники и панель Teams).
