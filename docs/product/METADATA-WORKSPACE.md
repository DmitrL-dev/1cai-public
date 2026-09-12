# Принадлежащая рабочая копия metadata

`rentgen_core.metadata_workspace` добавляет транзакционный writer для отдельной
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
3. `undo_workspace(...)` принимает только receipt со статусом `applied` и CAS
   по candidate inventory. Любая чужая правка даёт `METADATA_UNDO_CONFLICT`;
   baseline не перезаписывает новые байты молча. После проверки backup исходный
   inventory восстанавливается и выдаётся отдельная sealed undo receipt.

Незавершённая фаза `applying` или `undoing`, отсутствующий backup, временный
receipt либо несовпадение digest дают `METADATA_WORKSPACE_RECOVERY_REQUIRED`.
Повторный вызов не пытается угадать исход и не запускает автоматический replay.
Все операции требуют `project:read`, `source:edit`, `analysis:run`.

## Граница доказательства

Проверяется реальная запись файлов в принадлежащую копию, stale/CAS, backup,
atomic replacement, re-read, undo и остановка после частичной операции. Поле
`workspace_source_written=true` отделено от `live_source_written=false`.
Это не разрешение записи в зарегистрированный source root, не импорт в EDT и не
проверка компиляции/данных 1С. Для D1/D2 нужен следующий адаптер: тот же intent и
receipt протокол должен работать через квалифицированный EDT/1С writer на новой
рабочей базе, с native re-read, формами, данными, конфликтом чужой правки и
восстановлением после сбоя процесса.

Регрессии находятся в `tests/unit/test_metadata_workspace.py`: apply/undo,
stale workspace, foreign change и interruption recovery. Операция не принимает
пути или команды от модели; путь workspace задаёт доверенный вызывающий код.
