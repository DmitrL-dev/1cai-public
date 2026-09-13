# Runtime metrics adapter

`rentgen_core.runtime_metrics.load_runtime_report()` принимает один JSON-файл,
выгруженный доверенным источником данных 1С или ERP. Адаптер не подключается к
базе, не запускает 1С и не выполняет сеть: он читает ограниченный retained
файл и строит совместимый `RuntimeMetricReport` для owner-report.

```python
from rentgen_core.runtime_metrics import RuntimeFreshnessPolicy, load_runtime_report
from rentgen_core.owner_report import build_owner_report

policy = RuntimeFreshnessPolicy(
    max_age_seconds=3600,
    expected_period_start=period_start,
    expected_period_end=period_end,
)
runtime = load_runtime_report(
    export_path,
    expected_project_id=project_id,
    expected_snapshot_id=snapshot_id,
    expected_commit=commit,
    expected_source_digest=source_digest,
    authorize=authorize_runtime_export,
    freshness_policy=policy,
)
report = build_owner_report(
    project_id, snapshot_id, runtime=runtime, authorize=authorize_runtime_export,
)
```

Файл имеет schema `1` и содержит `adapter_id`, `source_ref`, project/snapshot/
commit/source digest, период, `generated_at`, флаг `complete` и массив метрик.
Каждая метрика содержит `metric_id`, конечное числовое значение, единицу,
период, `source_id` и `observed_at`. Неизвестные поля, дублирующиеся ключи,
невалидные даты, чужой контекст и повторяющиеся идентичности отклоняются.
Project, snapshot, commit и source digest должны точно совпадать с ожидаемыми
значениями вызывающего кода. Это проверка привязки доверенного evidence,
а не вычисление или доказательство соответствия digest данным внешней базы.

Размер файла ограничен 2 MiB, число метрик — 1000; число проверяется до
конструирования метрик. Авторизация проверяется до чтения и повторно перед
возвратом результата. Свежесть проверяется после второй авторизации, чтобы
ожидание внутри callback не продлевало срок годности evidence.

## Политика свежести и периода

Политику задаёт доверенный вызывающий код, поля политики в JSON запрещены.
Без параметра используется `RuntimeFreshnessPolicy()`: возраст выгрузки и
каждого наблюдения не более 86400 секунд, длительность периода не более
366 суток. Оба лимита — целые числа от 1 до 31622400 секунд; булевы значения
не принимаются. Ровно на границе возраста данные ещё свежие.

Ожидаемый период задаётся только парой `expected_period_start` и
`expected_period_end`; обе границы должны точно совпадать по времени с
границами отчёта. Эквивалентные часовые пояса допустимы. Без ожидаемого периода
исторический период разрешён, если сами наблюдения свежие: возраст периода
не равен возрасту evidence. Нулевой по длительности период разрешён для
показателя на конкретный момент времени.

Для каждой метрики обязательны `period_end <= observed_at <= generated_at`;
время генерации не раньше конца периода отчёта и не позже времени проверки.
Невозможный порядок дат отклоняется. `complete=false`, пустой массив или
метрика с периодом, покрывающим лишь часть периода отчёта, дают `incomplete`.
Loader возвращает их с `complete=false`, поэтому owner-report скрывает
значения и возвращает `business_metrics.status="incomplete"`.

Просроченная генерация или хотя бы одно просроченное наблюдение дают `stale`.
Этот статус имеет приоритет над `incomplete`. Повторная выгрузка старых
наблюдений с новым `generated_at` не восстанавливает доступность. Loader
завершается с `OWNER_RUNTIME_STALE` и не возвращает report: устаревшие значения
нельзя случайно передать в owner-report как `available` через этот вызов.

| Результат оценки | Поведение loader |
| --- | --- |
| `available`, reason `None` | Возвращает полный `RuntimeMetricReport` |
| `incomplete`, reason `runtime_report_incomplete` | Возвращает report с `complete=false` |
| `stale`, reason `runtime_report_stale` | Ошибка `OWNER_RUNTIME_STALE` без report |
| Неверный порядок дат, timezone, clock или policy | Ошибка `OWNER_RUNTIME_INVALID` |
| Период не совпадает с policy или превышает лимит | Ошибка `OWNER_RUNTIME_PERIOD` |
| Чужой project/snapshot/commit/source digest | Ошибка `OWNER_RUNTIME_CONTEXT` |

Отдельный `assess_runtime_report(runtime, freshness_policy=policy)` возвращает
`RuntimeMetricAssessment` с полями `status` и `reason`, без бизнес-значений.
Оценка не заменяет авторизацию и проверку ожидаемого контекста в loader.
Её можно использовать для диагностики или повторной проверки уже загруженного
report; не передавайте его в owner-report при статусе, отличном от `available`.

Loader и assessment принимают необязательный keyword `as_of` — строку даты
с часовым поясом для воспроизводимых тестов или исторических расчётов. Это
доверенные часы вызывающего кода, не поле входной выгрузки. По умолчанию
используется текущее UTC-время.

## Границы интеграции

Сигнатуры прежних аргументов loader и конструктор `RuntimeMetricReport`
сохранены. Однако прежний `complete=true` теперь недостаточен для успешной
загрузки: устаревшие exports отвергаются по умолчанию. Политика не сохраняется
в dataclass, owner-report или квитанцию. Перед каждым новым потреблением,
после отложенной авторизации или длительного ожидания вызывающий код обязан
заново загрузить evidence либо повторить assessment с той же доверенной
политикой. Сам `build_owner_report()` и чтение исторических receipts не
переоценивают свежесть; их API в этом срезе не менялся.

Typed report, возвращённый для неполных данных, сохраняет исходные значения
для авторизованного адаптера; готовый owner-report их скрывает. Результат
loader — evidence на момент проверки, а не бессрочное разрешение публикации.

Адаптер не доказывает правильность SQL/1С-выгрузки и не подменяет методику
расчёта. Поставщик данных должен подтвердить источник, период, свежесть и
права доступа. Подключение конкретного регистра 1С, расписание экспорта и
retention остаются за доверенным host-интегратором.
