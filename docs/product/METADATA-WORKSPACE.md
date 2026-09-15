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
Если immutable `workspace-result.json` уже существует, а полный sealed
`workspace-state.json.tmp` содержит тот же bound `phase="complete"` и
`result_id`, recovery может атомарно досублировать этот state и продолжить
CAS undo. Любой другой phase, binding, digest, дерево или receipt остаётся
`METADATA_WORKSPACE_RECOVERY_REQUIRED`; при изменённом candidate tree действует
отдельный `METADATA_WORKSPACE_CONFLICT`. EDT повторно не запускается.
Native restore при state или полном временном state с фазой `undoing`
делегирует этот же recovery к `original`, не выполняя EDT повторно.
Все операции требуют `project:read`, `source:edit`, `analysis:run`.

`apply`, `undo` и `recover` удерживают отдельный `workspace-operation.lock`
на весь цикл, включая проверку preconditions, staging, публикацию receipts и
cleanup. В Windows используется `msvcrt` byte-range lock, в POSIX предусмотрен
`flock`: одна неблокирующая попытка, занятый lock даёт `METADATA_WORKSPACE_BUSY`.
Lock не удаляется после операции и освобождается ОС при закрытии процесса.
Каталог, reparse point/симлинк, hardlink или неполный lock дают
`METADATA_WORKSPACE_LOCK_INVALID`; их содержимое не исправляется автоматически.
Создание workspace по-прежнему резервирует новое имя через атомарный `mkdir`.

До создания lock проверяются canonical root, допустимое расположение, identity
root/tree и marker: bounded read-only чтение обычного файла, seal и привязка к
project/operation/source_root. Отсутствующий, чужой, повреждённый или linked marker
отклоняется без записи lock/state/tree. Это чтение не удерживает directory pin;
retained marker не читается и root не pin-ится contender-ом.
На Windows этот admission-критический участок дополнительно сериализуется
именованным mutex, чьё имя строится из проверенной `(st_dev, st_ino)` identity
root. Alias пути, включая `\\?\\`, используют тот же mutex; занятый mutex даёт
`METADATA_WORKSPACE_BUSY` до создания file lock. Поэтому admission-read не может
удержать квитанцию параллельно публикации другого вызова Rentgen.
После захвата lock API заново читает marker/state/inventory. Перед записью или
заменой файла, публикацией receipt, удалением и cleanup перепроверяются права,
identity lock/root/tree и отсутствие обнаруженных links в пути публикации.
Windows pin удерживает родительский каталог root: pin самого root несовместим
с заменой receipts. Эти проверки обнаруживают уже произошедшую подмену пути,
но не превращают проверку и следующий системный вызов в одну атомарную операцию.

### Привязка квитанций и старые журналы

Новые state/recovery receipts, включая временные `.tmp`, содержат точный
канонический `workspace_root` и `marker_id`. Перед мутацией и при чтении статуса
проверяются эти поля, сохранённые intent/preview, inventories и ссылки state на
result/undo. Поэтому квитанция соседнего workspace отклоняется даже при одинаковых
operation ID и байтах candidate. Формат result/undo сохранён: их собственный
`workspace_root` и ссылки на них проверяются вместе с привязанным state/recovery.
Подмена квитанции даёт `METADATA_WORKSPACE_RECOVERY_REQUIRED` до записи; если
lock отсутствует, проверка происходит до его создания.

Для прежних записей schema 1 без root/marker сохраняется узкая совместимость:
complete-state принимается только с точной ссылкой на проверенный локальный
result либо undo, содержащий `workspace_root`. Завершённая legacy undo-recovery
дополнительно должна точно воспроизводиться из локального undo receipt, включая
его неизменяемую временную отметку. Обычные чтение и replay не переписывают такие
файлы. Старые `applying`/`undoing` и recovery без независимой локальной привязки
остаются `METADATA_WORKSPACE_RECOVERY_REQUIRED` для ручного разбора: совпадение
digest само по себе не доказывает принадлежность рабочей копии. Автоматическая
миграция недоказуемых записей не выполняется.

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

Остаточная граница: внешние писатели, игнорирующие `workspace-operation.lock`,
не исключены между проверкой inventory/identity и `os.replace`/удалением.
Их конкурентная правка во время операции может быть потеряна; это не полный
CAS-протокол и не атомарная транзакция над деревом. Вложенные каталоги workspace
не удерживаются на весь цикл публикации/очистки. До устранения этой границы
нельзя переносить writer на live source. Backup после undo сохраняется для
разбора; автоматический GC и recovery старого undo с уже потреблённым backup
не реализованы. Сохранность при потере питания отдельно не квалифицирована.

Регрессии находятся в `tests/unit/test_metadata_workspace.py`: apply/undo,
stale workspace, foreign change, explicit original/candidate apply recovery,
corrupt/missing/foreign backup, undo stage, прерывания замены файлов и публикации
undo/state/recovery receipts.
Также проверены busy admission каждого mutation API, lock в отдельном процессе,
release после ошибки, отказ для hardlink/каталога/пустого lock и подмена tree
до публикации state. POSIX fallback не квалифицирован этим Windows-прогоном.
Отдельный публичный caller во время замены state получает BUSY до retained-чтения
marker, не создавая мешающий активному writer-у directory pin. Для отсутствующего,
чужого, malformed/oversized и linked marker проверен отказ каждого mutation API
без изменения байтов и состава каталога.
Операция не принимает
пути или команды от модели; путь workspace задаёт доверенный вызывающий код.
