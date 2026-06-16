# Litmus Chaos Experiments

> Требуется Litmus 3.x (chaos-center или `kubectl apply -f litmus-operator.yaml`). Подробнее — [docs/ops/chaos_engineering.md](../../../docs/ops/chaos_engineering.md).

## Эксперимент: Pod Restart (1cai API)
- `chaos-engine.yaml` — привязывает эксперимент к namespace `1cai`, метке `app.kubernetes.io/component=api`.
- `pod-delete.yaml` — сценарий удаления пода (litmus generic).

## Эксперимент: Network Latency
- `chaos-engine-network.yaml` — цель `1cai` API.
- `pod-network-latency.yaml` — добавляет задержку 3s с jitter 500ms.

### Запуск
```bash
# pod-delete
make chaos-litmus-run
# network latency
make chaos-litmus-run EXPERIMENT=network
```

### Cleanup
```bash
kubectl delete -f infrastructure/chaos/litmus/chaos-engine.yaml --ignore-not-found
kubectl delete -f infrastructure/chaos/litmus/chaos-engine-network.yaml --ignore-not-found
kubectl delete -f infrastructure/chaos/litmus/pod-delete.yaml --ignore-not-found
kubectl delete -f infrastructure/chaos/litmus/pod-network-latency.yaml --ignore-not-found
```
