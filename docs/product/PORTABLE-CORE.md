# Переносимое ядро: первый ограниченный срез

Source и CI/installation dev19 связаны с [Core qualification](../../releases/core/0.1.0.dev19/qualification.json);
публичные файлы и теги — с [квитанцией публикации](evidence/release-dev19-publication-20261015.json).

Этот ограниченный срез входит в опубликованный Core dev19. Для Linux x86_64
доступно [экспериментальное дополнение](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev19)
с wheel и Rust executable; MCP-зависимости, Go scanner и редактор в него не входят.
Полный Linux/macOS-продукт и Companion не приняты. Отдельные development offline CLI/MCP receipts описаны ниже. Windows retained-source, live-apply, process ownership и native
adapters сохраняют прежние границы. Полная перепись и новый LLM runtime не нужны
для описанного ниже state/history среза. Уже реализованный экспериментальный
[Rust ZIP input core](RUST-INPUT-CORE.md) описан отдельно: у него собственные
Linux byte/session contracts и ограничения.

## Что входит в опубликованный dev19 на Linux

`rentgen capabilities` возвращает JSON с `contract_version: 1`, `platform` и
матрицей `os-adapter-support`. Это проверка реализации OS adapter, не выдача прав
и не обещание наличия установленного native runtime. Membership, текущие
permissions, schema и ограничения входных/выходных данных проверяются отдельно.

- Явный bootstrap локальной identity и нового registry/project.
- Чтение project list/head, layers, publication receipt, membership list/receipt.
- Чтение существующих shared drafts: get/list/history/receipt; MCP также умеет
  bounded `rentgen_draft_read`, включая UTF-8. Это чтение сохранённого state,
  не доказательство доступности или проверки прежних snapshot/source files.
- Существующие `metadata-materialize`, `edt-attribute-plan`, `edt-inventory-plan`
  по явно переданным JSON/byte inputs, с прежними bounds и reauthorization.
  Они возвращают план или summary, не применяют изменения к исходникам.
- Настоящий stdio MCP стартует на Linux с локальным profile. `tools/list`
  показывает только инструменты с поддерживаемым OS контрактом в startup scope.
  В unscoped сервере `rentgen_capabilities` отдаёт ту же матрицу поддержки.

В опубликованном dev19 на Linux capture, retained snapshot/graph access,
создание/изменение черновиков, workspace mutation, live apply/undo/recovery/status,
native execution, diagnostics и непроверенные state writes возвращают
`CAPABILITY_UNAVAILABLE`. CLI делает это
до identity, registry, payload и source IO. MCP делает это после ограниченной
проверки DTO/scope, до runtime dispatch. Прямая попытка вызвать скрытый инструмент
также отклоняется. Новая команда без явного capability mapping закрыта по умолчанию.

На macOS доступна только матрица capabilities: identity adapter и полный workflow
ещё требуют отдельной реализации и native приёмки. POSIX file descriptor не
объявляется эквивалентом Windows deny-write/deny-delete retained handle.

## Linux capture и чтение снимков

Ограниченный маршрут проверен на [PR #102, HEAD `366db69`](evidence/development-ci-366db69-20261016.json):
actual Linux scanner/kernel/ACL, publication/history/replay, installed CLI из wheel
и отдельно source SDK MCP. В Linux lanes 3.11/3.12 прошли по 4441 tests / 975 skips,
44 actual Linux cases, включая 2 source SDK cases; installed CLI — 45 вызовов, 42 success и
3 ожидаемых отказа. Windows regression и editor/GUI сохраняют свой scope в записи.

PR слит в main `2e2dd4f` с тем же деревом `32454b3da4a1fb6cbfc373a2b0c225bbb657bcd1`.
Fresh main push CI — отдельная проверка; PR receipt её не заменяет. Этот capture
не входит в опубликованный dev19. Source SDK и installed CLI не квалифицируют
следующий offline installed SDK-комплект; он требует собственной проверенной
`acceptance.json` с точными source/bytes bindings.

Целевой сценарий — GNU/Linux amd64, новый private project и его default base layer:
сохранить исходники и статический граф, перечитать их в свежем процессе, сохранить
следующую версию и прочитать предыдущую. В исходниках связаны:

- [Private state bootstrap](../../rentgen_core/PRIVATE-STATE-BOOTSTRAP.md) и
  [POSIX LiveTree](../../rentgen_core/POSIX-LIVE-TREE.md): private descriptor ownership,
  bounded копирование и повторные проверки источников.
- [Fixed Go scanner owner](../../rentgen_core/LINUX-SCANNER-OWNER.md): exact SHA-256,
  статический CGO-disabled ELF amd64, sealed image, ограниченные pipes и owned process.
- [Graph bundle](../../rentgen_graph/POSIX-GRAPH-BUNDLE.md) и
  [complete generation](../../rentgen_core/POSIX-GENERATION-OWNER.md): проверенные bytes,
  actual SQLite, final manifest last; source/generation owners успешно закрываются
  до короткой publication transaction.
- [Capture backend](../../rentgen_core/LINUX-CAPTURE-BACKEND.md): catalog/head/receipt CAS,
  recovery durable receipt и точный replay без повторного source/scanner IO.
- [Read facade](../../rentgen_core/POSIX-SNAPSHOT-FACADE.md): `source-list`, `source-read`,
  `graph-resolve` и `impact` из catalogued snapshot, с проверкой bytes и прав вокруг
  каждого чтения. Старые снимки читаются независимо от текущего live source.

CLI `capture --scanner <absolute-executable> --scanner-sha256 <trusted-sha256>`
требует заранее доверенные executable bytes. MCP получает те же параметры только
как startup options сервера; request не выбирает executable или его hash.
`--operation-id` и исходный `--expected-head-json` связывают повтор операции с её
квитанцией. При точном replay scanner может отсутствовать. Отмена проверяется вне
write transaction; если короткий commit уже выиграл гонку, исход восстанавливается
по durable receipt, а не объявляется отменённым задним числом.

Capability contract остаётся v1. Новый узкий alias `snapshot.source.read` и
`source.capture` допускают только этот source/graph маршрут на Linux. Старая
широкая группа `snapshot.retained.read` сохраняет Windows-совместимость и остаётся
закрытой на Linux. Snapshot diff и metadata navigation допускаются позже отдельными
узкими группами `snapshot.compare.read` и `snapshot.metadata.read`; создание/редактирование
черновиков, native execution, live writes и macOS этим блоком не допускаются.

Default capture limits: **64 МиБ всех исходников, 16 МиБ на файл, 4096 записей**,
120 секунд на операцию и более короткие фазовые limits. Это ограниченный срез,
не квалификация максимальных 1 ГиБ / 64 МиБ / 100 000 файлов внутренних adapters
или всего B07. Image/descriptor budgets не являются hard process RSS cap.
Private paths и повторные проверки не доказывают filesystem-wide atomicity или
защиту от hostile кода того же OS account. Source-copy staging attempts остаются
orphans; complete generation получает catalog/head/receipt только после успешного
CAS. Неопубликованные попытки сохраняются; автоматическая очистка и repair
permissions отсутствуют.

Локальные POSIX/SQLite controls и cross-compilation на macOS подтверждают только
свой scope. Actual Linux/source SDK, installed CLI и Windows regression отдельно
приняты для указанного PR source `366db69`; следующие source/bytes и fresh main
push требуют своих проверок. Offline installed SDK closure, весь Linux/macOS
продукт, native 1С/EDT и финальный релиз остаются открытыми.

## Кандидат Linux CLI/MCP offline-комплекта

В исходниках подготовлен отдельный профиль `owned-linux-cli-mcp-py311-x86_64-v1`;
это не опубликованное dev19-дополнение и не принятие всего Linux-продукта.
[Exporter и точные команды](../../scripts/release/OWNED-LINUX-KIT.md) связывают
source commit/tree, Core wheel, static Go scanner, прежний Rust helper и лицензии.
[Linux SDK lock](../../requirements/locks/LINUX-MCP-LOCK.md) сохраняет 29 оригинальных
wheels для официального MCP SDK 1.30.0. Interpreter и OS libraries не поставляются.

Target этого комплекта — **CPython 3.11.15 / GNU/Linux x86_64**, glibc ≥ 2.34,
kernel ≥ 5.9, `libgcc_s.so.1`, memfd seals и `/proc/self/fd`. Python 3.12 остаётся
source/CLI CI target, без квалифицированного offline SDK closure. Windows lock
не используется как Linux wheelhouse; optional MCP CLI extras не включены.

Generated `INSTALL.md` устанавливает только локальные hash-locked wheels и Core,
затем выполняет `pip check`. Отдельный `verify_owned_linux_delivery.py` предназначен
для фактической проверки извлечённых финальных bytes: свежие installed CLI и
официальный SDK stdio, default-base capture, source/graph/history, receipt replay
и контролируемая отмена до CAS с cleanup. Поздняя отмена по-прежнему может уступить
commit; отсутствие публикации в контролируемом pre-CAS сценарии не даёт общего rollback.

Actual offline SDK install/acceptance фиксируется отдельной `acceptance.json`;
проверяйте её точные source/bytes bindings по
[контракту комплекта](../../scripts/release/OWNED-LINUX-KIT.md#qualification-still-required).
[PR #103 `c9cb31e`](evidence/development-ci-c9cb31e-20261016.json) и независимо
[fresh main `8e7346e`](evidence/development-ci-8e7346e-20261016.json)
прошли этот ограниченный синтетический actual CLI/SDK-сценарий. Original API
hash/size проверены до guarded extraction; четыре публичных файла комплекта,
все 152 product files и 29 SDK wheels связаны с точными исходниками.
Установленный SDK inventory: 30 distributions / 1082 RECORD payload files,
четыре native extension imports; это bound CI observation, не полная публичная
копия установленного venv. Source SDK cases учитываются отдельно.

Observed target — CPython 3.11.15, glibc 2.39, kernel 6.17 на x86_64.
Проверка не квалифицирует нижние заявленные версии glibc/kernel, OS-wide airgap,
производительность или Python 3.12 offline SDK closure. Новая сборка требует
своих final archive/manifest hashes и actual target execution; её manifest
сохраняет `accepted:false`, `published:false`, `candidate:true` и
`linux_installed_cli_mcp_qualified:false`. Отдельный положительный CI receipt
имеет только свой scope и не изменяет authority этих flags.
Metadata/drafts/live/native, Companion, macOS, AI и полный B07 не приняты.

## Source-контракт SNAP-DIFF-01

[Ограниченное сравнение снимков](SNAPSHOT-DIFF.md) реализовано отдельно от
принятого capture/kit среза. Linux CLI `snapshot-diff` и MCP `rentgen_snapshot_diff`
сравнивают ordered catalog pair с ранним общим POSIX budget:
512 МиБ bounded read allowance, включая grow/probe; 8 ГиБ conservative image
accounting, не hard RSS; 40 000 source entries, 1 200 000 inventory items,
128 МиБ graph row allowance и 20 млн graph VM allowance с консервативными
reservations/precharges; state/catalog SQLite исключены. Далее — 8192 held
descriptors, 32 cursors и исходный
30-секундный deadline. Per-session limits действуют дополнительно.

Страница содержит не более 100 записей и 1 МиБ JSON; полный MCP wire message
ограничен 2 МиБ вместе с request ID, newline, emitted metadata и двумя представлениями
JSON; private authorization scope удаляется до выдачи. Это retained POSIX/graph
accounting, не whole-process/RSS или physical disk IO cap. Оба owner должны успешно закрыться; выдача повторно проверяет pair,
catalog, permissions и исходный deadline. Потеря/расхождение representations
или metadata даёт отказ. Windows CLI сохраняет legacy contract; новый Windows
MCP использует общий deadline/output guard и прежние per-session resources.
Public macOS не допущен. Точные команды, cursor и границы — в контракте.

Новая source-сборка требует отдельных actual Linux pair controls, installed
CLI/официального SDK scenarios и Windows regression receipts. Положительные
`c9` / `8e` этот diff не содержат и не квалифицируют.

## Local ownership, не новый IAM

Windows principal по-прежнему берётся из process token и имеет прежний формат
`windows-sid:...`; Linux profile не заменяет Windows SID.

Linux использует отдельный постоянный **local-account profile**. Случайный UUID
задаёт namespace установки, а effective OS UID проверяется вместе с владельцем
файла. Principal имеет форму `linux-local:<uuid>:uid:<uid>` с authority `local_os`.
Boot ID, namespace inode, имя пользователя, `USER`, `HOME` и machine-id в этот
идентификатор не входят. Поэтому reboot и пересоздание контейнера не меняют
identity, если сохранены profile, его filesystem ownership и числовой UID.

Это локальная метка владения, **не криптографическая аутентификация между
пользователями/хостами и не защита от клонирования**. Граница доверия исключает
hostile code того же OS account, root, изменение project DB и подмену trusted
startup configuration. UUID не является bearer token и не выдаёт permissions
сам по себе. Новая установка создаёт новый namespace. Копирование только project
state не назначает владельца. Копирование самого profile намеренно переносит
метку той же установки; не раздавайте его как часть проектных артефактов.
Автоматического импорта Windows memberships или назначения владельца нет.

Profile должен находиться вне исходников, project state и полученного от других
проектного контента. `--identity-profile` — trusted startup option CLI/MCP, а не
поле protocol request. Без него используется `.local/state/rentgen/local-identity/identity.json`
в home, полученном из OS password database через `pwd.getpwuid`, не из `HOME`.
Обычное чтение не создаёт profile: bootstrap всегда явный.

- Финальный parent directory: текущий UID, режим `0700`, не symlink.
- Profile: regular file текущего UID, режим `0600`, ровно одна hardlink,
  canonical schema-1 JSON не более 1024 байт; UID и UUID проверяются.
- Parent удерживается открытым; файл открывается относительно его descriptor с
  `O_NOFOLLOW`. FIFO/special files и небезопасные permissions отклоняются.
- Bootstrap пишет временный файл, делает fsync и атомарно публикует через Linux
  `renameat2(RENAME_NOREPLACE)`. Нет fallback на небезопасное overwrite. Нужны
  поддержка renameat2 libc/kernel и private local filesystem с directory fsync.
- Конкурирующие bootstrap вызовы не перезаписывают выигравший namespace.
  При потере ответа после publication сначала вызовите `identity`: существующий
  profile читается, а повторный `identity-init` не заменит его. После kill до
  publication может остаться закрытый временный файл; он не используется как
  identity и новый bootstrap может создать свой. Не удаляйте неизвестные файлы
  автоматически. После power loss гарантия хранения зависит от filesystem fsync.

Если изменился UID или profile утерян, доступ закрывается. Нужны сохранённая
правильная локальная identity либо отдельный явный процесс административного
переноса. Core не исправляет ownership/permissions и не редактирует старые
memberships самостоятельно.

## Синтетический запуск из исходников

Пример использует новые тестовые directories. Не подставляйте production state
для bootstrap. Python должен запускаться из checkout или установленного
wheel; MCP требует optional dependency `mcp`.

```sh
python -m rentgen_core capabilities
python -m rentgen_core identity-init --identity-profile ./demo-account/identity.json
python -m rentgen_core identity --identity-profile ./demo-account/identity.json
mkdir demo-source
python -m rentgen_core registry-init --registry ./demo-registry.sqlite3 \
  --identity-profile ./demo-account/identity.json
python -m rentgen_core project-register --registry ./demo-registry.sqlite3 \
  --identity-profile ./demo-account/identity.json \
  --source-root ./demo-source --state-root ./demo-state --name "Portable demo"
python -m rentgen_core project-list --registry ./demo-registry.sqlite3 \
  --identity-profile ./demo-account/identity.json
python -m rentgen_core project-head --registry ./demo-registry.sqlite3 \
  --identity-profile ./demo-account/identity.json --project <returned-project-uuid>
python -m rentgen_core.stdio_mcp --registry ./demo-registry.sqlite3 \
  --identity-profile ./demo-account/identity.json
```

MCP — JSON-RPC over stdio; последнюю команду запускает MCP client. В project-scoped
server глобальный capability tool, как и project-list, не рекламируется: для
матрицы используйте CLI. Полученный пустой проект не имеет snapshot и draft;
bootstrap не запускает capture скрыто.

## Проверка и границы доказательств

`tests/unit/test_portable_local_workflow.py` проверяет настоящие Linux CLI/MCP
subprocesses без подмены identity: bootstrap, state reads, historical drafts,
planner, membership denial/revocation, capability rejection, concurrent identity
creation и прерывание сразу после atomic publication. Исторические draft rows
создаются явно как synthetic schema-valid fixtures: это не принятие Linux capture.
Три существующих planner CLI suite теперь выполняются и на Linux, включая
revocation/error-output проверки. Mocked Windows dispatch tests явно выбирают
Windows capability contract и не выдаются за Linux live-apply приёмку.

Полный старый Windows-oriented unit suite на Linux имеет отдельные известные
platform/runtime failures. Сравнение с неизменённым baseline необходимо: нельзя
объявлять полный suite зелёным по одному целевому набору. Native 1С, macOS, квалификация нового capture/retained-reader блока, native tools,
Linux Companion и полный Linux offline-kit остаются отдельными этапами. Более
поздний Windows editor API main CI не квалифицирует Linux Companion или native 1С.
