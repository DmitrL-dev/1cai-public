# Источник runtime metrics: экспорт регистра 1С/ERP

`rentgen_core.runtime_source.load_onec_register_export()` проверяет один
retained JSON-файл и возвращает `RuntimeMetricReport`, который принимает
`build_owner_report()`. Это конкретный offline-контракт готовых показателей
регистра: адаптер не запускает 1С, SQL, процессы или сеть, не агрегирует
операционные записи и не рассчитывает бизнес-значения. Доверенный поставщик
сначала выгружает показатели из регистра 1С либо соответствующего источника ERP.

## Формат v1

Все перечисленные поля обязательны; любые дополнительные поля запрещены.

```json
{
  "schema": 1,
  "adapter_id": "onec-register-export-v1",
  "source_ref": "exports/owner-indicators.json",
  "register_id": "InformationRegister.OwnerIndicators",
  "project_id": "12345678-1234-5678-1234-567812345678",
  "snapshot_id": "<64 lowercase hex characters>",
  "commit": "<40 or 64 lowercase hex characters>",
  "source_digest": "<SHA-256 of canonical rows, lowercase hex>",
  "period_start": "2026-09-01T00:00:00Z",
  "period_end": "2026-09-07T23:59:59Z",
  "generated_at": "2026-09-08T00:00:00Z",
  "complete": true,
  "rows": [{
    "row_id": "orders",
    "metric_id": "orders_count",
    "value": 42,
    "unit": "count",
    "period_start": "2026-09-01T00:00:00Z",
    "period_end": "2026-09-07T23:59:59Z",
    "observed_at": "2026-09-08T00:00:00Z"
  }],
  "metrics": [{
    "metric_id": "orders_count",
    "value": 42,
    "unit": "count",
    "period_start": "2026-09-01T00:00:00Z",
    "period_end": "2026-09-07T23:59:59Z",
    "source_id": "InformationRegister.OwnerIndicators",
    "observed_at": "2026-09-08T00:00:00Z"
  }]
}
```

Пример схематический: placeholders необходимо заменить настоящими digest,
snapshot и commit; число 42 иллюстрирует формат, а не полученный бизнес-результат.
`register_id` — тип `InformationRegister`, `AccumulationRegister`,
`AccountingRegister` или `CalculationRegister`, затем точка и имя метаданных
(Unicode-буква или `_` в начале, затем буквы, цифры или `_`). Максимум 128
символов. Значение сохраняется в `source_id` каждой метрики owner-report.
`source_ref` — относительный безопасный locator retained-артефакта, максимум
1024 символа; это provenance, он никогда не открывается как файл или URL.

`row_id` и `metric_id` соответствуют `[a-zA-Z_][a-zA-Z0-9_.-]{0,127}`.
Оба уникальны среди строк. Строка означает один уже вычисленный показатель
регистра за заданный период. Каждая строка обязана иметь ровно одну метрику:
её поля точно совпадают с полями строки без `row_id`, а `source_id` равен
`register_id`. Пропуск, повтор, дополнительная метрика, замена значения,
единицы, периода или времени наблюдения отклоняются. Порядок метрик свободный.

Числа — только JSON integer/float, конечные, модуль не больше `10**15`;
bool и строки с числами запрещены. `unit` — непустой текст до 64 символов.
NaN, Infinity, переполнение float, повторные JSON-ключи на любом уровне,
Unicode-категории `C*` (включая control, format, surrogate), неверный UTF-8,
неизвестные поля и неправильные типы отклоняются.

## Проверяемый digest исходных строк

Digest считается по всем `rows`, включая `row_id`, значения, единицы и даты.
Сначала строки валидируются, затем сортируются лексикографически по `row_id`
(допустимые идентификаторы ASCII). Каноническое представление v1 определяется
следующим точным правилом Python 3.11+:

```python
canonical = json.dumps(
    sorted(rows, key=lambda row: row["row_id"]),
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
).encode("utf-8")
source_digest = hashlib.sha256(canonical).hexdigest()
```

Нет BOM, завершающего перевода строки или Unicode-нормализации. Пробелы,
порядок ключей и порядок строк исходного файла не влияют на digest. Числовые
JSON-токены предварительно разбираются обычным `json.loads`: `1` остаётся int,
`1.0` — float и даёт другой digest; `1e0` и `1.0` дают один float. Float
сериализуется по правилу `json.dumps`, включая `-0.0`. Даты сохраняются как
строки: эквивалентные timezone-записи дают разные digest. Это локальный
versioned-контракт, не заявление о совместимости с RFC 8785.

Вычисленный digest должен совпасть с `source_digest` файла и доверенным
`expected_source_digest`. Самосогласованная замена файла не проходит проверку
при прежнем expected digest. Источник expected digest должен быть независим
от проверяемого файла. Digest связывает report с экспортированными строками,
но не доказывает правильность запроса к базе или подлинность данных в 1С.
Контекст, идентификатор регистра и source_ref проверяются отдельно; digest
строк их не включает.

## Вызов и закрытые по умолчанию проверки

```python
from rentgen_core.runtime_source import load_onec_register_export
from rentgen_core.runtime_metrics import RuntimeFreshnessPolicy
from rentgen_core.owner_report import build_owner_report

runtime = load_onec_register_export(
    retained_absolute_path,
    expected_project_id=project_id,
    expected_snapshot_id=snapshot_id,
    expected_commit=commit,
    expected_source_digest=trusted_rows_digest,
    expected_register_id="InformationRegister.OwnerIndicators",
    expected_source_ref="exports/owner-indicators.json",
    authorize=authorize_runtime_export,
    freshness_policy=RuntimeFreshnessPolicy(max_age_seconds=3600),
)
owner = build_owner_report(
    project_id, snapshot_id, runtime=runtime, authorize=authorize_runtime_export,
)
```

`authorize` — обязательный trusted callback, который при отказе выбрасывает
`CoreError`; его return value не является решением доступа. Он вызывается
до чтения, после JSON parse и непосредственно перед оценкой свежести и
возвратом report. Отзыв на любом этапе прерывает загрузку без результата.

Читается только исходный абсолютный локальный путь без `..`, UNC, device
namespace, alternate data stream или URL. `Path.resolve()` не используется:
никакие ссылки не следуются заранее. `read_retained` удерживает Windows
no-follow handles файла и предков, отвергает reparse points/junctions,
hardlinks и изменённый файл. Нужен fixed local volume; на неподдерживаемой
платформе нет небезопасного fallback. Файл ограничен 2 MiB, каждый массив —
1000 элементов, объект — 32 ключами, структура — глубиной 8. Ошибки чтения,
parse и validation имеют безопасные сообщения; исходные причины подавлены,
чтобы стандартный `traceback.format_exception()` и `CoreError.to_dict()`
не раскрывали строки payload. Ошибки trusted authorization callback и их
причины передаются без изменений; за их содержимое отвечает host-интегратор.

Freshness и period policy делегированы существующему `assess_runtime_report`;
правила описаны в [RUNTIME-METRICS.md](RUNTIME-METRICS.md). Используются
доверенные часы после последнего authorize, по умолчанию текущее UTC.
`as_of` доступен только вызывающему коду для воспроизводимой проверки.
`complete=false`, пустые rows/metrics или частичный период дают report с
`complete=false`; owner-report показывает `incomplete` и скрывает значения.
Stale даёт ошибку без report. Нельзя превратить старые observations в свежие
простым изменением `generated_at`. Повторное потребление после ожидания
требует повторной загрузки или assessment: owner-report сам свежесть не
переоценивает.

| Ошибка | Причина |
| --- | --- |
| `OWNER_RUNTIME_SOURCE_INVALID` | Schema, типы, лимиты, path/read, строки или несоответствие метрик строкам |
| `OWNER_RUNTIME_SOURCE_DIGEST` | Вычисленный digest строк не совпадает с объявленным |
| `OWNER_RUNTIME_CONTEXT` | Экспорт не соответствует trusted project/snapshot/commit/digest/register/source_ref |
| `OWNER_RUNTIME_AUTHORIZATION` | Callback авторизации отсутствует |
| Исходный `CoreError` callback | Доступ отозван |
| `OWNER_RUNTIME_STALE` | Устарела генерация или observation |
| `OWNER_RUNTIME_PERIOD` | Период не соответствует trusted policy |
| `OWNER_RUNTIME_INVALID` | Недопустимые часы, порядок дат или freshness policy |

Адаптер не подключает источник к service/workflow автоматически. Host-интегратор
отвечает за получение экспорта, независимое доверие context/digest, retention,
права и своевременное повторное потребление evidence.

## Trusted retained producer для одного регистра

`rentgen_core.runtime_producer.RetainedRegisterProducer` связывает один заранее
разрешённый retained export с immutable owner receipt. Это bounded offline P1:
producer читает готовые показатели и создаёт квитанцию через существующие
`load_onec_register_export()`, `build_owner_report()` и `OwnerReportStore.save()`.
Он не запускает процессы, SQL или 1С, не открывает сеть и не вычисляет показатели
по операционным данным. В `service_entry` и CLI автоматического подключения нет.

Trusted host создаёт frozen `RetainedRegisterSource` независимо от JSON-файла:

```python
from rentgen_core.owner_report_store import OwnerReportStore
from rentgen_core.runtime_producer import RetainedRegisterProducer, RetainedRegisterSource

store = OwnerReportStore(owned_receipts_directory)
store.initialize()
source = RetainedRegisterSource(
    source_id="owner-indicators",
    export_path=retained_absolute_path,
    project_id=project_id,
    snapshot_id=snapshot_id,
    commit=commit,
    source_digest=trusted_rows_digest,
    register_id="InformationRegister.OwnerIndicators",
    source_ref="exports/owner-indicators.json",
    period_start=period_start,
    period_end=period_end,
    metric_ids=("orders_count", "revenue_amount"),
    max_age_seconds=3600,
)
producer = RetainedRegisterProducer(source, store)
receipt = producer.produce("owner-indicators", authorize=authorize_runtime_export)
```

Один экземпляр разрешает только свой `source_id`; запрос не передаёт путь,
команду, context pins, источник expected digest или policy. Путь открывает
только retained reader с указанными выше no-follow проверками. Значения
`source_ref` и `register_id` из файла не становятся локаторами. Абсолютный путь
источника не включается в receipt. `as_of` в методе `produce` доступен trusted
host для воспроизводимой проверки fixture; его нельзя брать из запроса.

Обе границы периода обязательны и входят в trusted freshness policy. Ожидаемые
`metric_ids` — непустой уникальный tuple из 1–1000 идентификаторов. Нужен точный
набор: пропущенный или лишний показатель отклоняется, даже если trusted digest
обновлён под такой экспорт. `complete=false`, пустые rows и частичный период
не создают receipt. Остальные проверки схемы и canonical digest выполняет
source adapter; исходные rows в retained export не изменяются.

Авторизация выполняется при трёх проверках loader, перед построением owner
report и в двух точках сохранения store. После каждого consumer/store callback
producer повторно оценивает свежесть по закреплённой policy. Исключение trusted
callback и его cause передаются без изменений. Пропущенные права, неверные
pins, неполные или устаревшие данные не дают возвращаемой квитанции.

Сохраняется существующий формат [owner receipt](OWNER-REPORT-STORE.md):
canonical SHA-256 `receipt_id` связывает весь owner report, его context и
source digest; запись через эксклюзивное создание и `fsync` не перезаписывает
старую квитанцию. Каждый успешный запуск создаёт новый UUID receipt. Лимит store
сохраняется — 1000 квитанций, до 2 MiB каждая. Отзыв прав или устаревание на
последней, **после записи**, проверке блокирует возврат, но уже записанный файл
может остаться в host-owned store. Его последующее чтение заново требует прав;
это историческое evidence, а не подтверждение текущей свежести. Producer не
удаляет такие файлы и не доставляет результаты во внешние каналы.

| Дополнительная ошибка | Причина |
| --- | --- |
| `OWNER_RUNTIME_PRODUCER_INVALID` | Неполный или неверный trusted contract |
| `OWNER_RUNTIME_PRODUCER_SOURCE` | Запрошен источник вне заданного allowlist |
| `OWNER_RUNTIME_PRODUCER_INCOMPLETE` | Нет полного ожидаемого набора показателей |

Owned fixture находится в `packaging/fixtures/runtime-register-v1/` и проверяется
`tests/unit/test_runtime_producer.py`. Все значения и context в нём синтетические:
это воспроизводимое evidence offline-контракта, не доказательство live-выгрузки
из регистра 1С, прав реального пользователя или истинности бизнес-показателей.
