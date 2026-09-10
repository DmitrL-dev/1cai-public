# Обновление project state: schema 1 → 2

Этот runner предназначен для локально зарегистрированного project state. Он
сохраняет проверенную SQLite-копию schema 1 перед вызовом существующей миграции.
Он не импортирует legacy graph/JSON и не приписывает старым approvals/tests новые
source snapshots. Эти задачи остаются в E3 плана cutover.

## Запуск

Остановите старые writers на время административного cutover. Runner поддерживает
корректную SQLite-копию committed WAL; это не заменяет организацию cutover и не
делает backup моментом, совпадающим с более поздним schema commit.

Команда запускается из установленного пакета локальным Windows пользователем,
чей process SID имеет `project:read` и `project:admin` в выбранном проекте:

```powershell
rentgen state-migrate --registry C:\Rentgen\registry.sqlite3 --project PROJECT_UUID --backup-directory C:\Rentgen\backups
```

Замените `PROJECT_UUID` зарегистрированным идентификатором. Родитель каталога
backup должен существовать на локальном fixed volume Windows. Сам каталог может
быть новым; path через junction/reparse не принимается. Снимки/исходники проекта
для этой команды не открываются. Получение identity и проверка membership
предшествуют созданию и чтению backup artifacts.

Первой строкой stderr команда выдаёт `migration_recovery` с project ID,
operation ID и каталогом backup. Stdout содержит один JSON result/error. Для
повтора той же попытки сохраните operation ID:

```powershell
rentgen state-migrate --registry C:\Rentgen\registry.sqlite3 --project PROJECT_UUID --backup-directory C:\Rentgen\backups --operation-id OPERATION_UUID
```

Raw source SQLite paths и actor/owner claims не принимаются из аргументов
миграции: state берётся из registry, identity — из токена процесса. Server/HTTP
adapter не должен использовать SID своего процесса как identity удалённого
пользователя.

## Что сохраняется и проверяется

Runner создаёт новый каталог `backups/<operation UUID>/` эксклюзивно. Готовый
набор состоит ровно из двух файлов:

- `state-v1.sqlite3` — копия через SQLite backup API, включая committed WAL.
- `backup-receipt.json` — canonical JSON с project/operation ID, исходным
  locator, locator копии, schema version, SHA-256, размером, временем создания и
  identity администратора.

Copy выполняется на уже открытом и авторизованном source connection внутри
ограниченной **read** transaction. Это узкое исключение из обычных коротких read
UOW: соединение и read snapshot удерживаются до конца backup; source connection
наружу не передаётся. В write UOW backup запрещён. WAL writers могут продолжать
работать; rollback-journal writers могут ждать завершения read transaction.

До копирования проверяется page count × page size. По умолчанию максимум копии
256 MiB, по 64 страницы на SQLite backup step, deadline 30 секунд. API допускает
явные меньшие/большие лимиты до 1 GiB и 300 секунд. Deadline проверяется между
ограниченными SQLite steps; integrity checks также используют progress handler.
Это cooperative deadline, не обещание жёсткого timeout для любого вызова ОС или
чтения файла. Существующие state transactions отдельно имеют SQLite busy timeout
5 секунд. Настройки CLI сейчас используют значения по умолчанию.

Destination закрывается с `journal_mode=DELETE`; sidecars не допускаются.
Runner вызывает FlushFileBuffers через существующий no-follow helper,
проверяет SHA-256/размер, SQLite integrity/FK, schema 1 и project identity.
Файл и предки удерживаются no-follow handles при чтении и immutable SQLite
проверке. Receipt записывается эксклюзивно и flush-ится только после проверки
копии; затем весь набор проверяется повторно. Неожиданные файлы/sidecars,
неполный JSON или повреждённые bytes не дают действительный backup receipt.

С последней полной проверки backup и JSON receipt удерживаются отдельными
no-follow leaf handles без разрешения записи/удаления через вызов миграции и
финальную сверку версии. Общий владелец ресурсов хранит handles/stamps, не полный
backup-буфер. Перед schema call и перед выдачей результата проверяются точный
состав каталога и сохранённые идентичности. Не заявляется обнаружение временного
постороннего файла, появившегося и исчезнувшего между этими наблюдениями.

Готовый backup последующие вызовы только читают; они не заменяют и не обновляют
его. Хэш обнаруживает изменение backup относительно receipt. Это локальная
запись целостности, не криптографическая аттестация против пользователя того же
OS account, способного переписать и копию, и receipt. OS read-only attribute/ACL
runner не устанавливает. Храните набор как recovery evidence и не используйте
его как рабочую SQLite-базу.

После полного backup существующий `ProjectState.migrate_v1_to_v2` повторно
проверяет admin в своей write transaction. Schema и существующий migration SQL
не менялись. Membership, permissions и прочие данные SQLite сохраняются.

## Значение результата

`migration_attribution` всегда равно **`not_proven`**. Operation ID относится к
backup/runner receipt. Он не является атомарным receipt schema commit:
существующая миграция не записывает operation ID, а другой процесс мог первым
обновить state. Ни normal return, ни обнаруженная schema 2 не доказывают, какой
именно operation произвёл изменение.

| Outcome | Значение |
|---|---|
| `version_confirmed` | Backup проверен; после вызова миграции авторизованно подтверждена schema 2 |
| `reconciled` | Проверен прежний backup и подтверждена schema 2 при повторе либо восстановлении после ошибки ответа |
| `already_current` | Обнаружена schema 2 без прежнего backup этой операции; новый backup не создавался, migration completion не заявляется |

`state_version_confirmed=2` описывает наблюдённую версию. Это не утверждение,
что backup соответствует состоянию в ту же наносекунду, что и миграция, или что
именно этот runner выполнил upgrade. Для точной schema-operation attribution
понадобится отдельно спроектированный receipt внутри schema transaction.

## Ошибка, остановка процесса и повтор

- До готового receipt может остаться незавершённый owned каталог. Повтор того же
  operation возвращает `MIGRATION_BACKUP_INCOMPLETE`; старые файлы не заменяются.
  Для новой попытки используйте новый operation ID, сохранив старую для разбора.
- После готового receipt повтор использует ту же проверенную копию. При
  `STATE_BUSY` снимите блокировку writer и повторите тот же operation ID.
- Admin revoked до изменения schema → `PROJECT_FORBIDDEN`; готовый backup может
  сохраниться, но не становится разрешением на дальнейшую миграцию.
- Ошибка/прерывание после schema call требует повторного авторизованного чтения
  версии. Если schema 2 и полный backup подтверждаются, а все закрытия завершены,
  возвращается `reconciled`. Если версию
  нельзя прочесть, ответ `MIGRATION_OUTCOME_UNKNOWN`; это не rollback receipt.
- Повреждение копии/receipt или лишние файлы не допускают reconciliation как
  действительного backup. Текущая state DB при этом не откатывается.
- Неподтверждённое закрытие выдаёт `MIGRATION_BACKUP_CLEANUP_FAILED` вместо
  успешной reconciliation. Если после schema call версия 2 подтверждена, ошибка
  содержит `state_version_confirmed=2` и `migration_attribution=not_proven`;
  она не превращается в точную квитанцию commit или rollback этой операции.

Успешный flush не является гарантией directory durability при потере питания.
При обычном process kill проверяется повторное открытие SQLite и artifacts;
не заявляется защита от всех storage/power-loss failures. Автоматического GC,
удаления incomplete attempts, downgrade или включения старых writers нет.

## Ручное восстановление

Остановите все writers и transport jobs для проекта, закройте SQLite handles.
Сохраните текущую state DB отдельной согласованной SQLite-копией вместе с её
состоянием и журналом восстановления; не заменяйте её, пока набор не проверен.
Проверьте hash/identity/schema исходного backup и сохраните его неизменным.
Восстанавливайте рабочую копию в рамках отдельно согласованного recovery
процесса, с учётом WAL/SHM и registry identity. Этот runner не выполняет эти
действия и не предоставляет команду downgrade. Не запускайте старые и новые
writers одновременно.

## Проверки

`tests/integration/test_project_core_state_migration.py` проверяет реальные
committed WAL bytes, admin/identity-before-IO, size/deadline, read-UOW seam,
busy writer, no-overwrite/incomplete receipt, junction refusal, corruption и
sidecars, пять actual process-kill boundaries, same-operation recovery,
lost acknowledgment, KeyboardInterrupt, retained-handle close failure,
revocation и реальный CLI с process SID. Existing state/migration/CLI tests
сохраняют прежний контракт перехода 1→2. Новые проекты совместимого ядра
создаются со schema 3; этот runner отвергает schema 3 до backup IO. Для
отдельного перехода 2→3 используйте `state-upgrade-access`, описанный в
[PROJECT-ACCESS.md](PROJECT-ACCESS.md). Его атомарная action receipt не меняет
историческое `migration_attribution=not_proven` у M1.

Windows backup path confinement использует существующие Windows helpers.
Наличие SQLite на другой ОС само по себе не означает поддержку этого runner.
Legacy graph/JSON migration, полный E1–E4 cutover и остальные требования
продуктовой готовности этим документом не объявляются выполненными.
