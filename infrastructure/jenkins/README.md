# Jenkins Pipeline

| Файл | Описание |
|------|----------|
| `Jenkinsfile` | Declarative pipeline: `lint` → `tests` → `build-image` → `security-scan` → `deploy-kind` → `deploy-k8s`.

## Требуемые credentials
- `REGISTRY_USERNAME`, `REGISTRY_PASSWORD` — Docker registry.
- `VAULT_TOKEN` — доступ к Vault.
- `KUBECONFIG` или kubeconfig файл для целевого кластера.
- (Опционально) `ARGOCD_TOKEN` для GitOps синхронизации.

Интегрируется с make-таргетами (`make test`, `make helm-deploy`, `make policy-check`). При адаптации под конкретный Jenkins окружение обновите stages и агента.
