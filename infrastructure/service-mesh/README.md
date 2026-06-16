# Service Mesh Manifests

Профили для Linkerd и Istio. Используйте совместно со скриптами [`scripts/service_mesh/`](../../scripts/service_mesh/README.md).

| Каталог | Назначение |
|---------|------------|
| [`linkerd/`](linkerd/README.md) | Kustomize-манифесты для установки Linkerd через GitOps. |
| [`istio/`](istio/README.md) | Профиль IstioOperator (альтернативный сервис-меш).

## Быстрый старт (Linkerd)
```bash
make linkerd-install
make linkerd-rotate-certs
```

Подробнее — в [`docs/ops/service_mesh.md`](../../docs/ops/service_mesh.md).
