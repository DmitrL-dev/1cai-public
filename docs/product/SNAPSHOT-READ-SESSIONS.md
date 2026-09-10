# Сессия чтения опубликованного снимка

`SnapshotSources.read_session(limits=SnapshotReadLimits())` создаёт синхронную
сессию одной операции. Capability уже привязана к явным project/snapshot;
конструктор сессии не принимает actor, source root, текущий head или transport JSON.
Модуль `rentgen_core.sources` использует stdlib и core. Поддерживаются локальные
Windows volumes с проверяемыми no-follow handles.

```python
from rentgen_core.sources import SnapshotReadLimits

with ctx.sources.read_session(limits=SnapshotReadLimits()) as reader:
    entries = reader.entries()
    raw = reader.read_source(entries[0].ref)
    reader.checkpoint()
# Публичный результат возвращают только после успешного выхода из with.
validation = reader.validation_summary
```

## Что проверено за одну операцию

При входе повторяется актуальная `project:read` авторизация и проверяется catalog
выбранного снимка. Manifest читается и разбирается один раз. Удерживаются handles
всех его ожидаемых source/derived/graph файлов, manifest и ancestor/generation
директорий. Каждый файл читается с проверкой точного raw SHA256 и размера.
Граф дополнительно проходит существующие integrity, foreign key, schema, coverage
и provenance проверки через одну SQLite connection `mode=ro&immutable=1`.

Перед каждым raw read и на выходе проверяется актуальный доступ. `entries()`
возвращает полный bounded tuple в порядке manifest; `read_source()` принимает
точный SourceRef того же снимка, слоя, пути и хеша. Повторное чтение проверяет
hash/size и не запускает новый inventory или разбор manifest. Живые roots и
сменившийся head не участвуют. Внутренние долгие операции вызывают `checkpoint()`
до и после parsing/materialization.

Состав файлов проверяется полным inventory на входе и на выходе. Постоянно
присутствующий лишний файл отклоняется до возврата результата; его содержимое
не читается. Обычная Windows запись, удаление или подмена ожидаемых файлов
запрещена удерживаемыми handles без write/delete sharing.

Это наблюдения на границах операции, а не доказательство неизменности всего
namespace во времени. Временный неиспользованный файл, созданный и удалённый
между проверками, может остаться незамеченным. Directory handles сами по себе
не запрещают создание новых дочерних файлов. Привилегированные обходы файловой
системы и ранее созданные writable mappings не входят в обещание защиты
обычных файловых операций. Несогласованные наблюдаемые identities отклоняются.

`validation_summary` доступен только после успешной финальной проверки и cleanup.
Это описание завершённой проверки, а не credential или новая долговечная receipt.
В нём есть exact snapshot/catalog bindings, количество проверенных файлов/байтов,
`all_expected_files_verified=true`, `inventory_checks=entry_exit`,
`expected_bytes_protected=retained_handles` и
`temporal_namespace_atomicity=not_proven`.

## Ресурсы и завершение

| Предел | Максимум; можно только уменьшать |
| --- | --- |
| Source entries | 20 000 |
| Owned Win32 handles | 65 536, включая весь временный ancestor chain каждого reread |
| SQLite connections | Одна; внутренние native handles SQLite не выдаются за измеренный Win32 count |
| Inventory items за проход | 200 000 |
| Manifest | 64 MiB |
| Все raw bytes полной проверки | 2 560 MiB |
| Сессия | 30 секунд cooperative deadline |

Дополнительно действуют per-source 64 MiB и aggregate source 1 GiB,
per-derived 128 MiB и graph 1 GiB. Хеширование работает порциями без удержания
byte buffers всего поколения. Предел owned handles учитывает реальные
ancestor+leaf opens до временного reread. Сложное глубокое дерево может
достигнуть этого предела раньше лимита source entries.

Deadline проверяется между IO/parse/materialization этапами, по chunks и через
SQLite progress callback. Это не hard interrupt зависшего Win32 вызова.
Cleanup пытается закрыть все handles независимо от deadline. При первичной
ошибке, включая BaseException, ошибка закрытия не заменяет её. Если cleanup
не подтверждён после иначе успешной операции, результат не возвращается.
Отмена ожидания worker thread транспортом не доказывает завершённый cleanup.

Сессия одноразовая, не допускает reentry, вызовов с другого потока и обращения
к read methods после выхода. Нельзя выдавать её как lazy iterator или использовать
для streaming частичного результата до финальной проверки доступа.

Коды: `SNAPSHOT_READ_LIMIT_EXCEEDED`, `SNAPSHOT_READ_DEADLINE_EXCEEDED`,
`SNAPSHOT_READ_SESSION_INVALID`. Неверные typed options дают
`INVALID_QUERY_OPTIONS`; повреждённые artifacts и cleanup-only failures —
`SNAPSHOT_CORRUPT`. Ошибки авторизации сохраняются без добавления source paths.
Transport mapping принадлежит адаптеру.

Resolver по-прежнему полностью проверяет generation перед выдачей capability
и закрывает свои handles. Сессия повторяет полную проверку один раз, поскольку
её handles не были переданы из resolver. Удаление этой дополнительной линейной
работы требует отдельного согласования жизненного цикла; cache по пути/mtime
здесь отсутствует.

## Проверка

`tests/integration/test_project_core_read_session.py` собирает реальный Go scanner,
публикует публичный fixture и проверяет реальные Windows sharing/cleanup эффекты,
отзыв доступа, extra files, повреждённый unselected source/derived input,
SQLite authorizer failure и повторный вход после ошибок. Unit-тесты проверяют
строгие числовые пределы. Эти проверки не являются измерением производительности
большой конфигурации или подтверждением runtime-семантики 1С.
