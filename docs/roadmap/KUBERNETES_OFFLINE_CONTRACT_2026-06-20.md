# Kubernetes Offline Contract

Дата: 2026-06-20.

## Зачем

Kubernetes client возвращал `pending_implementation` для deploy/scale и пустые логи/статус без явного признака, что живой adapter не подключён. Для DevOps/эксплуатации это опасно: mutation-инструмент обязан явно показывать, применял он изменения или нет.

## Что сделано

- Без kubeconfig/Kubernetes adapter операции `deploy_app`, `scale_deployment`, `get_deployment_status`, `get_pod_logs` возвращают `offline_kubernetes_contract`.
- Контракт содержит `applied: false`, `configured: false`, desired state, required evidence и caveats.
- Убраны `pending_implementation` и stub-диагностика из `src/integrations/k8s_client.py`.

## Проверка

- `pytest tests\unit\test_k8s_offline_contract.py -q`
- `python -m py_compile src/integrations/k8s_client.py tests/unit/test_k8s_offline_contract.py`
