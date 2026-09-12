# Runtime metrics adapter

`rentgen_core.runtime_metrics.load_runtime_report()` принимает один JSON-файл,
выгруженный доверенным источником данных 1С или ERP. Адаптер не подключается к
базе, не запускает 1С и не выполняет сеть: он читает ограниченный retained
файл, строит `RuntimeMetricReport` и передаёт его в owner-report.

```python
from rentgen_core.runtime_metrics import load_runtime_report

runtime = load_runtime_report(
    export_path,
    expected_project_id=project_id,
    expected_snapshot_id=snapshot_id,
    expected_commit=commit,
    expected_source_digest=source_digest,
    authorize=authorize_runtime_export,
)
```

Файл имеет schema `1` и содержит `adapter_id`, `source_ref`, project/snapshot/
commit/source digest, период, `generated_at`, флаг `complete` и массив метрик.
Каждая метрика содержит `metric_id`, конечное числовое значение, единицу,
период, `source_id` и `observed_at`. Неизвестные поля, дублирующиеся ключи,
невалидные даты, чужой контекст, повторяющиеся идентичности и превышение
лимитов отклоняются. Авторизация проверяется до чтения и повторно перед
возвратом результата.

Адаптер сохраняет `complete=false` как неполный evidence; owner-report в этом
случае скрывает значения и возвращает `business_metrics.status="incomplete"`.
Он не доказывает правильность SQL/1С-выгрузки и не подменяет методику расчёта:
поставщик данных должен сохранить источник, период, свежесть и права доступа.
Подключение конкретного регистра 1С, расписание экспорта и retention остаются
за доверенным host-интегратором.
