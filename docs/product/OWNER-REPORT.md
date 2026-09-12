# Owner report

`rentgen_core.owner_report.build_owner_report()` собирает один ограниченный
отчёт для владельца проекта из двух независимых источников: состояния Git/BSL
находок и typed runtime evidence. Функция не запускает 1С, SQL, модель или
сеть. Runtime adapter передаёт `RuntimeMetricReport` и обязан предоставить
авторизационный callback; project, snapshot, commit, период и digest источника
проверяются до выдачи значений.

```python
from rentgen_core.owner_report import build_owner_report

report = build_owner_report(
    project_id,
    snapshot_id,
    findings=finding_state,
    runtime=runtime_report,
    authorize=authorize_runtime_read,
)
```

`RuntimeMetric` содержит стабильный идентификатор, числовое значение с жёстким
лимитом, единицу измерения, период, источник и время наблюдения. Повторяющаяся
пара `(source_id, metric_id)`, невалидная дата, перевёрнутый период, чужой
snapshot/commit или неподтверждённый callback отклоняются. Порядок findings и
metrics детерминированный, документы и коллекции ограничены.

Если runtime report неполный, отчёт возвращает `business_metrics.status` со
значением `incomplete` и пустой `metrics`; значения не маскируются нулями. Если
adapter не подключён, статус — `not_available`. Поэтому текущий public core уже
имеет формат owner report, но бизнес-данные появятся только после отдельного
проверенного runtime adapter и его evidence-пакета.

Это контракт агрегации, а не доказательство прав или истинности внешней базы:
вызывающий слой должен авторизовать чтение и связать report с фактически
проверенным runtime. Сохранение отчётов, уведомления, SQL/1С adapters и
retention policy остаются следующими этапами.
