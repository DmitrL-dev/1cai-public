# Istio Service Mesh (Blueprint)

> Поддерживает AWS/GCP/Azure/On-prem. Требуется установленный `istioctl` (>=1.21).

## 1. Структура
- `profile-default.yaml` — IstioOperator манифест для демо-кластера (IngressGateway, telemetry v2).
- `kustomization.yaml` — позволяет применить IstioOperator через `kubectl apply -k`.

## 2. Быстрый старт
```bash
istioctl install -f infrastructure/service-mesh/istio/profile-default.yaml -y
# либо
kubectl apply -k infrastructure/service-mesh/istio
```

## 3. Интеграция с 1C AI Stack
- Namespace `1cai` нужно пометить `kubectl label namespace 1cai istio-injection=enabled`.
- Обновить Helm values (`infrastructure/helm/1cai-stack/values.yaml`): добавить `sidecar.istio.io/inject: "true"` при необходимости.
- Prometheus/Grafana из наблюдаемости автоматически подберут метрики через Istio scraping.

## 4. Следующие шаги
- Создать ServiceEntry/VirtualService для внешних сервисов (MCP, marketplace).
- Настроить mTLS (PeerAuthentication) и AuthorizationPolicy.
- Сценарии chaos-тестирования: см. `infrastructure/chaos/litmus/`.
