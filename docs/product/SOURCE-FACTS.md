# Source facts: экспериментальный Linux CLI

Core **0.1.0.dev18** содержит отдельную команду `source-facts` для ограниченных
наблюдений над готовым ZIP. Это следующий исходный кандидат; приёмка полного
source-fact маршрута ещё не завершена. Текущий source Companion — **0.1.19**. Новая команда
не имеет MCP endpoint или интерфейса Companion. Этот документ не объявляет
новый выпуск и не заменяет ранее принятые пакеты.

Нормативный контракт — [SOURCE-FACTS-PROTOCOL.md](SOURCE-FACTS-PROTOCOL.md), SHA-256
`ae22acd2df04bfedb4070e3709ee1c0cd14cb80c2abb7da3084493977dad94dc`.
Ниже описан его узкий пользовательский маршрут, без расширения грамматики,
гарантий происхождения или области приёмки.

## Какой результат можно получить

Команда принимает явно выбранные caller/candidate BSL entries и точный диапазон
байтов в caller. Она может вернуть только три наблюдения:

1. **Lexical selector:** в указанном диапазоне находится лексическая форма
   `Имя.Метод(...)` внутри допустимого routine body.
2. **Candidate header Export marker:** есть ли `Export` / `Экспорт` в заголовке
   совпавшей по имени процедуры или функции явно выбранного candidate-файла.
3. **Candidate XML Server property:** явно записанное `true` или `false` в
   ограниченном XML, точно сопоставленном с candidate.

Каждый слот либо `observed`, либо `unavailable` с фиксированной причиной.
`false` — наблюдение записанного маркера/свойства, а не диагноз недоступности
метода. Отсутствие подходящего объявления означает `declaration_unavailable`,
а не доказанное отсутствие метода. Успешная операция может не дать ни одного
наблюдения.

`receiver_binding` и `runtime_relation` **всегда `unknown`**. Даже совпадение имён,
общий caller/candidate, локальное затенение, имя свойства платформы или частичная
выгрузка не доказывают, что receiver обозначает этот общий модуль. Принадлежность
и полнота конфигурации остаются `unverified`. Команда не устанавливает причину
ошибки 1С, не выбирает и не выполняет native check и не вызывает модель.

## Что подготовить

- Linux с `close_range` (kernel >= 5.9), memfd sealing, `/proc/self/fd` и подходящей
  локальной файловой системой. Windows/macOS для этой команды закрыты.
- Python >= 3.11 из checkout либо установленного candidate wheel. Extra `mcp`
  для команды не требуется. Wheel не включает три executable.
- Уже созданные registry, project и доверенный local-account profile:
  [bootstrap и границы identity](PORTABLE-CORE.md), [права проекта](PROJECT-ACCESS.md).
  Текущему principal нужны одновременно `project:read` и `analysis:run`.
- Готовый ZIP и SHA-256 именно его сырых байтов. CLI не создаёт выгрузку или ZIP,
  не ищет проекты и не выбирает файлы автоматически.
- Три проверенных Linux executable с собственными ожидаемыми SHA-256:
  `rentgen-input-core`, `bsl-source-facts`, `rentgen-source-facts`.

Архив проходит существующий [Rust ZIP input core](RUST-INPUT-CORE.md), но эта
команда не использует Designer inventory analyzer из `export-analyze`.
Она читает только выбранные BSL entries и точно парный XML; `Configuration.xml`
и остальная metadata не становятся доказательством полноты или принадлежности.

## Сборка трёх executable из выбранных исходников

Команды ниже — инструкция для локальной сборки, не свидетельство завершённой
приёмки. Нужны Go **1.25.5**, Rust **1.92.0** и зависимости из закреплённых
Cargo.lock. Выполняйте из корня checkout или распакованного sdist. Зависимости
не встроены в sdist; для офлайн-сборки нужен заранее подготовленный проверенный
cache/vendor и Cargo configuration, после чего к Cargo добавляют `--offline`.

```sh
set -eu
images="$(mktemp -d /tmp/rentgen-source-images.XXXXXX)"
cargo +1.92.0 build --locked --release \
  --manifest-path rust/input-core/Cargo.toml --bin rentgen-input-core
cargo +1.92.0 build --locked --release \
  --manifest-path rust/diagnostic-core/Cargo.toml --bin rentgen-source-facts
go -C go build -trimpath -o "$images/bsl-source-facts" ./cmd/bsl-source-facts
install -m 0700 rust/input-core/target/release/rentgen-input-core \
  "$images/rentgen-input-core"
install -m 0700 rust/diagnostic-core/target/release/rentgen-source-facts \
  "$images/rentgen-source-facts"
chmod 0700 "$images/bsl-source-facts"
sha256sum "$images/rentgen-input-core" "$images/bsl-source-facts" \
  "$images/rentgen-source-facts"
printf '%s\n' "$images"
```

Остановитесь при ошибке любой команды. Не используйте старый binary вместо
неудачной сборки. При заданном `CARGO_TARGET_DIR` пути в `install` нужно явно
заменить путями этого выбранного каталога. Cargo может создавать hardlinked
outputs: отдельный `install` в новый каталог даёт CLI single-link copy.

Executable должен быть regular file с одной hardlink, владельцем root или
текущим effective UID, executable bit, без group/other write и размером
1..33 554 432 байта. Symlink в пути не допускается. Hash вычисляют по той
копии, которую передают CLI. Hash подтверждает выбранные bytes, не доверие
к произвольной программе: используйте только рассмотренные реализации.

Отдельные описания компонентов: [input-core](../../rust/input-core/README.md),
[diagnostic-core](../../rust/diagnostic-core/README.md),
[лицензии input-core](../../rust/input-core/THIRD_PARTY_NOTICES.md) и
[лицензии diagnostic-core](../../rust/diagnostic-core/THIRD_PARTY_NOTICES.md).
Новый Go observer не является режимом прежнего `bsl-scan`. Rust binary для этой
команды — `rentgen-source-facts`, не синтетический `rentgen-diagnostic-core`.

## Точные аргументы CLI

После замены обозначений `ABS_*`, `HEX64_*`, `PROJECT_UUID`, `CALLER_ZIP_PATH`,
`CANDIDATE_ZIP_PATH`, `START` и `END` своими значениями:

```sh
python -m rentgen_core source-facts \
  --registry ABS_REGISTRY \
  --project PROJECT_UUID \
  --identity-profile ABS_IDENTITY_PROFILE \
  --archive ABS_ZIP --archive-sha256 HEX64_ZIP \
  --input-core ABS_INPUT_CORE --input-core-sha256 HEX64_INPUT_CORE \
  --source-scanner ABS_SOURCE_SCANNER --source-scanner-sha256 HEX64_SOURCE_SCANNER \
  --source-kernel ABS_SOURCE_KERNEL --source-kernel-sha256 HEX64_SOURCE_KERNEL \
  --caller-entry CALLER_ZIP_PATH --candidate-entry CANDIDATE_ZIP_PATH \
  --selector-start START --selector-end END
```

После установки wheel равнозначен `rentgen source-facts`. Статическая справка:
`python -m rentgen_core source-facts --help`.

- Все показанные аргументы обязательны, кроме `--identity-profile`. Без него
  используется существующий default profile из local-account adapter; команда
  не создаёт identity. Явный profile предпочтителен для воспроизводимого запуска.
- Registry, profile, archive и три executable задаются абсолютными host paths
  без компонента `..`. ZIP paths задаются отдельно и не являются host paths.
- Каждый флаг допускается один раз. Abbreviated flags, positional arguments,
  selector text, query, готовые observations и overrides binding не принимаются.
- Каждый SHA-256 — ровно 64 lowercase hex-символа, без префикса и пробелов.
- Caller — существующий inventory path с точным суффиксом `.bsl`. Candidate —
  точно `CommonModules/<name>/Ext/Module.bsl`, где `<name>` — допустимый identifier.
  Парный XML ищется только как `CommonModules/<name>.xml`. Нет case-insensitive
  поиска, снятия внешней папки ZIP или выбора первого совпадения.
- `START`/`END` — десятичные `0` либо число без ведущих нулей, знака и пробелов,
  каждое 0..524288. Это нулевой half-open диапазон **сырых UTF-8 bytes**
  `[start,end)`, включая начальный BOM в отсчёт. Не номера строк, колонок или
  Unicode-символов. Диапазон начинается на receiver identifier и заканчивается
  сразу после method identifier, без скобок и аргументов. Например, для
  `Demo.Run()` выбирают ровно `Demo.Run`. Пустой, обратный, неточный,
  выходящий за буфер или разрезающий UTF-8 scalar диапазон даёт abstention.

Нет параметров изменения budgets, другого XML/BSL profile, AI provider или
автоматического выполнения следующей проверки.

## Почему допустимый исходник может дать unavailable

BSL profile `bsl_lexical_headers_v1` намеренно меньше языка 1С. Весь выбранный
буфер должен пройти admission: неизвестная конструкция в другом routine также
может закрыть наблюдения по этому файлу. Принимаются UTF-8, один начальный BOM,
LF/CRLF, одно-строчные routine headers, комментарии `//`, простые параметры
и ограниченная лексика body. Семантика statements, типов и аргументов не проверяется.

Identifier alphabet — ASCII letters, русские А–Я/а–я, Ё/ё и `_`, затем также
цифры. Сравнение уменьшает регистр только этого алфавита; Ё и Е, латинские и
кириллические похожие буквы различаются. Неподдержанные директивы `#`/`&`,
многострочные strings, date literals, defaults параметров, module-level code,
dynamic/async keywords и повторные routine names приводят к abstention.
Computed receiver и trailing member/index/call chains также не принимаются.
Полная грамматика и порядок причин находятся в §4–5 нормативного контракта.

XML profile называется **`handwritten_common_module_properties_v1`**.
Разрешена только структура `MetaDataObject/CommonModule/Properties/Name,Server`
в namespace `http://v8.1c.ru/8.3/MDClasses`. Префикс namespace может меняться,
URI и expanded names — нет. `Name` должен быть допустимым identifier; `Server`
принимает только `true` или `false` после снятия XML whitespace.

Обычные attributes, включая Designer UUID и version, дополнительные properties,
другая структура, DTD/entities и внешние ресурсы не поддерживаются. Дублированное
свойство, даже с одинаковыми значениями, не выбирается произвольно. Это
**рукописный ограниченный профиль**, не проверка genuine Designer serialization.
Файл Designer, принятый `export-analyze`, может дать здесь `xml_shape_unsupported`.

Receiver spelling, `<name>` в candidate path и XML `Name` должны совпасть прежде,
чем можно раскрыть candidate Export или Server. Это проверка согласованности
выбранных bytes и имён, без receiver binding. Отсутствующий XML закрывает оба
candidate-наблюдения; корректный Name при плохом Server ещё допускает Export.
Отсутствие matching declaration не закрывает независимо наблюдаемый Server.

## Владение, права и граница доверия

Python сохраняет identity, membership, deadlines, отмену, process ownership,
проверку receipts и окончательное раскрытие. Rust input-core принимает ZIP
целиком и удерживает immutable bytes. Python считывает каждый выбранный entry
один раз, проверяет размер/hash и завершает input child до запуска Go.
Go получает только два byte buffers и диапазон, без файловых путей; отдельный
Rust source-fact kernel получает только закрытый типизированный envelope.
Команда не меняет исходники, не вызывает базу 1С, не публикует snapshot
и не записывает project head/drafts; отчёт не сохраняется. ZIP members никогда
не извлекаются на диск.

Каждый executable читается и проверяется перед исполнением собственной sealed
memfd-копии. Нет shell, PATH lookup или окна «hash path, затем exec изменённого
path». Источники не передаются в argv/environment новых helpers. До передачи
bytes host требует точный hello с установленным Linux parent-death SIGKILL.
Go удерживает ownership OS thread до выхода. Parent владеет дочерними процессами
последовательно, а не объявляет завершением одно лишь получение response.

Успех требует полной записи request и EOF stdin, единственного response,
отсутствия trailing stdout, EOF обеих output pipes, exit 0 и подтверждённого
reap всех детей. SIGINT, timeout, отзыв прав или ошибка останавливают раскрытие.
Права проверяются до input/launch/read, после read/parse/evaluation, во время
ожидания и после финальной serialization. Это bounded polling, не мгновенный
отзыв. `CLEANUP_UNCONFIRMED` не означает, что child подтверждённо завершился.

Допущения: доверенные Linux kernel, loader/runtime libraries, разрешённый local
host и startup configuration. Sealed main image не закрепляет все динамические
зависимости. Hostile code того же account, root, изменение project DB и trusted
configuration находятся вне границы. Это не общий sandbox для произвольных
executables и не криптографическая аутентификация происхождения данных.
SHA-256 связывает выбранные bytes; он не доказывает полноту выгрузки или
одновременный filesystem snapshot. Receipts локальны одному invocation и не
являются подписями. Прямой вызов Rust library не получает host workflow assurance.

## Лимиты и обработка результата

Существующие ZIP limits сохранены: 16 MiB archive, 4096 entries, 4 MiB на entry,
32 MiB распакованных bytes; Stored/Deflate без ZIP64, encryption и multipart.
Небезопасные/colliding paths и неполный/несогласованный архив отвергаются целиком.
Для нового маршрута дополнительно действуют:

| Ресурс | Максимум |
| --- | ---: |
| BSL buffers | 2 различных, по 524 288 bytes |
| Все выбранные BSL/XML reads | 8 388 608 bytes |
| XML | 4 194 304 bytes / 50 000 nodes / depth 64 |
| Tokens на BSL buffer | 32 768 |
| Identifier | 128 Unicode scalars / 512 UTF-8 bytes |
| Routines / parameters на routine / delimiter depth | 256 / 128 / 128 |
| Go request / response JSON | 1 500 000 / 65 536 bytes |
| Rust request / response JSON | 65 536 bytes каждый |
| Discarded stderr каждого нового child | 65 536 bytes |
| Итоговый success envelope | 65 536 bytes плюс LF |

Полная операция ограничена 60 s, hello — 5 s, Go exchange — 10 s от запуска,
Rust exchange — 5 s от запуска, с учётом общего deadline. Failure cleanup имеет
отдельный интервал до 2 s. Go memory limit 64 MiB — runtime soft target, не
OS sandbox cap; Rust helpers имеют свои resource limits. Лимиты не обещают
bounded kernel IO при stalled filesystem или performance SLA.

Exit **0** возвращает один JSON `{"result":...,"request_id":...}` с финальным LF.
В `result` находятся input/image hashes, только выбранные relative source refs,
BSL admission, разрешённые spans и `kernel.observations`. Фиксированы
`scope: submitted_source_facts`, `workflow: verified_bytes_to_source_facts_v1`,
XML profile, unverified configuration fields и обе unknown relations. Absolute
host paths, source snippets, XML text и private receipt ledger не раскрываются.
Relative paths сами могут содержать имена: передавайте этот ответ только
авторизованному получателю.

Exit **2** означает неуспех. Обычно это один CoreError JSON с закрытым кодом
`SOURCE_FACTS_*`, сообщением `Submitted source facts could not be completed`,
request ID и пустым `details`. Динамические exception/child stderr не выводятся.
Если сломалась запись stdout, ответ может отсутствовать или оказаться частичным:
при exit 2 клиент обязан отбросить любой частичный success. Все причины и
приоритеты отказов перечислены в §8 [контракта](SOURCE-FACTS-PROTOCOL.md).

## Приёмка и доставка

Сейчас source-fact acceptance **pending**. Development contracts, lifecycle
fault-injection и независимый рукописный ZIP cohort — отдельные gates. Старые
synthetic kernel results не принимают этот новый путь; наличие тестов в дереве
не означает, что они выполнены на данном candidate. Новые acceptance numbers
нужны из фактического запуска с зафиксированными source/build/image hashes.
Genuine Designer exports, native 1С, пользовательская call diagnosis, macOS,
Windows source-facts, AI usefulness и ускорение не квалифицированы.

Sdist включает этот guide, frozen protocol, исходники Go и оба Rust crates,
их Cargo.lock, provenance, лицензии и crate tests. Python `tests/unit` остаются
только в полном checkout. Исходный пакет не является готовым Linux binary kit;
отдельная проверка установки и поставки обязательна для каждого выпуска.
Companion/version admission и прежние Windows/native gates проверяются отдельно.

Смежные инструкции: [платформы](PLATFORM-SUPPORT.md),
[Linux state/history](PORTABLE-CORE.md), [ZIP import](RUST-INPUT-CORE.md),
[сборка Python package](CORE-INSTALLATION.md),
[отдельный синтетический kernel](DIAGNOSTIC-KERNEL.md).
