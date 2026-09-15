# Журнал подготовки metadata apply

Статус: внутренний Python API и отрицательные проверки preflight. Сам preflight
остаётся read-only. Для единственного квалифицированного файлового сценария
`rename_catalog_attribute` в одном base Designer XML слое добавлен отдельный
[live writer с CAS undo/recovery](METADATA-LIVE-APPLY.md); он не расширяет
полномочия этого preflight API и не заявляет поддержку остальных форматов.

Отдельный внутренний API `metadata_native_apply` выполняет EDT-операцию в новой
принадлежащей операции среде и публикует проверенные байты только в новую
принадлежащую Рентгену файловую копию. Его `applied` не означает live apply;
`live_apply_allowed=false` и `live_source_written=false` обязательны.

`rentgen_core.metadata_apply.preflight_apply` проверяет завершённый сохранённый
preview и записывает намерение до чтения живых файлов. Вызов требует отдельный
канонический UUID операции, UUID preview, точный `preview_id` и `ProjectHead`,
связанный с выбранным `SnapshotRef`. Пути источника и состояния берутся из
контекста проекта; исполняемый файл, URL, инструмент EDT и токен не принимаются.

## Native EDT и принадлежащая копия

`await metadata_native_apply.apply_native_workspace(ctx, preview_operation_id,
operation_id, workspace_root, expected_preview_id=..., expected_plan_id=...,
expected_head=..., timeout=600)` принимает только завершённый сохранённый preview,
точные токены preview/plan, выбранный SnapshotRef и ProjectHead. Поддерживается
существующая операция rename реквизита справочника в одном Designer XML base
слое. Runtime-профиль берётся из preview; передать другой EDT client, executable,
URL, token или произвольный tool через этот API нельзя.

`workspace_root` должен быть новым абсолютным каталогом вне живого источника
и project state. State также обязан находиться вне живого источника. До запуска
EDT создаётся эксклюзивный `metadata-native-apply/<UUID>/intent.json` с SHA256
намерения, точным head, preview/plan/profile, полными inventory hashes и путём
копии. Существующий native operation ID не перезапускается, а существующий
runtime operation нельзя присвоить новой операции. Авторизация проверяется
до чтения входа, во время runtime и перед публикацией; head, настройка слоёв
и полный живой inventory перепроверяются до и после EDT.

До создания native intent, preflight и файловой копии выполняется
`edt_runtime.edt_admission`: общий retained-run/free-space/project-budget gate
резервирует `metadata-runs/<UUID>` единожды, удерживая project slot и проверенный
runtime. `edt_session` принимает внутренний одноразовый handle активного
admission; модель не может передать произвольную квитанцию вместо него. Отказ
quota/admission не оставляет native journal, preflight или owned workspace.
Успешная резервация сохраняется даже при последующем сбое: такой UUID требует
разбора и не запускается заново.

EDT импортирует retained snapshot в новый runtime workspace, экспортирует
baseline, проверяет UUID и владельца и сравнивает **весь** baseline с выбранным
preview до rename. Подтверждение rename использует contentHash только что
полученного native preview. После экспорта и закрытия owned runtime повторно
проверяются UUID/owner, snapshot/layer, все original/baseline/candidate inventories
и оба diff. Любое отличие, включая неизвестный файл, блокирует публикацию.
Положительный ответ EDT сам по себе результата не подтверждает.

Операция удерживает cooperative lock файловой копии во время EDT. Затем
`metadata_workspace.apply_workspace` заново получает lock, проверяет исходное
дерево/head/preview и публикует байты сохранённого candidate, совпавшие с native
экспортом. Существующий writer создаёт backup и журнал отдельных файловых
замен. Его CAS также проверяет изменения между двумя захватами lock.
Нормализация сравнивается точно, но её общая семантическая безопасность этим
не квалифицируется; этот adapter не является отдельным квалифицированным live
executor и не меняет `require_live_apply`, CLI, MCP или команды редактора.

`timeout` — целое число секунд от 1 до 600 для native последовательности.
Сохраняются также ограничения runtime на каждый вызов, число вызовов и размер
вывода. Timeout, отмена, обрыв транспорта, потеря ответа и прерывание публикации
оставляют `OUTCOME_UNKNOWN`; запись не повторяется автоматически. Отсутствующий
terminal result при корректном intent также читается как `OUTCOME_UNKNOWN`:
он может означать активную операцию или сбой. Повреждённый журнал требует
восстановления и не даёт разрешения на повтор. Повтор точного завершённого
запроса возвращает исторический результат без EDT; иной запрос с тем же UUID
вызывает conflict.

`get_native_apply_result(ctx, operation_id)` читает историческую квитанцию.
Для `applied` он заново читает native preview, проверяет `native_preview_id`,
plan/profile и все inventory hashes. Затем под cooperative lock проверяются
ownership marker, сохранённый preflight и полная sealed workspace-result:
result ID, проект/операция/preview, before/after inventories и изменённые пути.
Текущее дерево должно совпадать с candidate, либо с original при подтверждённой
связанной undo-квитанции. Утраченный или подменённый результат, повреждённая
привязка и чужие байты вызывают отказ вместо возврата `applied`. Чтение не
восстанавливает отсутствующие квитанции и не запускает EDT.
`undo_native_workspace(ctx, operation_id, workspace_root)` явно восстанавливает
backup подтверждённого apply только при совпадении дерева с candidate.
`restore_native_workspace(...)` восстанавливает **original** после прерванной
локальной публикации; он не повторяет EDT и не продолжает публикацию candidate.
Если собственная квитанция native adapter потеряна после завершения файлового
apply, restore использует сохранившийся complete workspace receipt для CAS undo.
Если `workspace-result.json` уже immutable и дерево точно совпадает с candidate,
а перед финальным `os.replace` остался полный bound
`workspace-state.json.tmp` с тем же `result_id`, restore сначала атомарно
досублирует этот state через workspace recovery и затем выполняет CAS undo.
Повреждённый, чужой или иного phase `.tmp` остаётся `OUTCOME_UNKNOWN` и
`METADATA_WORKSPACE_RECOVERY_REQUIRED`; EDT повторно не запускается.
Если native вызов прервался до файловой публикации, исходная копия сохранена,
а незавершённый EDT workspace остаётся для разбора. Чужие изменения вызывают
conflict и не перезаписываются. Успешный undo/restore имеет собственную
workspace-квитанцию и не переписывает исторический native result.
Если прерывание произошло уже после записи фазы `undoing`,
`restore_native_workspace` сначала передаёт workspace в core recovery к
`original`; это завершает только начатый CAS undo и также не запускает EDT.

## Read-only preflight

Поддержанный состав проверки — один слой Designer XML типа base с корнем `.`.
Каталог состояния должен находиться вне живого дерева источников: этот срез не
реализует исключения вложенного state при обходе. Иной текущий состав слоёв
не проходит проверку свежести. Runtime не запускается, профиль EDT не получает
новых полномочий, candidate не копируется в живой источник.

```python
from uuid import uuid4

from rentgen_core import get_project_head
from rentgen_core.metadata_apply import preflight_apply, get_apply_result
from rentgen_core.metadata_runs import get_preview

preview = get_preview(ctx, preview_operation_id)
operation_id = str(uuid4())
result = preflight_apply(
    ctx,
    preview_operation_id,
    operation_id,
    expected_preview_id=preview["preview_id"],
    expected_head=get_project_head(ctx),
)
assert result["live_source_written"] is False
assert get_apply_result(ctx, operation_id) == result
```

## Проверяемые привязки

Намерение содержит проект, UUID операции, исходный head с ревизией настройки
источников и SnapshotRef, зарегистрированный корень, preview/plan/profile ID и
отдельные SHA256 полных инвентарей original, baseline и candidate. Сохранённые
байты и UUID владельца/реквизита перепроверяются через существующий `get_preview`.
Живой полный инвентарь, включая неизвестные файлы, сравнивается с **original**;
импортированный EDT baseline не заменяет исходное состояние для этой проверки.

Права `project:read`, `source:edit`, `analysis:run` проверяются до разбора запроса,
перед созданием операции, во время обхода и перед записью результата. Файлы и
каталоги открываются через существующие Windows no-follow/pinning механизмы.
Существующие файлы удерживаются при повторной инвентаризации; наличие новых
файлов проверяется повторным полным обходом. Это наблюдение состояния, а не
эксклюзивное владение внешним workspace и не разрешение будущей записи.

## Журнал и повторный вызов

В `<project-state>/metadata-apply/<operation-id>/` создаются два файла:

- `intent.json`: неизменяемое намерение с `intent_id` (SHA256 канонического JSON).
- `result.json`: результат проверки с привязкой к намерению и собственным SHA256.

Каталог операции создаётся эксклюзивно, записи используют `xb`, flush и fsync.
Параллельный вызов с тем же ID не выполняет проверку повторно. Эти механизмы
сохраняют результаты при перезапуске процесса; гарантия против потери питания
и атомарность записи нескольких живых файлов этим срезом не заявляются.
Хэши обнаруживают несогласованные изменения, но не являются подписью против
кода, работающего от той же учётной записи ОС.

Точный повтор завершённого запроса возвращает историческую квитанцию. Новый
preview, другой head или другой запрос с прежним ID вызывает
`METADATA_APPLY_CONFLICT`. Новый запуск проверки требует нового ID. Сам факт
чтения прежней квитанции не подтверждает свежесть текущего живого источника.

| Результат | Значение |
|---|---|
| `unavailable` | Проверки свежести прошли, но live apply не реализован, нормализация не квалифицирована. |
| `stale` | Head, настройка слоёв либо живые байты отличаются от ожидаемых. |
| `revoked` | Во время проверки отозваны требуемые права; вызов также возвращает ошибку доступа. |
| `failed` | Проверка завершилась другой контролируемой ошибкой; причина содержит код ошибки. |

Во всех допустимых preflight-квитанциях `live_source_written=false`. Статусы
`applied` и `undone` относятся только к отдельному live writer.

## Прерывание и восстановление

Нет намерения, нет результата, файл усечён, хэш или схема не совпадают — чтение
и повторный запуск завершаются `METADATA_APPLY_RECOVERY_REQUIRED`. Незнакомый
исход не переводится в успех или разрешение повторной записи. Исходный журнал
не удаляется и не перезаписывается. Исключение ОС или остановка процесса могут
оставить именно такое незавершённое состояние.

Этот модуль версии схемы 1 сам остаётся read-only и не восстанавливает живые
файлы из своего журнала. Для разбирательства preflight сохраняют журнал и
retained preview, проверяют версии исполнителя и состояние проекта. Ограниченный
live writer ведёт отдельный журнал и recovery-квитанцию, описанные в
[`METADATA-LIVE-APPLY.md`](METADATA-LIVE-APPLY.md).

`apply_metadata(ctx, operation_id)` повторно проверяет текущие права, выбранный
snapshot, retained preview и живой источник. Устаревшее состояние вызывает
`METADATA_APPLY_STALE`; стабильное — `METADATA_LIVE_APPLY_UNAVAILABLE`. Эта проверка
не меняет историческую квитанцию preflight.

`undo_metadata(ctx, operation_id)` требует доступ к существующей квитанции, затем
возвращает `METADATA_UNDO_UNAVAILABLE`: у preflight нет квитанции применения и
принадлежащего операции результата для восстановления. Чужая последующая правка
никогда не заменяется baseline. Проверка undo conflict между текущим
состоянием и подтверждённым результатом apply реализована только для новой
принадлежащей Рентгену копии в `metadata_workspace` и `metadata_native_apply`.

## Граница приёмки

Unit-тесты используют собственную конфигурацию и реальное локальное состояние
проекта. Проверяются неизменность живых байтов/head, stale после edit/add/delete
и смены head/настройки, конфликт ID, отзыв прав, повреждения журнала, остановка до
квитанции и запрет apply/undo. Это тесты протокола подготовки, не доказательство
успешной записи EDT или 1С. CLI-команды и MCP-инструменты bounded live writer
перечислены в [`METADATA-LIVE-APPLY.md`](METADATA-LIVE-APPLY.md); observer и
типовые конфигурации в этот срез не интегрированы.

Для live apply необходимы квалификация нормализации, квалифицированный executor,
протокол публикации в управляемый живой проект, re-read EDT/1С и восстановление
точного baseline с проверкой последующей чужой правки. Owned workspace protocol
и его native smoke описаны выше; они не предоставляют live capability.
Основание: [EDT-METADATA-DESIGN.md](EDT-METADATA-DESIGN.md)
и [EDT-ADAPTER-PLAN.md](EDT-ADAPTER-PLAN.md).
