# Chaos Engineering

| Скрипт | Описание |
|--------|----------|
| `run_litmus.sh` | Запускает Litmus pod-delete/latency эксперименты. Используется `make chaos-litmus-run` и workflow `chaos-validate.yml`.

## Требования
- Установленный Litmus Chaos Operator в Kubernetes-кластере.
- kubeconfig с правами на namespace эксперимента.

## Запуск
```bash
make chaos-litmus-run EXPERIMENT=network
```

Результаты и логи сохраняются в `output/chaos/`. После проведения эксперимента обновляйте [`docs/ops/chaos_engineering.md`](../../docs/ops/chaos_engineering.md).
