# GitOps с Argo CD

> Обновлено: 11 ноября 2025

## 1. Цели
- Описать инфраструктуру как код и синхронизировать её через GitOps.
- Исключить ручные `kubectl apply` и гарантировать idempotent деплой до Kubernetes.

## 2. Компоненты
- Argo CD (устанавливается стандартным Helm chart/manifest).
- Kustomize-манифесты `infrastructure/argocd/` (namespace, AppProject, Applications).
- Helm charts (`infrastructure/helm/1cai-stack`, `infrastructure/helm/observability-stack`).

## 3. Быстрый старт
1. Установите Argo CD (https://argo-cd.readthedocs.io/en/stable/getting_started/).
2. Примените наши manifests:
   ```bash
   make gitops-apply
   ```
3. Логин в Argo CD UI/CLI и убедитесь, что приложения `1cai-stack` и `observability-stack` в статусе `Synced`.
4. Синхронизируйте вручную при необходимости:
   ```bash
   ARGOCD_TOKEN=... make gitops-sync
   ```

## 4. Структура
- `namespace.yaml` — создаёт namespace `argocd`.
- `app-project.yaml` — проект `1cai` с whitelisted репозиториями (priv/public).
- `application-1cai.yaml` — Helm chart приложения (`infrastructure/helm/1cai-stack`).
- `application-observability.yaml` — Helm chart наблюдаемости (`infrastructure/helm/observability-stack`).
- `application-linkerd.yaml` — Helm chart Linkerd control plane (опциональный mesh).
- `applicationset-linkerd.yaml` — пример ApplicationSet (staging/prod) для Linkerd.
- `kustomization.yaml` — позволяет применять всё через `kubectl apply -k`.

## 5. Поток изменений
1. Разработчик пушит изменения (Helm chart, values).
2. Argo CD синхронизирует chart → кластер (namespace `1cai` / `observability`).
3. Политики (Conftest/Semgrep) контролируют качество на этапе CI.
4. Alertmanager, Grafana, observability stack фиксируют состояние.

## 6. Best Practices / TODO
- Перевести Argo CD установку в Terraform модуль (EKS/AKS/GKE).
- Добавить SSO (OIDC) и RBAC политики для Argo CD.
- Конфигурировать ApplicationSet (multi-env: staging/prod).
- Интегрировать с Vault (авто-sync секретов).
