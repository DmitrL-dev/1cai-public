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

Статусы `applied`, `undone` и `recovered` имеют `live_source_written=true`.
Повреждённый или перепривязанный journal блокирует чтение кодом
`METADATA_LIVE_RECOVERY_REQUIRED`.

## Что пока не входит

Writer не принимает binary `.cf/.cfe`, EDT `.mdo` или `MetaDataObject/*.xml`,
extensions, новые/удалённые объекты, candidate с нормализацией-модификацией,
формы и СКД как самостоятельные операции. Для них нужны отдельные producer,
полная матрица платформенных проверок и такой же доказанный rollback.
Ручной preflight API в [`METADATA-APPLY.md`](METADATA-APPLY.md) остаётся
read-only и не получает полномочий live writer автоматически.
