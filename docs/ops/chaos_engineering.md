# Chaos Engineering (Litmus)

## 1. Цель
- Проверить устойчивость API/MCP сервисов при сбоях (перезапуски pod’ов, сетевые проблемы).

## 2. Компоненты
- Litmus Chaos (operator в namespace `litmus`).
- Эксперименты: `infrastructure/chaos/litmus/` (pod-delete + engine, pod-network-latency + engine).
- Скрипт: `scripts/chaos/run_litmus.sh` (`make chaos-litmus-run [EXPERIMENT=network]`).

## 3. Запуск
1. Установить Litmus (см. https://docs.litmuschaos.io/docs/runbooks/install). Минимум: `kubectl apply -f https://litmuschaos.github.io/litmus/litmus-operator-v3.yaml`.
2. Запустить эксперимент:
   ```bash
   make chaos-litmus-run
   ```
3. Наблюдать результат:
   ```bash
   make chaos-litmus-run                # pod-delete
   make chaos-litmus-run EXPERIMENT=network  # latency
   kubectl describe chaosengine api-pod-delete -n 1cai
   kubectl get chaosresults -n 1cai
   ```

## 4. Расширение
- Добавить сетевой chaos (pod-network-loss) для проверки Istio resilience.
- Интеграция с Grafana (панель ChaosRun).
- Автоматизировать запуск в CI (nightly).
