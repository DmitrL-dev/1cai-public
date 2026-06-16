# Linkerd Service Mesh (Blueprint)

## 1. Установка
1. Установите CLI: `curl -sL https://run.linkerd.io/install | sh` и добавьте в `$PATH`.
2. Проверка: `linkerd check --pre`.
3. Установка control plane:
   ```bash
   linkerd install | kubectl apply -f -
   linkerd viz install | kubectl apply -f -
   ```
4. Включить sidecar для `1cai`:
   ```bash
   kubectl annotate ns 1cai linkerd.io/inject=enabled
   kubectl rollout restart deploy -n 1cai
   ```

## 2. Certs & identity
- Скрипт `bootstrap_certs.sh` генерирует trust anchor/issuer (`observability/service-mesh/linkerd/certs`).
- Скрипт `deploy_issuer_secret.sh` применяет секрет `linkerd-identity-issuer`. Используется в Helm/ArgoCD (TODO: sealed-secret).
- Для Azure Managed Identity: `apply_managed_identity.sh <rg> <identity> <keyvault> <namespace>` — выдаёт доступ и сохраняет `AZURE_CLIENT_ID` в секрет.

## 3. GitOps
- `application-linkerd.yaml` — одиночное приложение.
- `applicationset-linkerd.yaml` — staging/prod.

## 4. Roadmap
- Пользовательский Helm chart (values overlay).
- Integrate trust anchors via external secrets.
- Chaos эксперимент для Linkerd (latency/packet loss).
