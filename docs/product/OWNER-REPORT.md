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

Для локального observer готовая quality-история собирается без повторного Git
или LLM-запуска:

```python
report = observer.owner_report(snapshot_id, max_findings=1000)
```

Метод читает durable `finding_state`, требует опубликованный snapshot и права
`project:read` + `analysis:run`, повторяет проверку прав перед возвратом и
оставляет `business_metrics` в `not_available`, пока вызывающий runtime adapter
не передаст подтверждённый `RuntimeMetricReport`. `record_findings()` должен
получить `snapshot_id` для явной записи связи анализа с опубликованным
snapshot; без этой связи quality возвращается как
`quality_snapshot_binding_unverified`. Такой binding фиксирует утверждение
вызывающего слоя отдельно для каждого Git commit и не доказывает соответствие
этого commit содержимому snapshot: в текущем каталоге snapshot отсутствует
отдельный Git commit. Исторический replay не меняет binding текущего состояния.

`max_findings` ограничивает размер owner report от 1 до 10 000 и по умолчанию
равен 1 000. История observer может содержать до 10 000 записей; при
превышении выбранного лимита отчёт останавливается с `OWNER_REPORT_LIMIT`,
пока вызывающий слой явно не поднимет параметр.

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

Для durable хранения уже построенного отчёта используйте
`rentgen_core.owner_report_store.OwnerReportStore`. Store создаётся в отдельном
каталоге, удерживает блокировку и проверенный дескриптор `reports`, пишет
immutable UUID receipts через эксклюзивное создание и `fsync`, а затем повторно
проверяет project/snapshot и авторизацию при `get`/`list`. Чужой файл,
повреждённая квитанция или превышение лимита останавливают чтение;
автоудаления и сетевой доставки нет. Контракт приведён в
[OWNER-REPORT-STORE.md](OWNER-REPORT-STORE.md).

Это контракт агрегации, а не доказательство прав или истинности внешней базы:
вызывающий слой должен авторизовать чтение и связать report с фактически
проверенным runtime. Уведомления, SQL/1С adapters и retention policy остаются
следующими этапами.
