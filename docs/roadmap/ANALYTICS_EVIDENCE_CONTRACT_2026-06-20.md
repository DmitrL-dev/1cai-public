# Analytics Evidence Contract

Дата: 2026-06-20.

## Зачем

Analytics API и ROI service показывали hardcoded owner/executive/PM/developer цифры и монетизировали улучшения через фиксированные коэффициенты. Для директора это выглядит красиво, но не выдерживает вопрос "откуда цифра?".

## Что сделано

- Owner, Executive, PM и Developer analytics dashboards возвращают `analytics_dashboard_evidence_contract`.
- Revenue, customers, growth, ROI, users, sprint, CI и quality sections помечаются как `measured: false`, если источник не подключен.
- Pydantic response models теперь пропускают `data_contract`, `caveats`, `measured` и `caveat`.
- ROI service больше не считает cost savings из фиксированных часов/стоимости бага; без value model возвращает `roi_measured: false`.

## Проверка

- `pytest tests\unit\test_analytics_evidence_contract.py tests\unit\test_dashboard_evidence_contract.py -q`
- `python -m py_compile src/modules/analytics/application/service.py src/modules/analytics/api/routes.py src/modules/analytics/api/schemas.py tests/unit/test_analytics_evidence_contract.py`
