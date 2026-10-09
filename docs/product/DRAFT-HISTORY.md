# История черновиков: ядро и локальный CLI

Реализовано в development checkout, 2026-09-09. Это сохранение предложений
изменений в SQLite проекта. Исходные модули и опубликованные снимки не меняются.
[HTTP API](PROJECT-DRAFTS-HTTP.md) и [браузерный редактор](DRAFT-EDITOR.md) реализованы;
предыдущие wheel/sdist dev2 не содержат эту реализацию.

## Обновление состояния

Новые проекты создаются со schema4. Для существующей schema3 сначала обновите
все процессы, работающие с проектом, до совместимого кода. Затем выполните:

```powershell
$workflowOperation = [guid]::NewGuid().ToString()
python -m rentgen_core state-upgrade-workflows --registry C:\Rentgen\registry.sqlite3 --project PROJECT_UUID --backup-directory C:\Rentgen\backups --operation-id $workflowOperation
```

Команда проверяет администратора, создаёт согласованную резервную копию schema3
с учётом WAL, проверяет её и удерживает файлы открытыми до окончания миграции.
DDL, номер версии и отдельная квитанция `workflow.state_upgraded` фиксируются
одной транзакцией. Проверены откат до commit и восстановление ответа по точной
операции после commit. Существующие права, снимки и квитанции публикации
сохраняются. Копия SQLite не заменяет архив сохранённых исходников и графов.

Сохраните operation ID до запуска. Повтор той же команды с тем же ID возвращает
исходную квитанцию, если она подтверждена. Для уже существующей schema4 без этой
операции результат `already_current` не приписывает ей чужую миграцию.
Команды `state-migrate` и `state-upgrade-access` по-прежнему выполняют только
1→2 и 2→3 соответственно; они не пропускают этапы и не понижают schema4.

## Сохранение и повторное открытие

CLI устанавливает actor по SID текущего процесса Windows. Просмотр требует
`project:read`; сохранение, архивирование и возврат из архива дополнительно
требуют `source:edit`. Команды не принимают выбранного пользователем actor.

### Первый черновик без модели и BSL

Этот маршрут предназначен для Windows-комплекта Core dev17 после
[первого снимка и списка модулей](../../GETTING_STARTED.md#3-сохраните-первый-снимок).
Продолжите в той же PowerShell-консоли: `$rentgenCommand`, `$projectId` и
`$snapshotId` уже содержат путь установленного CLI и точные ID из его ответов.
Для создания черновика Java, BSL-LS, модель и запущенная 1С не нужны.

Выберите небольшой `.bsl`/`.os` модуль в строгом UTF-8, до 1 MiB. Скопируйте
`ref.layer_id` и `ref.relative_path` нужной строки `source-list`; путь относится
к снимку, а не к текущей рабочей папке. Подставьте эти значения ниже.
Используйте новый каталог: существующие файлы пример не перезаписывает.

```powershell
$ErrorActionPreference = 'Stop'
$registry = 'C:\RentgenState\registry.sqlite3'
$layerId = 'LAYER-ID-ИЗ-SOURCE-LIST'
$modulePath = 'ПУТЬ-МОДУЛЯ-ИЗ-SOURCE-LIST'
$utf8 = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = $utf8
$work = Join-Path $env:LOCALAPPDATA 'Rentgen\manual-first-draft'
if (Test-Path -LiteralPath $work) { throw 'Выберите новый каталог; для прерванного сохранения используйте recovery.json.' }
[IO.Directory]::CreateDirectory($work) | Out-Null
$candidateFile = Join-Path $work 'candidate.bsl'
$sourceRefFile = Join-Path $work 'source-ref.json'
$proposalFile = Join-Path $work 'proposal.json'
$recoveryFile = Join-Path $work 'recovery.json'

$raw = & $rentgenCommand source-read --registry $registry --project $projectId --snapshot $snapshotId --layer $layerId --path $modulePath --output $candidateFile
if ($LASTEXITCODE -ne 0) { throw 'source-read завершился ошибкой; не продолжайте сохранение.' }
$source = $raw | ConvertFrom-Json
if ($null -eq $source.result.ref) { throw 'В ответе нет SourceRef.' }
[IO.File]::WriteAllText($sourceRefFile, ($source.result.ref | ConvertTo-Json -Depth 12), $utf8)
```

`source-read --output` записывает точные байты исходника, включая BOM и переводы
строк. `candidate.bsl` пока совпадает с исходником. Можно оставить его как есть
для первой версии или перед следующим блоком отредактировать эту отдельную
копию, сохранив UTF-8, наличие BOM и тип переводов строк. Рабочую конфигурацию
это не меняет. Смешанные LF/CRLF не поддерживаются.

JSON-файлы пишутся в UTF-8 без BOM через .NET; `>` и `Out-File` в Windows
PowerShell 5.1 по умолчанию создают UTF-16LE. Если сохраняете команды с кириллицей
в отдельный `.ps1` для PowerShell 5.1, самому скрипту нужен UTF-8 с BOM.
[Правила кодировок PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1).

Создайте proposal из точного SourceRef и полной копии модуля. Сохраняется именно
`result.proposal`, а не весь ответ CLI. Самостоятельно заданный content ID
не заменяет проверку снимка.

```powershell
$candidateHash = (Get-FileHash -LiteralPath $candidateFile -Algorithm SHA256).Hash.ToLowerInvariant()
$raw = & $rentgenCommand proposal-create --registry $registry --project $projectId --snapshot $snapshotId --source-ref-json $sourceRefFile --replacement-file $candidateFile
if ($LASTEXITCODE -ne 0) { throw 'proposal-create завершился ошибкой; черновик ещё не сохранён.' }
$created = $raw | ConvertFrom-Json
if ($null -eq $created.result.proposal -or $created.result.proposal.replacement.raw_sha256 -ne $candidateHash) { throw 'Ответ не совпадает с выбранными байтами кандидата.' }
[IO.File]::WriteAllText($proposalFile, ($created.result.proposal | ConvertTo-Json -Depth 12), $utf8)
```

Создайте ID один раз и сохраните намерение до отправки `draft-save`.
После прерывания переходите к восстановлению ниже; повторный запуск блока
с новыми UUID создаст другое намерение.

```powershell
$draftId = [guid]::NewGuid().ToString()
$saveOperation = [guid]::NewGuid().ToString()
$title = 'Первый ручной черновик'
$intent = @{ registry = $registry; project_id = $projectId; snapshot_id = $snapshotId; draft_id = $draftId; operation_id = $saveOperation; title = $title; expected_revision = 0; proposal_json = $proposalFile; proposal_content_id = $created.result.proposal.content_id }
[IO.File]::WriteAllText($recoveryFile, ($intent | ConvertTo-Json -Depth 12), $utf8)

$raw = & $rentgenCommand draft-save --registry $registry --project $projectId --snapshot $snapshotId --proposal-json $proposalFile --draft-id $draftId --title $title --expected-revision 0 --operation-id $saveOperation
if ($LASTEXITCODE -ne 0) { throw 'Исход сохранения проверьте по operation_id из recovery.json; не создавайте новый ID.' }
$saved = $raw | ConvertFrom-Json
if ($saved.result.outcome -ne 'committed' -or $saved.result.revision -ne 1 -or $saved.result.draft_id -ne $draftId -or $saved.result.operation_id -ne $saveOperation) { throw 'Ожидаемая квитанция не подтверждена; используйте recovery.json.' }

$raw = & $rentgenCommand draft-get --registry $registry --project $projectId --draft-id $draftId --revision 1
if ($LASTEXITCODE -ne 0) { throw 'Не удалось повторно прочитать сохранённую версию; не повторяйте запись.' }
$loaded = $raw | ConvertFrom-Json
if ($loaded.result.receipt.proposal_content_id -ne $created.result.proposal.content_id -or $loaded.result.proposal.replacement.raw_sha256 -ne $candidateHash) { throw 'Прочитанная версия не совпадает с созданным proposal.' }
$loaded.result.receipt
```

Получена сохранённая ревизия 1 с проверенным content ID и хэшем кандидата.
Если копию не редактировали, пустой diff ожидаем: первая версия совпадает с
исходником. Её можно открыть и затем изменить через
[ручное редактирование в Companion](../../integrations/vscode-rentgen/README.md#ручное-исправление-черновика).
Квитанция сохранения не подтверждает диагностику, тесты или применение.

`draft-get` возвращает `result.receipt` и полный `result.proposal`. Параметр
`--revision N` выбирает конкретную старую версию. Извлечённый объект proposal
можно снова сохранить отдельным JSON-файлом для `proposal-diff`,
`proposal-check` или нового `draft-save`.

Для следующего сохранения передайте текущую `--expected-revision` и новый
operation ID. При `DRAFT_CONFLICT` изменения другого автора уже сохранены:
прочитайте текущую версию, согласуйте изменения и только затем создайте новое
намерение сохранения. Нельзя автоматически подменять ожидаемую ревизию.

### Если ответ потерян

В новой консоли снова укажите установленный `$rentgenCommand`. Прочитайте
намерение из выбранного ранее каталога и запросите его исходный operation ID:

```powershell
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$recoveryFile = Join-Path $env:LOCALAPPDATA 'Rentgen\manual-first-draft\recovery.json'
$intent = Get-Content -LiteralPath $recoveryFile -Raw -Encoding UTF8 | ConvertFrom-Json
$registry = $intent.registry
$projectId = $intent.project_id
$saveOperation = $intent.operation_id
$raw = & $rentgenCommand draft-receipt --registry $registry --project $projectId --operation-id $saveOperation
if ($LASTEXITCODE -ne 0) { throw 'Не удалось прочитать квитанцию; исход записи остаётся неизвестным.' }
($raw | ConvertFrom-Json).result
```

Квитанция описывает конкретную историческую операцию. `null` означает, что в
момент чтения её нет; это не доказывает остановку ещё работающего автора или
откат. Для сверки используйте `draft_id` и `operation_id` из `recovery.json`.
Повтор сохранения с тем же ID, actor и canonical содержимым возвращает исходную
квитанцию. Другой запрос с тем же ID получает `OPERATION_CONFLICT`; поэтому
сохраните исходный `proposal.json`, snapshot, title и expected revision.
Сохранение повторно проверяет retained source; чтение квитанции и сохранённого
черновика не открывает файловую систему снимка.

## Остальные команды

Все команды требуют `--registry` и `--project`.

| Команда | Аргументы | Результат |
|---|---|---|
| `draft-list` | `--limit`, `--after-draft-id`, `--status active\|archived` | Текущие версии, без исходных текстов |
| `draft-history` | `--draft-id`, `--limit`, `--before-revision` | Версии от новых к старым |
| `draft-archive` | `--draft-id`, `--expected-revision`, `--operation-id` | Новая версия со статусом archived |
| `draft-restore` | Те же | Новая версия, возвращающая черновик из архива |

Страница содержит до 25 записей, по умолчанию 20. Для продолжения используйте
`next_after` или `next_before` ответа. Архивирование не удаляет историю.
`draft-restore` возвращает черновик из архива; для возврата старого текста
прочитайте нужную версию и сохраните её proposal как новую текущую версию.
Обычное сохранение сохраняет полный SourceRef, включая исходный снимок.
Перенос изменений на новый снимок требует отдельного будущего механизма rebase.

## Контракты и проверка

Оригинал и кандидат ограничены 1 MiB каждый, canonical proposal — 1.5 MiB,
квитанция — 64 KiB. Заголовок: до 240 символов/960 UTF-8 байт, без управляющих
символов. Ответ CLI ограничен 2 MiB и проходит финальную проверку прав после
сериализации. JSON, хеши и ссылки сохранённых предложений проверяются при
открытии; списки читают только метаданные. Это не защита от администратора ОС,
который может согласованно переписать базу и код проверки.

Проверки используют реальную SQLite и опубликованные Go-анализатором снимки:
повторное открытие, история, конкурирующие авторы, откат, потеря ответа,
отзыв прав между проверкой исходника и commit, повреждение данных и CLI.
Отдельно проверяется сохранение старых снимков и квитанций при миграции3→4.
Чтение исходника завершается до открытия write-транзакции; Java и 1С при
сохранении не запускаются. Статическая проверка, тесты платформы, approval
и применение изменений — отдельные этапы, которые квитанция сохранения не
подтверждает. Реальные тесты 1С отложены до установки платформы пользователем.

Публичные SDK-функции находятся в `rentgen_core.drafts`: `save_draft`,
`get_draft`, `list_drafts`, `draft_history`, `get_draft_receipt`,
`archive_draft`, `restore_draft`. SDK возвращает canonical JSON как bytes;
CLI преобразует его в JSON-объект proposal. Полный продуктовый план остаётся
активным, в том числе HTTP/UI, защита несохранённых изменений и новый выпуск.
