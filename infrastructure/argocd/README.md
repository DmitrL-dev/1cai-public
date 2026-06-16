# Argo CD Manifests

Kustomize-манифесты, которые разворачивают AppProject и приложения Argo CD для 1C AI Stack.

## Структура
| Файл | Назначение |
|------|-----------|
| `namespace.yaml` | Namespace `argocd`. |
| `app-project.yaml` | AppProject с политиками доступа. |
| `application-1cai.yaml` | Helm release приложения (`infrastructure/helm/1cai-stack`). |
| `application-observability.yaml` | Helm release observability-стека. |
| `application-linkerd.yaml` | Развёртывание Linkerd (при использовании Helm chart/manifest). |
| `applicationset-linkerd.yaml` | ApplicationSet для Linkerd в нескольких средах (staging/prod). |
| `applicationset-1cai.yaml` | ApplicationSet для 1cai Helm chart в нескольких средах (staging/prod). |
| `kustomization.yaml` | Сборка всех манифестов.

## Использование
```bash
# Применить манифесты
make gitops-apply

# Синхронизировать приложения
make gitops-sync
```

Требования: установлен `kubectl`, `kustomize` (или встроенный в kubectl) и Argo CD CLI (для `make gitops-sync`). Подробнее — [docs/ops/gitops.md](../../docs/ops/gitops.md).
