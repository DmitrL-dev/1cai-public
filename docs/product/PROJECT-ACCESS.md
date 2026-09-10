# Доступ к проекту: локальное администрирование

Runbook ядра schema v3 и локального CLI из пакета 0.1.0.dev1. Pre-v3 пакет 0.1.0.dev0 не поддерживает команды membership-* и state-upgrade-access. Установка совместимой сборки описана в [CORE-INSTALLATION.md](CORE-INSTALLATION.md).

Локальный CLI определяет действующего администратора по SID токена процесса Windows. Аргументов для выбора actor нет. Получатель прав — точная пара principal.id и principal.authority. HTTP roles не назначают членство в проекте, а SID HTTP-службы не является пользователем запроса.

## Версия состояния и обновление

Пакеты dev1/dev2 создают schema3. Текущий development checkout создаёт schema4
с [историей черновиков](DRAFT-HISTORY.md); новый дистрибутив ещё не собран.
Совместимая версия ядра продолжает читать снимки и публиковать новые снимки в
существующих schema2 проектах. Изменения членства поддерживаются в schema3/4:
права и квитанция с аудитом записываются в одной SQLite-транзакции.

Перед явным обновлением установите совместимую версию всех CLI/MCP/HTTP процессов, использующих проект, и перезапустите старые процессы. Pre-v3 пакет отвергает schema3; откат исполняемого кода не понижает версию состояния.

```powershell
$upgradeOperation = [guid]::NewGuid().ToString()
rentgen state-upgrade-access --registry C:\Rentgen\registry.sqlite3 --project PROJECT_UUID --backup-directory C:\Rentgen\backups --operation-id $upgradeOperation
```

Эта операция выполняет только 2→3. Она сначала создаёт и проверяет согласованную SQLite backup-копию с учётом committed WAL, затем повторно проверяет администратора и атомарно записывает schema3 и квитанцию обновления. Backup содержит состояние, но не заменяет архив сохранённых исходников и графов. Существующие snapshot/catalog/head/publication receipts сохраняются.

Резервируется эксклюзивный каталог `backups/OPERATION_UUID` с `state-v2.sqlite3` и `backup-receipt.json`. При повторе завершённая копия сверяется по hash, размеру, версии, проекту и сохранённой квитанции; незавершённая копия отвергается. По умолчанию backup ограничен 256 MiB и 30 секундами кооперативного deadline между SQLite steps; обычный write-lock ждёт не более 5 секунд. После `STATE_BUSY` допустим только явный повтор с прежним operation ID. CLI использует эти ограничения ядра и не подменяет исходный ID.

После последней проверки оба файла удерживаются no-follow дескрипторами без разрешения записи/удаления через commit и итоговую сверку состояния. В памяти между этими этапами остаются дескрипторы и stamps, не полный backup-буфер. Состав каталога и идентичность файлов проверяются перед commit и перед успешным завершением. Все закрытия предпринимаются даже при исходной ошибке; неподтверждённое закрытие не превращается в успешную reconciliation. Временный посторонний файл, созданный и удалённый между проверками каталога, не объявляется обнаруживаемым.

`committed` означает подтверждённую квитанцию именно этой операции; `reconciled` — её повторное подтверждение. `already_current` с `receipt=null` не приписывает чужое обновление вызывающему и не создаёт новую копию. Повреждение backup после commit возвращает `MIGRATION_COMMITTED_BACKUP_INVALID` с `migration_committed=true`; ошибка последующей сверки state возвращает `MIGRATION_OUTCOME_UNKNOWN`. Уже наблюдавшийся commit при этом не объявляется отменённым.

Для schema1 сохраняется отдельный `state-migrate --backup-directory PATH`: сначала явный проверенный 1→2, затем отдельный 2→3. Результат M1 остаётся `migration_attribution=not_proven`; ему не приписывается новый контракт точной квитанции v3. Подробнее: [STATE-MIGRATION.md](STATE-MIGRATION.md).

Незавершённые backup attempts не перезаписываются и автоматически не удаляются. Версия3 сама по себе не доказывает, какая операция выполнила обновление; это устанавливает соответствующая квитанция. Неизвестный результат не превращается в «откат выполнен». Рабочие записи между backup и миграцией допустимы, поэтому backup не обещает тот же момент времени, что schema commit. Гарантия восстановления после потери питания или автоматический restore в этот срез не входят.

## Получатель HTTP-доступа

Авторизованный HTTP пользователь получает свой principal из identity endpoint. Используйте возвращённый объект `principal` без изменения ID или authority. `auth_realm` — стабильный UUID настроенного сервера; его смена меняет пространство идентичностей и требует отдельного назначения прав.

Сохраните только объект principal в bounded UTF-8 JSON без повторяющихся ключей:

```json
{"id":"http-user:EXACT_VALUE_FROM_IDENTITY_ENDPOINT","authority":"verified_token"}
```

Этот файл задаёт получателя. Он не меняет локального администратора и не является доказательством владения HTTP identity. Не используйте имя пользователя, token roles или весь HTTP envelope вместо principal.

## Список и назначение прав

```powershell
rentgen membership-list --registry C:\Rentgen\registry.sqlite3 --project PROJECT_UUID --limit 100
```

Ответ содержит project_id, state_schema_version, текущую revision, memberships и next_after. Каждый элемент содержит principal и отсортированный набор permissions. Корни исходников/состояния не выдаются. Для следующей страницы сохраните объект next_after и передайте `--after-principal-json FILE`; каждая страница заново авторизуется и отражает свою текущую revision. Это не исторически зафиксированная многостраничная выборка.

Список разрешений в permissions.json задаёт полный новый набор. Для чтения источников, метаданных и графа достаточно:

```json
["project:read"]
```

Поддерживаются project:read, project:admin, analysis:run, source:edit, artifacts:export, approvals:decide, operations:execute и policies:decide. Неизвестные, повторяющиеся или нестроковые значения отвергаются. Наличие разрешения не означает, что соответствующая продуктовая возможность уже реализована. Набор для set должен содержать project:read; для удаления доступа используется revoke.

```powershell
$operation = [guid]::NewGuid().ToString()
rentgen membership-set --registry C:\Rentgen\registry.sqlite3 --project PROJECT_UUID --principal-json .\principal.json --permissions-json .\permissions.json --operation-id $operation --expected-revision REVISION_FROM_LIST
```

CLI проверяет project:read и project:admin до чтения JSON файлов, затем повторяет проверку в write UOW. Если после получения revision произошла другая административная операция, изменение отклоняется с MEMBERSHIP_CONFLICT. CLI не получает новую revision и не повторяет grant автоматически. Сохраните operation ID и исходные аргументы до запуска.

## Отзыв и защита администратора

```powershell
$operation = [guid]::NewGuid().ToString()
rentgen membership-revoke --registry C:\Rentgen\registry.sqlite3 --project PROJECT_UUID --principal-json .\principal.json --operation-id $operation --expected-revision REVISION_FROM_LIST
```

Удаляется точная пара ID+authority и её permissions. Отсутствующий получатель даёт аудируемый результат changed=false при совпадении revision.

CLI не разрешает администратору удалить собственное членство или собственные project:read/project:admin. Передача администрирования выполняется назначением другого администратора, после чего этот другой principal может удалить прежнего. Должен сохраняться хотя бы один доступный администратор с обоими разрешениями. Если до изменения был локальный администратор local_os, хотя бы один такой администратор должен остаться. Исторический неизменяемый owner не выдумывается для старых баз, где такого поля не было.

Отзыв влияет на следующие транзакции и проверки capabilities. Уже начатая read-транзакция может завершить чтение своей согласованной версии. Ни CLI, ни HTTP token role не возвращают удалённые права автоматически.

## Квитанция, повтор и потерянный ответ

Успешный mutation-result выдаётся только после commit. Он содержит project, operation, action, реального actor, target, before/after permissions, changed, revision и время записи. Запись служит одновременно аудитом и квитанцией; API не изменяет и не удаляет её. Это локальное транзакционное свидетельство, не защита от владельца ОС, напрямую переписывающего SQLite.

```powershell
rentgen membership-receipt --registry C:\Rentgen\registry.sqlite3 --project PROJECT_UUID --operation-id SAVED_OPERATION_UUID
```

Точное повторение operation ID с прежними actor, action, target, permissions и expected revision возвращает прежнюю квитанцию, даже если доступ затем изменился. Оно не применяет прежние permissions повторно. Повтор ID с другими аргументами даёт OPERATION_CONFLICT. Для чтения или повтора требуется актуальное право администратора; отозванный actor не получает доступ по известному ID операции.

Если процесс завершился или ответ потерялся, сначала сверяйте квитанцию. MEMBERSHIP_OUTCOME_UNKNOWN означает, что результат не удалось подтвердить. Отсутствие квитанции не является квитанцией успешного отката. При допустимом повторе используйте исходный ID и revision: новая конкурирующая операция приведёт к конфликту, а не к применению устаревших прав.

Нормальный stdout — один JSON envelope; диагностика идёт в stderr. Нет автоматического назначения всех token administrators, импорта legacy JSON, обхода project membership, удаления истории или изменения live source tree. HTTP onboarding и полный перевод всех E1–E4 consumers имеют отдельную приёмку.
