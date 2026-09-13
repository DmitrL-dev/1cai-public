# Принадлежащая рабочая копия metadata

`rentgen_core.metadata_workspace` добавляет файловый writer с журналом для отдельной
директории, явно созданной Рентгеном. Это безопасный слой подготовки и проверки
изменений: зарегистрированный `source_root`, рабочая база 1С и live EDT никогда
не изменяются этим API.

## Жизненный цикл

1. `create_workspace(ctx, operation_id, path)` требует завершённый preflight и
   копирует точный `original` inventory в новую директорию `tree/`. В корне
   создаётся sealed marker с project/preview/source binding и полным digest.
2. `apply_workspace(...)` повторно проверяет права, head, preview и исходный
   digest workspace. Candidate экспорт проверяется по полному inventory. Перед
   заменой создаются `backup/`, `stage/` и durable state `phase="applying"`.
   Файлы заменяются через `os.replace`, удалённые candidate пути удаляются, затем
   фактический inventory перечитывается и записывается immutable receipt.
3. `undo_workspace(...)` принимает только receipt со статусом `applied` и точное
   совпадение candidate inventory. Чужая правка, видимая при этой проверке, даёт
   `METADATA_UNDO_CONFLICT`. До записи `undoing` полный backup inventory должен
   совпасть с original: повреждение, пропуск и посторонний файл останавливают
   операцию до изменения дерева. Исходные байты копируются с проверкой хэшей в
   `.rentgen-undo-stage`, затем заменяют файлы дерева. Backup не потребляется;
   stage очищается после durable undo receipt и complete state.

4. `recover_workspace(..., target="original"|"candidate")` продолжает
   прерванный `apply` только после проверки sealed backup, сохранённого preview
   и отсутствия чужих байтов. `original` возвращает копию к baseline и оставляет
   apply доступным для нового запуска; `candidate` завершает применение и выдаёт
   receipt с `recovered=true`. Выбор цели обязателен, recovery не читает live
   source и не пытается угадывать, что хотел сделать предыдущий процесс.

   Для прерванного `undo` разрешён только `--target original`: он перепроверяет
   привязки state/receipt, полный backup, stage из целых проверенных файлов и
   дерево, затем завершает отмену и публикует отдельную recovery receipt.
   Обрыв внутри записи отдельного stage-файла или receipt остаётся
   `RECOVERY_REQUIRED` для ручного разбора. `candidate` отклоняется после
   намерения undo; возврат к candidate не является повтором отмены.
   Если undo receipt уже существует, дерево должно точно совпасть с original —
   последующая правка не восстанавливается поверх неё. Проверенные полные `.tmp`
   state/recovery receipts завершаются только через явный recovery; повреждённые
   записи требуют ручного разбора. Повтор завершённого recovery идемпотентен.

Незавершённая фаза `applying` или `undoing`, отсутствующий backup, временный
receipt либо несовпадение digest останавливают обычный apply/undo.
Повторный вызов не пытается угадать исход и не запускает автоматический replay.
Если candidate уже записан и процесс прервался перед финальным state receipt,
`recover --target candidate` проверяет результат по digest и завершает journal
идемпотентно; выбор `original` в этом состоянии отклоняется до явного undo.
Все операции требуют `project:read`, `source:edit`, `analysis:run`.

## CLI

После `metadata-preview` и успешного `metadata` preflight принадлежащую копию
можно использовать без редактора:

```text
rentgen metadata-workspace-create --registry REGISTRY --project PROJECT \
  --snapshot SNAPSHOT --operation-id OPERATION --workspace WORKSPACE
rentgen metadata-workspace-apply --registry REGISTRY --project PROJECT \
  --snapshot SNAPSHOT --operation-id OPERATION --workspace WORKSPACE
rentgen metadata-workspace-undo --registry REGISTRY --project PROJECT \
  --snapshot SNAPSHOT --operation-id OPERATION --workspace WORKSPACE
rentgen metadata-workspace-status --registry REGISTRY --project PROJECT \
  --snapshot SNAPSHOT --operation-id OPERATION --workspace WORKSPACE
rentgen metadata-workspace-recover --registry REGISTRY --project PROJECT \
  --snapshot SNAPSHOT --operation-id OPERATION --workspace WORKSPACE \
  --target original|candidate
```

Команды требуют точный snapshot и исходный operation ID; workspace path задаёт
доверенный вызывающий код. Все ответы возвращаются одним JSON-конвертом. Эти
команды записывают только принадлежащую копию и не превращают preflight в
разрешение изменения live source или базы 1С.

## Граница доказательства

Проверяется реальная запись файлов в принадлежащую копию, inventory preconditions,
backup, замена отдельного файла, re-read, undo и явное восстановление после
частичной операции. Поле
`workspace_source_written=true` отделено от `live_source_written=false`.
Это не разрешение записи в зарегистрированный source root, не импорт в EDT и не
проверка компиляции/данных 1С. Для D1/D2 нужен следующий адаптер: тот же intent и
receipt протокол должен работать через квалифицированный EDT/1С writer на новой
рабочей базе, с native re-read, формами, данными, конфликтом чужой правки и
восстановлением после сбоя процесса.

Остаточная граница: между проверкой inventory и `os.replace`/удалением нет
эксклюзивной защиты от внешнего писателя или второго workspace caller. Поэтому
конкурентная чужая правка во время операции может быть потеряна; это не полный
CAS-протокол и не атомарная транзакция над деревом. Каталоги workspace также
не удерживаются на весь цикл публикации/очистки. До устранения этой границы
нельзя переносить writer на live source. Backup после undo сохраняется для
разбора; автоматический GC и recovery старого undo с уже потреблённым backup
не реализованы. Сохранность при потере питания отдельно не квалифицирована.

Регрессии находятся в `tests/unit/test_metadata_workspace.py`: apply/undo,
stale workspace, foreign change, explicit original/candidate apply recovery,
corrupt/missing/foreign backup, undo stage, прерывания замены файлов и публикации
undo/state/recovery receipts. Операция не принимает
пути или команды от модели; путь workspace задаёт доверенный вызывающий код.
