# Security Scans & Policy Checks

Инструменты для запуска статического анализа, Policy-as-Code и проверки инфраструктуры. Используются в `make policy-check` и CI (Gitleaks, Trufflehog, Checkov, Semgrep).

| Скрипт | Назначение |
|--------|-----------|
| `run_security_scans.sh` | Запускает bandit, pip-audit, safety. Используется в Jenkins/GitLab pipeline. |
| `run_policy_checks.sh` | Рендерит Helm-чарты, прогоняет Conftest (Rego из `policy/`), Semgrep и Checkov. |
| `run_checkov.sh` | Запускает Checkov и Trivy для Terraform/Kubernetes. |

## Требования
- `helm`, `kubectl`, `terraform`, `conftest`, `semgrep`, `checkov`, `trivy` в `$PATH`.
- Настроенные провайдеры/credentials, если проверяются реальные кластеры.

## Использование
```bash
# Локальный Policy-as-Code
make policy-check

# Полный security-скан
bash scripts/security/run_security_scans.sh
```

Сводки сохраняются в `output/security/`. При изменении политик обновляйте [`docs/security/policy_as_code.md`](../../docs/security/policy_as_code.md).
