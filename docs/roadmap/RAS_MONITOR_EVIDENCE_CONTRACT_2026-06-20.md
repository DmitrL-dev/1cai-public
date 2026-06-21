# RAS Monitor Evidence Contract

Дата: 2026-06-20.

## Зачем

RAS Monitor возвращал фиктивный cluster object при ошибке RAC/RAS, из-за чего недоступный источник мог выглядеть как пустой и потенциально здоровый кластер. Для Platform Doctor/Operations это недопустимо.

## Что сделано

- Добавлен публичный `get_cluster_health`.
- Недоступный RAS возвращает `status: not_connected`, `coverage: no_ras_connection`, `health_status: unknown` и caveats.
- Убран фиктивный cluster fallback.
- Базовое чтение cluster/session помечается как partial evidence, если рабочие процессы/память/CPU не измерены.
- Расчет рекомендаций больше не делит на ноль, когда число рабочих процессов неизвестно.

## Проверка

- `pytest tests\unit\test_ras_monitor_contract.py -q`
- `python -m py_compile src/integrations/onec/ras_monitor.py tests/unit/test_ras_monitor_contract.py`
