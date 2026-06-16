# Policy-as-Code

RegO-политики для Conftest/Semgrep/Checkov, которые проверяются скриптом [`scripts/security/run_policy_checks.sh`](../scripts/security/README.md) и make-таргетом `make policy-check`.

## Структура
| Каталог | Содержимое |
|---------|------------|
| `kubernetes/` | Политики для Deployment/Service/Ingress (например, запрет `allowPrivilegeEscalation`, проверка TLS). |
| `terraform/` | Политики IaC (общие, AWS, Azure). |

## Запуск проверок
```bash
make policy-check
```

Результаты складываются в `output/security/`. Полное описание подхода — в [`docs/security/policy_as_code.md`](../docs/security/policy_as_code.md).
