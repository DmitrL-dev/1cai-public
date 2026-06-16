# Policy-as-Code для 1C AI Stack

> Обновлено: 11 ноября 2025 — Conftest/OPA + Semgrep интеграция.

## 1. Цели
- Автоматический контроль Kubernetes/Helm/Kind конфигураций.
- Превентивный поиск небезопасных паттернов в Python коде.
- Единая команда (`make policy-check`) и CI-стадия для проверки политик.

## 2. Инструменты
- **Conftest (OPA)** — исполняет Rego-политики из каталога `policy/`.
- **Helm template** — рендерит чарты перед проверкой (1cai-stack, observability-stack).
- **Semgrep** — статический анализ Python кода (hardcoded secrets, небезопасные API).

## 3. Реализация
- Каталог `policy/kubernetes/` (темы: ресурсы, probes, securityContext), `policy/terraform/` (AWS/Azure/общие требования: теги, публичный доступ, purge protection).
- Скрипт `scripts/security/run_policy_checks.sh`: Helm → Conftest, Terraform plan → Conftest (`policy/terraform`), Semgrep, Checkov/Trivy.
- Make `policy-check`.
- Jenkins/GitLab pipeline обновлены (stage Security Scan).
- Скрипты `scripts/secrets/rotate_vault_secret.sh`, `scripts/secrets/test_vault_sync.sh` — ротация и проверка.
- Документ `docs/security/policy_as_code.md`.

## 4. Требования к окружению
- `helm`, `conftest >= 0.46`, `semgrep`, `terraform` (для fmt).
- CI job устанавливает зависимости (`apk add helm`, wget conftest, pip install semgrep).

## 5. Расширение
- Добавить Rego-политики для Terraform (`tfplan.json`), docker-compose, GitHub Actions.
- Подключить внешние наборы правил Semgrep (`p/ci`, `p/secpipeline`).
- Балансировать исключения через аннотации `policy.1cai.io/skip` (TODO).

## 6. Благодарности
- [Open Policy Agent / Conftest](https://www.openpolicyagent.org/)
- [Semgrep](https://semgrep.dev/)

Политики и скрипты обязательны к выполнению перед merge/release (см. конституцию).
