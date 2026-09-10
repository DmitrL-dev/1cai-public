# Локальное ядро: сборка, установка и первый проект

Срез `rentgen-core 0.1.0.dev7`, Windows x64 / CPython 3.11. Это CLI снимков,
графа и предложенных правок с BSL-диагностикой и локальным stdio MCP. Полная
приёмка продукта ведётся в полном репозитории (`docs/product/READINESS.md`). Инструкции не
устанавливают платформу 1С, EDT или модели и не запускают HTTP-сервер или старый
MCP. Для текущего захвата нужен Windows.

## Сборка из открытых исходников

В корне checkout создайте отдельное окружение. Старый `setup.py` — генератор
окружения, его не запускают. `pyproject.toml` прямо выбирает Hatchling; построение
wheel и sdist не использует setuptools или этот скрипт.

Состав задаётся явными списками в pyproject. VCS ignore-правила не участвуют в
отборе; доставленный build hook `packaging/core/hatch_build.py` убирает также
автоматическое добавление `.gitignore`/`.hgignore` самим Hatchling 1.32.0.
Поэтому расположение сборки внутри другого checkout не добавляет его файлы
в sdist. Проверка поставки сравнивает полный состав архива и хэши с выбранными
входами плюс генерируемый `PKG-INFO`.

```powershell
py -3.11 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements/locks/product-build-py311-windows.txt
.\.venv-build\Scripts\python.exe -m pip check
.\.venv-build\Scripts\python.exe -m build --no-isolation
```

Для первой установки инструментов сборки нужен доступ к источнику пакетов или
заранее подготовленным проверенным wheels. `--no-isolation` здесь использует
именно отдельное окружение с зафиксированным профилем. Это не команда для общего
системного Python. Версии build tools обновляются вместе с lock и аудитом.

Wheel включает `rentgen_core`, `rentgen_graph`, `rentgen_diagnostics` и сведения о лицензии MIT.
Source distribution также содержит исходники Go scanner, профили сборки/runtime
и инструкции CORE-INSTALLATION, CORE-MCP, STATE-MIGRATION, PROJECT-ACCESS,
SNAPSHOT-METADATA, SNAPSHOT-READ-SESSIONS и SNAPSHOT-PUBLICATION-ADR.
Также доставляются инструкции истории черновиков, MCP больших модулей, поиска
исходников и проектных HTTP/редакторских интерфейсов. Описание этих интерфейсов
не устанавливает сам портал. Полный checkout нужен для разработки HTTP-приложения
и портала. JSON входов YAxUnit — справочный манифест, без runtime/CFE или запуска 1С.

## Установка готового wheel

Сам пакет ядра не требует сторонних runtime-зависимостей. Эти команды устанавливают
локальный wheel без обращения к индексу пакетов:

```powershell
py -3.11 -m venv .venv-core
.\.venv-core\Scripts\python.exe -m pip install --no-index --no-deps .\dist\rentgen_core-0.1.0.dev7-py3-none-any.whl
.\.venv-core\Scripts\python.exe -m pip check
.\.venv-core\Scripts\rentgen.exe --help
```

Альтернативная точка входа — `python -m rentgen_core`. Обычный успешный ответ —
один JSON с `result` и `request_id`; ошибки — JSON с `error`, код выхода 2.
`--help` выводит справку. Диагностика scanner/сборки и сведения для восстановления
захвата идут в stderr и не смешиваются с JSON результата.

Go scanner собирается отдельно установленным Go версии из `go/go.mod`:

```powershell
New-Item -ItemType Directory -Force .\output | Out-Null
go -C go build -buildvcs=false -trimpath -o ..\output\bsl-scan.exe ./cmd/bsl-scan
```

Путь к scanner передаётся явно доверенным локальным пользователем. Wheel сам по
себе не содержит исполняемый scanner и не заменяет будущий полный offline bundle.

## Локальный stdio MCP

Extra `mcp` добавляет официальный SDK `mcp==1.30.0`; обязательных зависимостей у
базового wheel по-прежнему нет. Для воспроизводимой установки SDK используйте
существующий проверенный Windows runtime profile, который входит в sdist:

```powershell
py -3.11 -m venv .venv-mcp
.\.venv-mcp\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements/locks/product-py311-windows.txt
.\.venv-mcp\Scripts\python.exe -m pip install --no-index --no-deps ".\dist\rentgen_core-0.1.0.dev7-py3-none-any.whl[mcp]"
.\.venv-mcp\Scripts\python.exe -m pip check
.\.venv-mcp\Scripts\rentgen-mcp.exe --registry C:\RentgenState\registry.sqlite3 --scanner C:\RentgenTools\bsl-scan.exe
```

Runtime profile также содержит зависимости других частей продукта; его установка
сама по себе их не запускает. Первая команда установки требует индекса или заранее
подготовленного wheelhouse. Для offline используйте `--no-index --find-links PATH`
с тем же hash lock. Версии транзитивных зависимостей берутся из этого профиля;
обычный незакреплённый resolver для extra не заменяет проверку поставки.

Альтернативная точка входа — `python -m rentgen_core.stdio_mcp`. MCP-клиент запускает
процесс и обменивается JSON-RPC по stdin/stdout; диагностика остаётся в stderr.
Registry и scanner — доверенные startup-параметры. Все source/graph tools требуют
явные project_id и snapshot_id; identity берётся из SID процесса Windows. Setup,
слои и административная миграция остаются в CLI. 21 tool, ограничения,
отмена и восстановление по receipt описаны в [CORE-MCP.md](CORE-MCP.md).

## Диагностика предложенной правки

Wheel включает `rentgen_diagnostics` и два закреплённых JSON-профиля.
Базовая CLI-диагностика не требует MCP SDK или HTTP-зависимостей. Java/JAR
устанавливаются отдельно в профиль текущего Windows-пользователя; команды,
контрольные суммы и ограничения описаны в [PROPOSAL-CHECK.md](PROPOSAL-CHECK.md).

## Первый проект

Выберите существующую папку выгрузки и новые пути registry/state. Родительские
каталоги должны существовать. Ни registry, ни state не перезаписываются.
Пример ниже показывает форму команд; пути заменяют своими.

```powershell
$rentgenCommand = (Resolve-Path .\.venv-core\Scripts\rentgen.exe).Path
& $rentgenCommand registry-init --registry C:\RentgenState\registry.sqlite3
& $rentgenCommand project-register --registry C:\RentgenState\registry.sqlite3 --source-root C:\Configs\Demo --state-root C:\RentgenState\Demo --name 'Демо'
& $rentgenCommand project-list --registry C:\RentgenState\registry.sqlite3
```

Из ответа регистрации возьмите `project_id`. Во всех дальнейших командах это
канонический UUID; имя проекта или путь не заменяют его. Пустое/неизвестное значение
не переключает команду на другой проект. Владельцем становится реальная учётная
запись Windows, определённая по SID токена процесса. Параметров `--owner`/`--actor`
и доверия к имени из переменной окружения нет.

```powershell
$projectId = 'UUID-ИЗ-ОТВЕТА-РЕГИСТРАЦИИ'
& $rentgenCommand layers-get --registry C:\RentgenState\registry.sqlite3 --project $projectId
& $rentgenCommand project-head --registry C:\RentgenState\registry.sqlite3 --project $projectId
& $rentgenCommand capture --registry C:\RentgenState\registry.sqlite3 --project $projectId --scanner .\output\bsl-scan.exe
& $rentgenCommand source-list --registry C:\RentgenState\registry.sqlite3 --project $projectId
```

Регистрация создаёт исходный слой; дополнительные слои задаются `layers-set` с
явной ожидаемой ревизией. Конфликт ревизии требует нового решения вызывающего
кода, а не автоматического повторения изменения. Формат файла `--layers-json`:

```json
[{"layer_id":"base","ordinal":0,"kind":"base","root_relative_path":".","source_format":"designer_xml"}]
```

Результат `capture` содержит `snapshot`; передавайте его `snapshot_id` в
`--snapshot`, чтобы несколько запросов читали одну конкретную опубликованную
версию. Путь модуля берётся из `source-list`, слой — из конфигурации проекта.

```powershell
$snapshotId = 'SHA256-ИЗ-ОТВЕТА-ЗАХВАТА'
& $rentgenCommand source-read --registry C:\RentgenState\registry.sqlite3 --project $projectId --snapshot $snapshotId --layer base --path CommonModules/Demo/Ext/Module.bsl --base64
& $rentgenCommand graph-resolve --registry C:\RentgenState\registry.sqlite3 --project $projectId --snapshot $snapshotId --layer base --path CommonModules/Demo/Ext/Module.bsl
& $rentgenCommand impact --registry C:\RentgenState\registry.sqlite3 --project $projectId --snapshot $snapshotId --layer base --path CommonModules/Demo/Ext/Module.bsl --depth 2
```

`source-read --base64` возвращает точные исходные bytes, размер и SHA-256. Для
сохранения используйте `--output NEW_FILE` вместо `--base64`; существующий файл не
заменяется. BOM, CRLF и непрозрачные двоичные данные не нормализуются. Снимок
проверяется перед чтением; повреждённая generation не подменяется живыми файлами.

## Права и метаданные в dev3

Новые проекты создаются со schema4. Команды `membership-list`, `membership-set`,
`membership-revoke` и `membership-receipt` управляют доступом с обязательной
ожидаемой revision и operation ID для изменений. CLI не выбирает actor из JSON.
Для schema2 доступно явное `state-upgrade-access --backup-directory PATH`, которое
проверяет резервную копию перед обновлением. Перезапустите все использующие
проект процессы на совместимой версии до перехода на schema3; старый dev0 не
читает schema3. Точные команды и ограничения: [PROJECT-ACCESS.md](PROJECT-ACCESS.md).

Python API метаданных поставляется в базовом wheel и возвращает
`metadata_scan_v2`: bounded refs ответа и отдельное подтверждение полной
проверки сохранённой generation. Summary/search/object используют одну
ограниченную сессию с удержанием файлов и проверками состава при входе/выходе.
Это не добавляет новых CLI или stdio tools. Контракты: [SNAPSHOT-METADATA.md](SNAPSHOT-METADATA.md)
и [SNAPSHOT-READ-SESSIONS.md](SNAPSHOT-READ-SESSIONS.md).

## Переход существующего проекта на schema4

Установка dev3 не изменяет состояние существующих проектов автоматически.
Для проекта schema3 из dev2 сначала подготовьте существующую папку backup:

```powershell
$workflowOperation = [guid]::NewGuid().ToString()
& $rentgenCommand state-upgrade-workflows --registry C:\RentgenState\registry.sqlite3 --project $projectId --backup-directory C:\RentgenBackups --operation-id $workflowOperation
```

Команда создаёт проверенную SQLite-копию и отдельную квитанцию обновления.
Повтор использует тот же operation ID. Снимки, публикационные квитанции и
членство сохраняются. До явной миграции команды черновиков дают
WORKFLOW_SCHEMA_REQUIRED. Проект schema2 сначала обновляется через
state-upgrade-access до3. Понижение версии состояния до3 не поддерживается;
возврат старого пакета сам по себе не откатывает миграцию.

[История черновиков](DRAFT-HISTORY.md) доступна через CLI. [MCP](DRAFT-MCP.md)
использует ту же историю, а [большие модули](LARGE-DRAFT-MCP.md) редактируются
точными заменами по выбранной ревизии. Сохранение не применяет изменения к 1С.

## Прерванный захват

До длительной работы capture выводит в stderr JSON `recovery`: `operation_id` и
исходный `expected_head`. Сохраните оба значения, включая вложенный `snapshot` и
`source_revision`. Запрашивайте `publication-receipt --operation-id UUID`, чтобы
проверить исход операции. Ошибка/прерывание клиента сами по себе не доказывают откат.

Для точного повторения той же операции сохраните объект `expected_head` в UTF-8
JSON и передайте **оба** `--operation-id` и `--expected-head-json`. Сохранённый ответ
команды `project-head` тоже допустим, если это именно исходное ожидаемое состояние.
Нельзя подставлять новый head после конфликта. Уже завершённая операция возвращает
свой прежний receipt даже при более новом текущем снимке; повторное построение для
этого не требуется. Неопределённый исход требует сверки receipt, а не удаления
generation. Автоматического удаления оставшихся незарегистрированных попыток нет.

## Разработка и проверка поставки

Для редактируемой установки используйте отдельное окружение с тем же зафиксированным
профилем сборки, затем `pip install --no-build-isolation --no-deps -e .`.
`rentgen_graph` является настоящим пакетом; старые `tools/rentgen` пути сохраняют
совместимые aliases для поэтапного перевода существующих consumers. Ядро и новый CLI
их не импортируют. Поддержка editable ограничена явно выбранными тремя пакетами;
Hatchling использует import hook, который некоторые IDE не индексируют.

Проверка настоящих артефактов запускается из продуктового test-окружения:

```powershell
$env:RENTGEN_BUILD_PYTHON = (Resolve-Path .\.venv-build\Scripts\python.exe).Path
$env:RENTGEN_MCP_WHEELHOUSE = (Resolve-Path .\verified-mcp-wheels).Path
$env:RENTGEN_PREVIOUS_CORE_WHEEL = (Resolve-Path .\previous\rentgen_core-0.1.0.dev2-py3-none-any.whl).Path
.\.venv-test\Scripts\python.exe -m pytest -o addopts= --no-cov tests/integration/test_core_distribution.py
```

Она строит sdist и wheel, сравнивает wheel из sdist с прямой сборкой, проверяет
содержимое и лицензию, устанавливает wheel без сети в новое окружение и запускает
CLI вне checkout. Для проверки настоящего BSL добавьте
`RENTGEN_BSL_RUNTIME_DESCRIPTOR`: абсолютный путь UTF-8 JSON с полями `java`
(полный путь `bin/java.exe` указанного JDK) и `jar` (полный путь JAR). Тест
копирует runtime в отдельный профиль и выполняет четыре реальных анализа через
установленные CLI и MCP; эти входные бинарные файлы не берутся из wheel. Без этого
параметра BSL-проверка пропускается и не считается пройденной.
Без явного build interpreter этот отдельный тест пропускается;
такой пропуск не является успешной проверкой поставки.

Для MCP отдельный wheelhouse должен содержать SDK и его Windows CPython 3.11
зависимости из существующего runtime lock. Перед offline-установкой тест сверяет
имя/версию/SHA-256 каждого wheel с доставленным lock, создаёт второе окружение и
отдельный профиль пользователя. Затем установленный `rentgen-mcp` проходит
initialize/list/call, настоящий Go capture, чтение S1 после S2 и receipt replay.
Оба установленных окружения проверяют schema4 и отказ после аудируемого отзыва
прав вторым локальным администратором; базовое также выполняет metadata API v2.
Без `RENTGEN_MCP_WHEELHOUSE` пропускается только эта дополнительная проверка;
базовая установка остаётся без SDK. Сохраните `--basetemp` в отдельном каталоге
evidence, если нужны wheel/sdist, логи и JSON после проверки.

Для schema 1 доступен явный `state-migrate --backup-directory PATH` с проверенной
SQLite-копией перед обновлением; повтор использует operation ID из stderr.
Семантика backup и `migration_attribution=not_proven` описана в
[STATE-MIGRATION.md](STATE-MIGRATION.md). Это не импорт legacy graph/JSON evidence.
CLI не подтверждает работу платформы 1С, обновление конфигурации, непрерывный аудит,
канонические metadata UUID или готовность существующих HTTP/MCP обработчиков.
Граф показывает ограниченный статический анализ, quality — unavailable, временная
атомарность меняющегося источника — not_proven. Лимиты времени, дескрипторов и объёма проверки описаны в runbook сессий;
измерения конкретной конфигурации не заменяются проверкой установки.

Механика сборки: [Hatch build configuration](https://hatch.pypa.io/latest/config/build/).

Приёмка dev3 дополнена обменом общим черновиком между установленными CLI и SDK,
с фильтрами исходников, большими кандидатами и чтением старой версии после S2.
RENTGEN_PREVIOUS_CORE_WHEEL указывает на сохранённый настоящий wheel dev2:
отдельное окружение создаёт им проект schema3 со снимком, обновляет пакет без
сети и выполняет явную миграцию с проверкой backup и сохранения данных.
Без этого входа проверка перехода пропускается и не считается подтверждённой.
Для отдельного прогона поставки без повторения Java используйте
`-k 'not installed_bsl_checks'`; это не подтверждает новую установку Java runtime.


## Исправление CLI в dev4

В dev3 явные `--limit` у draft-list/draft-history и `--status` у draft-list
ошибочно отклонялись как повторные аргументы: parser считал значением вызова
значение по умолчанию. Dev4 учитывает только фактически переданные аргументы;
повторное указание по-прежнему запрещено. Схема состояния остаётся 4, для
перехода с dev3 миграция не нужна. Установите новый wheel/комплект в отдельное
окружение, укажите прежний registry; старые снимки и черновики сохраняются.
Расширение просмотра VSCodium требует dev4 для листания и фильтра архива.


## Обратная связь MCP в dev7

Ошибка схемы `INVALID_ARGUMENT` теперь сообщает путь к полю и ожидаемый формат.
Недостающие/лишние известные поля названы явно; значения аргументов и неизвестные
имена не отражаются в ответе. Это помогает человеку и агенту исправить запрос.
Валидация, ограничения MCP и схема состояния 4 сохранены; миграция с dev6 не нужна.

## Ограничение MCP в dev6

Сервер принимает доверенные параметры `--project` и повторяемый `--allow-tool`.
Они ограничивают обнаружение и исполнение инструментов, включая вложенные ссылки
на другой проект, до доступа к состоянию. Проверки membership сохраняются.
Без параметров остаётся прежний набор из 21 инструмента. См. [контракт MCP](CORE-MCP.md).
Схема 4 не меняется; миграция с dev5 не нужна. Профили редактора нового
генератора требуют dev6, чтобы ограничения исполнялись сервером.

## Текст для агента в dev5

У rentgen_draft_read появился необязательный encoding=utf-8: читаемые порции
кода с прежними ссылками, хешами и лимитами, без повреждения границ Unicode.
Режим base64 по умолчанию совместим с dev4. Состояние schema4 не меняется;
новая миграция не нужна. Подробности в LARGE-DRAFT-MCP.md.
