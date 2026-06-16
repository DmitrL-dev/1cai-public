# GitOps Scripts

- `apply.sh` — применяет Kustomize-манифесты Argo CD (`infrastructure/argocd`).
- `sync.sh` — инициирует синхронизацию приложений (`ARGOCDB_SERVER`, `ARGOCD_TOKEN`). Требуется argocd CLI.
