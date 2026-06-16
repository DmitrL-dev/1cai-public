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

## 2. Интеграция с 1C AI Stack
- Используйте скрипты из [`scripts/service_mesh/linkerd`](../../../scripts/service_mesh/linkerd/README.md) для генерации сертификатов и smoke-тестов.
- Namespace `1cai` должен быть аннотирован `linkerd.io/inject=enabled`.
- Observability доступна через `linkerd viz`. Алерты/метрики интегрированы с Grafana (`helm/observability-stack`).

## 3. Примечания
- Linkerd не ставит ingress — используйте Nginx/contour или Istio Gateway.
- Для мTLS и политик доступа смотрите [docs/ops/service_mesh.md](../../../docs/ops/service_mesh.md).
