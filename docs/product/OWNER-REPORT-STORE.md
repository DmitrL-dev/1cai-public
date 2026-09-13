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
даёт `OWNER_REPORT_STORE_CONFLICT`. Запись удерживает блокировку и проверенный
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

## Локальный CLI

После аутентификации проекта те же операции доступны из Windows CLI. CLI
использует только выделенный каталог `<state-root>\owner-reports`; перед чтением
или записью он подтверждает, что snapshot опубликован в выбранном проекте,
сверяет project/snapshot в отчёте и повторно проверяет права:

```powershell
rentgen owner-report-save --registry .\registry.sqlite3 --project <project-id> `
  --store .\state\owner-reports --snapshot <64-hex-snapshot> --report-json .\report.json
rentgen owner-report-get --registry .\registry.sqlite3 --project <project-id> `
  --store .\state\owner-reports --snapshot <64-hex-snapshot> --report-id <uuid>
rentgen owner-report-list --registry .\registry.sqlite3 --project <project-id> `
  --store .\state\owner-reports --snapshot <64-hex-snapshot> --limit 20
```

`owner-report-save` сначала проверяет JSON и точное соответствие project/snapshot,
затем создаёт store при необходимости. Полученный результат — обычная receipt;
`owner-report-list` возвращает bounded summary без поля `report`; полную запись
можно получить отдельной командой по `report-id`. Порядок списка — от новых к
старым. CLI не запускает анализатор и не отправляет отчёты во внешний канал.
