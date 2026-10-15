# Durable owner-report store

`OwnerReportStore` хранит уже построенный результат
`build_owner_report()` в отдельном каталоге. Он не строит отчёт заново, не
подключается к 1С или SQL и не отправляет его во внешний канал.

```python
from rentgen_core.owner_report_store import OwnerReportStore

store = OwnerReportStore(r"C:\RentgenState\owner-reports")
store.initialize()
receipt = store.save(report, authorize=authorize_owner_report_write)
same = store.get(
    receipt["report_id"],
    expected_project_id=project_id,
    expected_snapshot_id=snapshot_id,
    authorize=authorize_owner_report_read,
)
latest = store.list(
    expected_project_id=project_id,
    expected_snapshot_id=snapshot_id,
    authorize=authorize_owner_report_read,
    limit=20,
)
```

Каждый файл содержит `status="stored"`, UUID `report_id`, точные
project/snapshot, исходный отчёт, время записи и hash `receipt_id`. Повторная
запись с тем же UUID и теми же байтами идемпотентна; другой отчёт с этим UUID
даёт `OWNER_REPORT_STORE_CONFLICT`. В Windows запись удерживает блокировку и проверенный
дескриптор каталога, создаёт финальный UUID-файл через `xb`, записывает байты и
делает `fsync`. Читатели сериализованы с публикацией; если процесс оборвётся
на записи, неполный финальный файл закрывает store с
`OWNER_REPORT_STORE_RECOVERY_REQUIRED` до ручного разбора.

Каталог ограничен 1000 квитанциями и 2 MiB на квитанцию. В каталоге разрешены
только канонические UUID-имена с расширением `.json`; ссылки, каталоги,
посторонние имена и повреждённые квитанции закрывают чтение fail-closed. Store
не удаляет старые отчёты и не считает их свежими: retention, расписание,
уведомления и подтверждённый runtime-источник остаются ответственностью
вызывающего host.

## POSIX library workflow в текущих исходниках

Следующий блок исходников добавляет POSIX backend для библиотечных
`load_onec_register_export()`, `load_runtime_report()` и `OwnerReportStore`.
Это ещё не новая опубликованная поставка и не перенос всего продукта.
Публичные owner-report CLI/MCP capabilities на Linux/macOS остаются закрыты.
Принимающий host по-прежнему задаёт доверенный абсолютный locator, ожидаемые
project/snapshot/commit/digest, источник и callback авторизации; файл экспорта
не выбирает эти ограничения и не подтверждает запрос к работающей 1С.

POSIX backend открывает каждый компонент пути через удерживаемые directory
descriptors и `dir_fd`/`O_NOFOLLOW`, проверяет тип, device/inode и namespace,
отклоняет ссылки и специальные файлы, ограничивает размер и сравнивает stamps
до/после чтения. Потребитель получает отдельные неизменяемые `bytes` и не должен
заново открывать проверенный pathname. Обычный POSIX descriptor не блокирует
чужую запись или rename как Windows deny-write/delete handle; `flock`
сериализует сотрудничающие операции store, а наблюдаемая подмена прекращает
операцию. Защита от враждебного процесса с тем же UID/root и одновременный
снимок всей файловой системы этим контрактом не заявляются.

Для store нужны существующий родитель и канонический абсолютный путь без
symlink-компонентов. В частности, системные macOS aliases `/var` и `/tmp`
не разворачиваются автоматически: host выбирает проверенный locator заранее.
Созданные root/reports принадлежат текущему UID с mode `0700`, файлы — `0600`
и с одним hardlink; расширенные ACL для этих private объектов отклоняются.
Небезопасный существующий каталог не исправляется через `chmod` и не становится
принадлежащим store автоматически. Проверки private ancestors сохраняются
и при работе через дочернюю directory capability.

POSIX публикация пишет private sibling temporary, выполняет `fsync`, затем
atomic no-overwrite rename и `fsync` каталога. Финальные identity и байты
перепроверяются. Конфликтующий UUID не перезаписывается. Незавершённый `.tmp`,
повреждённая запись или отказ durability требуют разбора; уже опубликованный
complete final при ошибке не удаляется. Повторное чтение не объявляет неизвестный
исход новой успешной записью, старые квитанции не становятся свежими runtime
измерениями. Автоматической очистки истории или неизвестных файлов нет.
Явный повтор `save` того же UUID с тем же отчётом заново выполняет directory
`fsync` перед успехом; повторный отказ durability остаётся отказом.

На настоящей macOS arm64 проверены положительный import/store/restart/read,
отказы на links/FIFO/ACL и подменах namespace, конкурентная запись отдельных
процессов, no-overwrite/durability failures и сохранение исходного отказа
авторизации при cleanup. Linux CI и Windows regression для этого нового блока
ещё требуются. SQLite graph consumers, capture, source sessions, native 1С/EDT,
Companion и GUI не входят в эту библиотечную проверку; capability admission
и установленный полный пользовательский маршрут принимаются отдельно.

## Локальный CLI

После аутентификации проекта те же операции доступны из Windows CLI. CLI
использует только выделенный каталог `<state-root>\owner-reports`; перед чтением
или записью он подтверждает, что snapshot опубликован в выбранном проекте,
сверяет project/snapshot в отчёте и повторно проверяет права:

```powershell
rentgen owner-report-save --registry .\registry.sqlite3 --project <project-id> `
  --store .\state\owner-reports --snapshot <64-hex-snapshot> --report-json .\report.json
rentgen owner-report-build --registry .\registry.sqlite3 --project <project-id> `
  --store .\state\owner-reports --snapshot <64-hex-snapshot> --profile C:\Rentgen\observer-profile
rentgen owner-report-get --registry .\registry.sqlite3 --project <project-id> `
  --store .\state\owner-reports --snapshot <64-hex-snapshot> --report-id <uuid>
rentgen owner-report-list --registry .\registry.sqlite3 --project <project-id> `
  --store .\state\owner-reports --snapshot <64-hex-snapshot> --limit 20
```

`owner-report-save` сначала проверяет JSON и точное соответствие project/snapshot,
затем создаёт store при необходимости. Полученный результат — обычная receipt;
`owner-report-list` возвращает bounded summary без поля `report`; полную запись
можно получить отдельной командой по `report-id`. Порядок списка — от новых к
старым. `owner-report-build` читает durable findings из указанного локального
observer profile, повторно проверяет права через `Observer.owner_report()` и
сохраняет новый immutable отчёт; модель, анализатор, 1С, SQL и сеть при этом не
запускаются. Профиль должен быть абсолютным локальным путём. CLI не отправляет
отчёты во внешний канал.
