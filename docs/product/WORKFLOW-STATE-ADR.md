# ADR: проектное хранение проверок и применения

Статус: частично реализовано, 2026-09-09. Текущий development checkout создаёт
schema4 и содержит хранение черновиков, историю и CLI; это ещё не новая сборка
дистрибутива. Profiles/runs/approvals/effects ниже остаются целевым решением.
Это решение продолжает
W2/W3 ежедневного сценария и не меняет критерии готовности продукта.

Уточнение последовательности: [сохранение черновиков и история](DRAFT-HISTORY-DESIGN.md)
поставляются первым полным контрактом schema4. Таблицы profiles/runs/approvals/effects
ниже описывают целевую архитектуру последующих явных обновлений схемы; они не будут
созданы с заглушками до реализации их проверяемых контрактов. Требования W2/W3
остаются обязательными. Переход3→4 и семейство workflow receipts сохраняются.

## Зачем нужна отдельная версия

Сейчас `ProjectState` проверяет версии1/2/3/4. Таблица `project_action_receipts`
допускает только membership.set, membership.revoke и state.upgraded. Её decoder
в `access.py` проверяет точный формат существующей миграции2→3. Использование
этой таблицы для тестов или apply сломало бы уже доставленные контракты.

Решение: явная verified-backup миграция3→4 и отдельные проектные workflow tables
в том же SQLite-файле и `StateTransaction`. Существующие membership/publication
receipts и их декодеры сохраняют семантику. Для новых действий используется
`workflow_receipts`; семейство явно выбирается API, поиск UUID не смешивает
membership/publication/workflow. Новые таблицы не появляются при чтении или
вызове функции в schema3. До завершения миграции workflow API отвечает
`WORKFLOW_STATE_UPGRADE_REQUIRED`.

## Состояние и инварианты

Все записи включают project_id и составные внешние ключи в пределах проекта.
Канонический JSON проходит типизированную проверку до транзакции; в SQL хранятся
также ключевые идентификаторы и хэши, необходимые для FK/CAS. Публичного универсального
`save_record` или записи результата произвольным JSON нет.

| Таблица | Ключ/назначение | Основной инвариант |
|---|---|---|
| workflow_receipts | project_id + operation_id; action, actor, request/result | Immutable; повтор идентичного действия возвращает прежний ответ, другое содержимое с тем же ID даёт конфликт |
| test_profile_versions | project_id + profile_id + revision; canonical definition/hash | Immutable: runtime identity, test-copy identity, corpus manifest и adapter version связаны одной ревизией |
| test_profile_heads | project_id + profile_id; revision, active | CAS; смена/деактивация создаёт новую монотонную revision, без ABA |
| workflow_proposals | project_id + proposal_content_id | Канонические bytes подтверждены ядром по полному SourceRef; FK на сохранённый snapshot |
| workflow_runs | project_id + run_id; kind, proposal, profile revision, input bindings, state | Запуск начинается записанным intent; terminal outcome однократен и не меняет исходную привязку |
| workflow_approvals | project_id + approval_id; exact proposal/runs/head/policy | Одноразовое потребление с CAS; новая выдача имеет новый ID, отсутствующее доказательство не становится true |
| workflow_effects | project_id + operation_id; approval, before/after identity/hash, phase | Intent до внешней записи; terminal outcome после re-read; неизвестный исход требует reconciliation |

Точная SQL-схема, CHECK, индексы и поля JSON входят в реализацию с проверками,
а не генерируются из этой таблицы во время работы. Ограничения объёма:
proposal до1.5 MiB канонического JSON, profile definition до64 KiB и10000 записей
в manifest, normalized run result до2 MiB. Значения вводятся как явные константы
контракта; превышение даёт отказ, а не урезанную успешную запись.

`workflow_runs.kind` разделяет диагностику и тесты. Clean от BSL-LS не означает
passed тестов 1С. Для тестового passed необходимы завершённый trusted worker,
точный профиль/corpus/input, полный корректный report и executed_count>0;
failed/error>0, skip-only, missing, stale, unsupported и unknown не проходят.
Переданный клиентом отчёт хранится только как manual_import и никогда не
переходит в trusted execution посредством переименования поля статуса.

Источник доказательства — контролируемый локальный запуск и проверенные артефакты.
Это не криптографическое доказательство против администратора машины или самого
кода, исполняемого в том же доверенном контексте. Отдельная тестовая ИБ сама по себе
не является запретом записи в остальные файлы ОС или доступа к сети.

## Регистрация и исполнение

1. Доверенный локальный администратор регистрирует immutable profile через CLI.
   Runtime/test-copy пути принадлежат этой операции; HTTP/MCP выполнения принимает
   только profile_id + expected revision + proposal ID + operation ID.
2. Наличие каталога версии не доказывает доступный runtime. Проверяются настоящий
   executable/version/identity, файл расширения и manifest corpus; успешная загрузка
   и тест в отдельной ИБ подтверждаются отдельно. Entitlement не выводится из версии.
3. `project:read`, `source:edit`, `operations:execute` проверяются до копирования/
   запуска, после внешних этапов и при записи результата. Профиль не даёт полномочий
   сам по себе; отозванный/сменённый профиль не используется по прежней revision.
4. В короткой UOW сохраняется run intent с exact bindings. Долгие копирование,
   загрузка в 1С и исполнение проходят вне SQL write transaction. Попытка имеет
   отдельный каталог и сохраняет владение процессами/артефактами до завершения.
5. Candidate применяется к собственной одноразовой тестовой копии; загрузка и
   тестовый input проверяются по байтам, а не по имени файла. Старый report из
   соседней попытки или с другим test selection не принимается.
6. Завершение проверяет права и все связи в той же UOW, что outcome/receipt.
   Отзыв прав не превращает исполнившийся процесс в not_run: очистка и внутренний
   исход фиксируются доверенным worker, пользователь получает отказ в доступе.

Точные полномочия технического worker при фиксации результата после отзыва
пользовательских прав должны быть отдельным закрытым внутренним интерфейсом.
Нельзя подставить actor из JSON или отключить authorization целого StateTransaction.
Это обязательная часть реализации, не разрешение на скрытый обход.

## Миграция3→4

- Явная административная команда с operation_id и новым backup directory.
- Повторно проверить project:admin, построить SQLite backup версии3, проверить
  его identity/integrity/размер/SHA, flush и удерживать проверенный leaf/parents
  через commit и финальное подтверждение. Переиспользовать существующие
  `_backup_schema`, `_new_backup`, `_hold_verified_backup`; не копировать live DB
  обычным copyfile и не писать второй конкурентной connection внутри UOW.
- В одной write UOW подтвердить исходную версию3, добавить workflow tables,
  записать `workflow.state_upgraded` receipt и PRAGMA user_version=4.
- При lost acknowledgement искать точный workflow receipt; отсутствие такого
  receipt при уже schema4 означает изменение другой операцией, не наш успех.
- Чтения snapshots и memberships явно принимают2/3/4;1→2 и2→3 остаются отдельными
  миграциями с прежними результатами. Никаких изменений hash сохранённых снимков.
- Новые проекты переключаются на4 только вместе с поставкой проверенного
  bootstrap/reader/CLI контракта; обновление уже существующих БД не автоматическое.

## Последующее применение и восстановление

Apply не принимает эфемерный результат W1 как approval. Нужны exact durable runs,
proposal, полный исходный head/revision/source configuration, свежая identity/hash
живого файла и одноразовое approval. В одной UOW потребляются approval и intent;
внешняя запись выполняется затем; после фактического re-read записывается outcome.
Не заявляется атомарная замена Windows-файла поверх сильных parent pins.
Writer и crash protocol требуют отдельного испытания до включения apply.
Undo — новая операция с expected applied bytes; стороннее изменение не затирается.

## Обязательная приёмка

- Миграция настоящей schema3 с данными: snapshot/ref/hash, membership history,
  публикационные receipts и старые команды сохранились; backup реально открывается.
- Wrong version/identity, revoke, concurrent migration, corrupt/swap backup,
  сбой до/после DDL/receipt/commit дают rollback или доказанный точный outcome.
- CAS profile revisions, cross-project refs, reused operation ID с другим запросом,
  старые corpus/runtime/report и manual passed не проходят.
- В отдельной реальной 1С ИБ: ошибочная функция → executed failed test;
  исправленная → executed passed с новым candidate/report hash. Без 1С gate
  остаётся невыполненным; OneScript и BSL-LS его не заменяют.
- Apply/undo/crash/transport проверки сохраняются обязательными после W2.

Входы YAxUnit закреплены в
[inputs.json](../../packaging/test-profiles/yaxunit-25.12/inputs.json).
Ни этот ADR, ни скачивание CFE не являются регистрацией или выполнением профиля.
