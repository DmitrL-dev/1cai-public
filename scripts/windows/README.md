# Windows Helpers

PowerShell-скрипты, повторяющие ключевые make-таргеты для пользователей Windows (без GNU Make и bash).

| Скрипт | Что делает |
|--------|------------|
| `docker-up.ps1`, `docker-down.ps1`, `docker-logs.ps1` | Аналог `make docker-up/down/logs` — управление docker-compose окружением. |
| `migrate.ps1`, `servers.ps1` | Поднимают миграции и API/MCP сервисы. |
| `bsl-ls-up.ps1`, `bsl-ls-check.ps1`, `bsl-ls-logs.ps1` | Управление `bsl-language-server`. |
| `feature-init.ps1`, `feature-validate.ps1` | Спецификации/feature workflow без Make. |
| `security-audit.ps1` | Полный security-аудит (hidden dirs, secrets, git safety, comprehensive audit) без GNU Make. |
| `k8s-portforward.ps1`, `cleanup.ps1` (если есть) | Вспомогательные операции.

## Использование
```powershell
pwsh scripts/windows/docker-up.ps1
pwsh scripts/windows/migrate.ps1
pwsh scripts/windows/servers.ps1

# Полный security-аудит для Windows:
pwsh scripts/windows/security-audit.ps1
```

> Запускайте PowerShell от имени администратора, если скрипты обращаются к Docker Desktop или Kubernetes. Параметры (например, путь к конфигурации) задаются через аргументы или переменные внутри скрипта.
