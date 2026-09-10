# Предложенная правка и BSL-диагностика

В dev2 можно создать правку одного сохранённого модуля, посмотреть diff и проверить
полученные bytes настоящим BSL Language Server. Исходный файл берётся из явно
выбранного снимка: более новый capture или удаление живого файла не меняет основу
предложения. Создание и проверка не записывают изменения в конфигурацию.

## Установка runtime на Windows x64

Python-пакет включает адаптер и контрольные профили. Бинарные Java/JAR загружаются
отдельно из указанных выпусков, а затем устанавливаются локальным пользователем.
Автоматического скачивания, поиска Java в PATH и переключения на другую версию нет.

| Компонент | Зафиксированный выпуск | SHA-256 входного файла |
|---|---|---|
| BSL-LS JAR | [1.0.5](https://github.com/1c-syntax/bsl-language-server/releases/tag/v1.0.5) | `de97f571e6474c5c151cf859294f589ee01152de3b4826b43e1a80b69ee2602a` |
| Temurin JDK ZIP, Windows x64 HotSpot | [21.0.12.1+1](https://github.com/adoptium/temurin21-binaries/releases/tag/jdk-21.0.12.1%2B1) | `f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e` |

Сохраните файлы под именами из примера или измените только два входных пути.
Команды предназначены для новой установки; существующий runtime не заменяется.

```powershell
$ErrorActionPreference = 'Stop'
$javaArchive = 'C:\RentgenDownloads\temurin21-windows-x64.zip'
$bslJar = 'C:\RentgenDownloads\bsl-language-server-1.0.5.jar'
if ((Get-FileHash -LiteralPath $javaArchive -Algorithm SHA256).Hash -ne 'f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e') { throw 'JDK checksum mismatch' }
if ((Get-FileHash -LiteralPath $bslJar -Algorithm SHA256).Hash -ne 'de97f571e6474c5c151cf859294f589ee01152de3b4826b43e1a80b69ee2602a') { throw 'BSL checksum mismatch' }
$profileId = 'bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1'
$runtime = Join-Path $env:LOCALAPPDATA ('Rentgen\runtimes\' + $profileId)
if (Test-Path -LiteralPath $runtime) { throw 'Runtime directory already exists' }
Expand-Archive -LiteralPath $javaArchive -DestinationPath $runtime
Rename-Item -LiteralPath (Join-Path $runtime 'jdk-21.0.12.1+1') -NewName 'jdk'
Copy-Item -LiteralPath $bslJar -Destination (Join-Path $runtime 'bsl-language-server.jar')
```

Итоговый путь Java — `<runtime>\jdk\bin\java.exe`. Сохраняйте весь JDK, включая
legal/notices: перед каждым анализом проверяются все490 файла JDK и JAR, а не
только java.exe. Профили внутри wheel сверяются с закреплёнными хэшами ядра.
MIT относится к коду Рентгена; внешний BSL-LS помечен upstream как LGPL-3.0-or-later,
JDK сохраняет свои лицензии и уведомления. Эта поставка не распространяет эти
бинарные файлы и не является готовым общим offline bundle.

## CLI

Установите wheel по [CORE-INSTALLATION.md](CORE-INSTALLATION.md), зарегистрируйте
проект и выполните capture. Из его ответа возьмите конкретный snapshot_id.
Пример использует явный файл модуля; путь слоя/модуля берётся из `source-list`.

```powershell
$rentgenCommand = (Resolve-Path .\.venv-core\Scripts\rentgen.exe).Path
$registry = 'C:\RentgenState\registry.sqlite3'
$projectId = 'UUID-ИЗ-ОТВЕТА-РЕГИСТРАЦИИ'
$snapshotId = 'SHA256-ИЗ-ОТВЕТА-CAPTURE'
$source = (& $rentgenCommand source-read --registry $registry --project $projectId --snapshot $snapshotId --layer base --path CommonModules/Demo/Ext/Module.bsl --base64 | ConvertFrom-Json).result
[IO.File]::WriteAllText((Join-Path $PWD 'source-ref.json'), ($source.ref | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
# candidate.bsl содержит полную новую версию модуля в UTF-8.
$created = & $rentgenCommand proposal-create --registry $registry --project $projectId --snapshot $snapshotId --source-ref-json .\source-ref.json --replacement-file .\candidate.bsl | ConvertFrom-Json
[IO.File]::WriteAllText((Join-Path $PWD 'proposal.json'), ($created.result.proposal | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
& $rentgenCommand proposal-diff --registry $registry --project $projectId --snapshot $snapshotId --proposal-json .\proposal.json
& $rentgenCommand proposal-check --registry $registry --project $projectId --snapshot $snapshotId --proposal-json .\proposal.json --diagnostics-profile 'bsl-ls-1.0.5-temurin21.0.12.1-win64-bmp-default-v1'
```

Для создания/просмотра нужны `project:read` и `source:edit`, для проверки ещё
`analysis:run`. Actor берётся из SID процесса Windows. CLI не принимает полномочия
из proposal JSON. Отзыв доступа во время анализа приводит к отказу в выдаче результата.

## Что означает результат

`diagnostic.analysis.status=completed`, `runtime_verified=true` и `coverage=exact_one`
подтверждают завершённый запуск закреплённого анализатора ровно для переданных bytes.
`candidate_sha256`, `proposal_content_id`, полный `source_ref` и `report_sha256`
связывают ответ с правкой и исходным снимком. `diagnostics_status=clean` означает
отсутствие диагностик этого запуска; `diagnostics_present` сопровождается их списком.
Неуспешный, неполный или неподдерживаемый анализ не превращается в clean.

Ответ остаётся `evidence=ephemeral_unattested`, `tests.status=not_run` и
`apply.status=unavailable`. Проверка отдельного модуля не исполняет конфигурацию,
не проверяет бизнес-процессы и не разрешает применение. Постоянное хранение runs,
платформенные тесты и запись изменений относятся к следующим этапам.

## Поддерживаемый объём

- Один `.bsl` или `.os`, строго UTF-8. Кандидат сохраняет наличие BOM и тип
  перевода строк исходника (LF или CRLF); смешанные переводы строк не поддержаны.
  Нарушение возвращает `PROPOSAL_ENCODING_UNSUPPORTED`, без нормализации bytes.
- Диагностика пока ограничена BMP Unicode: для символов вне BMP upstream смешивает
  системы координат. Такие кандидаты возвращаются как unsupported, а не clean.
- CLI: оригинал и кандидат до1 MiB, JSON proposal до1.5 MiB, diff до256 KiB.
  У MCP кандидат до8 KiB; остальные ограничения — в [CORE-MCP.md](CORE-MCP.md).
- Анализатор запускается в отдельной папке с доступом текущего SID и SYSTEM,
  фиксированной конфигурацией и ограниченным Windows Job. Cooperative timeout60s;
  отдельно ограничено завершение/уборка. Это не жёсткий дедлайн ОС и не запрет сети.
- Незавершённая уборка удерживает владение процессами/файлами и блокирует новые
  попытки этим экземпляром адаптера. Ошибка не разрешает повтор с произвольным
  другим Java, отключённой проверкой хэшей или изменёнными опциями анализатора.
