# Operational Self-Control Checklist

## 1. Назначение
- Инженер выполняет самопроверку перед релизом/деплоем.
- Автоматизированный скрипт + чек-лист для ручного подтверждения.

## 2. Скрипт
- `scripts/checklists/preflight.sh` — запускает `make check-runtime`, `make lint`, `make test`, `make policy-check`, `run_checkov.sh`. Сохраняет лог (временный файл) и, если установлен `SLACK_WEBHOOK_URL`, отправляет summary в канал.
- Команда: `make preflight` (см. Makefile).

## 3. Ручной чек-лист
1. Проверены все CI job’ы (Jenkins/GitLab/Azure) — зелёные.
2. GitOps/Argo CD приложения в статусе `Synced`.
3. Vault/Secret Manager — подтверждён актуальный секрет.
4. Observability — Grafana dashboards без аномалий.
5. Коммуникация со стейкхолдерами (issue, changelog, оповещения).

## 4. Отчётность
- После выполнения `make preflight` фиксировать результат в issue/PR (скриншот или лог).
- В случае ошибки — описывать RCA (Root Cause) внутри PR.
