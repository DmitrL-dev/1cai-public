# Live apply для Designer XML

В ветке разработки появился первый writer, который меняет зарегистрированное
дерево исходников напрямую, без GUI Конфигуратора и без вызова EDT. Он работает
только с уже сохранённым preview операции `rename_catalog_attribute`.

```python
from rentgen_core.metadata_live_apply import apply_live, undo_live

receipt = apply_live(ctx, operation_id)
assert receipt["status"] == "applied"
undo = undo_live(ctx, operation_id)
assert undo["status"] == "undone"
```

CLI имеет те же явные границы:

```text
rentgen metadata-live-apply  --registry ... --project ... --snapshot ... --operation-id ...
rentgen metadata-live-status  --registry ... --project ... --snapshot ... --operation-id ...
rentgen metadata-live-undo   --registry ... --project ... --snapshot ... --operation-id ...
rentgen metadata-live-recover --registry ... --project ... --snapshot ... --operation-id ... --target original
```

Перед записью ядро повторно проверяет права `project:read`, `source:edit` и
`analysis:run`, selected snapshot/head, полный inventory живого дерева и
сохранённый preview. Разрешён ровно один base-слой `designer_xml`; candidate
не может добавлять пути, а каждая изменённая строка должна быть `modified` в
preview edit. Нормализация, выраженная удалением файлов из EDT candidate,
сохраняется как исходный файл, поэтому сторонние модули не пропадают.
Source-root и state-root должны находиться на одном файловом томе: иначе
`os.replace` между journal stage и исходником не даёт атомарной замены.
Такое размещение отклоняется до создания live journal кодом
`METADATA_LIVE_APPLY_UNSUPPORTED`.

Внешний state-root содержит
`metadata-live-apply/<operation-id>/intent.json`, `backup/`, `stage/`,
`state.json` и запечатанный `result.json`. Один OS lock сериализует writers.
Backup и candidate fsync-ятся до публикации, файлы заменяются атомарным
`os.replace`, а после замены выполняется полный re-read inventory.

`undo_live` — compare-and-swap: он работает только если дерево полностью
совпадает с сохранённым after inventory. Любая чужая правка вызывает
`METADATA_LIVE_UNDO_CONFLICT` и оставляет дерево как есть. Потеря процесса
между заменами оставляет статус `OUTCOME_UNKNOWN`; повторный apply запрещён.
`recover_live(..., target="original")` восстанавливает только запечатанный
backup и после полного re-read выдаёт `recovered`.
Прерванные Undo и Recover тоже дают `OUTCOME_UNKNOWN`: прежний `applied`
result больше не считается завершением при фазе `undoing`. Повторный Recover
проверяет содержимое своего staging-каталога, восстанавливает уже перенесённые
файлы из backup и продолжает. Короткий файл после прерванной записи
пересоздаётся только из проверенного backup; неожиданный файл или изменённый
staged-файл той же длины блокирует операцию для разбора владельцем.
Корректные временные записи `state.json.tmp` и `result.json.tmp` после
прерывания сверяются с операцией, result ID и ожидаемым inventory перед
завершением Recover. Повреждённые или конфликтующие записи не применяются
автоматически.

Статусы `applied`, `undone` и `recovered` имеют `live_source_written=true`.
Повреждённый или перепривязанный journal блокирует чтение кодом
`METADATA_LIVE_RECOVERY_REQUIRED`.

## Проверка на зарегистрированном дереве — 15 сентября 2026

На принадлежащем EDT-профиле выполнен новый apply→undo по тому же retained
preview. Writer изменил два candidate-файла в зарегистрированном Designer XML
дереве, после чего CAS undo вернул полный исходный inventory:

```text
operation: 0da267cc-bb83-46bf-882a-3c27d3afa76c
before:    e4099571515b28588939bd20df1b29deb39d76dbb16b21b4a8012eaf12de254b
after:     8dc3cbb4b4fe91c32543d29125f600565a2ac1052da4173e6b294da7d083cd5c
restored:  e4099571515b28588939bd20df1b29deb39d76dbb16b21b4a8012eaf12de254b
```

Перед этим исправлена проверка границы EDT: нормализация `original → baseline`
допускается только для тех же путей, которые явно изменены в edit
`baseline → candidate`; неподдержанные и неподтверждённые изменения по-прежнему
останавливаются до записи. Машинная квитанция с result IDs и ограничениями —
[`metadata-live-source-20260915.json`](evidence/metadata-live-source-20260915.json).

В том же профиле отдельный запуск с отказом на второй замене получил
`OUTCOME_UNKNOWN`; явный `recover_live(target="original")` восстановил исходный
inventory (`before` и `after_recovery` совпали). Эта проверка зафиксирована в
[`metadata-live-source-interruption-20260915.json`](evidence/metadata-live-source-interruption-20260915.json).

Это доказательство записи исходного Designer XML дерева, а не обновления живой
информационной базы 1С. Платформенный импорт/проверка, расширения, `.cf/.cfe`,
формы/СКД и внешние конкурентные writers остаются отдельной матрицей.

## Что пока не входит

Writer не принимает binary `.cf/.cfe`, EDT `.mdo` или `MetaDataObject/*.xml`,
extensions, новые/удалённые объекты, candidate с независимой нормализацией-
модификацией,
формы и СКД как самостоятельные операции. Для них нужны отдельные producer,
полная матрица платформенных проверок и такой же доказанный rollback.
Ручной preflight API в [`METADATA-APPLY.md`](METADATA-APPLY.md) остаётся
read-only и не получает полномочий live writer автоматически.
