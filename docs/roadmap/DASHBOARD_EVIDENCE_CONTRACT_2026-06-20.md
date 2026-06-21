# Dashboard Evidence Contract

Дата: 2026-06-20.

## Зачем

Executive и Developer dashboard показывали синтетические ROI, revenue trend, alerts, objectives, задачи, PR, build status, code quality и AI suggestions. Это создавало красивую, но недоказуемую картинку.

## Что сделано

- Executive dashboard больше не генерирует случайную выручку, ROI, growth, usage и objectives.
- Users count берется из БД, остальные секции помечены `measured: false` / `not_measured` с caveats.
- Developer dashboard больше не показывает фиктивные задачи, PR, CI и quality scores.
- Добавлен `data_contract: dashboard_evidence_contract`.

## Проверка

- `pytest tests\unit\test_dashboard_evidence_contract.py -q`
- `python -m py_compile src/modules/dashboard/services/executive_service.py src/modules/dashboard/services/developer_service.py tests/unit/test_dashboard_evidence_contract.py`
