# Переносимое ядро: первый ограниченный срез

Этот ограниченный срез входит в опубликованный Core dev17. Для Linux x86_64
доступно [экспериментальное дополнение](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev17)
с wheel и Rust executable; MCP-зависимости, Go scanner и редактор в него не входят.
Полный продукт, offline-kit и Companion пока не приняты на Linux/macOS. Windows retained-source, live-apply, process ownership и native
adapters сохраняют прежние границы. Полная перепись и новый LLM runtime не нужны
для описанного ниже state/history среза. Уже реализованный экспериментальный
[Rust ZIP input core](RUST-INPUT-CORE.md) описан отдельно: у него собственные
Linux byte/session contracts и ограничения.

## Что работает на Linux

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

На Linux capture, retained snapshot/graph access, создание/изменение черновиков,
workspace mutation, live apply/undo/recovery/status, native execution, diagnostics
и непроверенные state writes возвращают `CAPABILITY_UNAVAILABLE`. CLI делает это
до identity, registry, payload и source IO. MCP делает это после ограниченной
проверки DTO/scope, до runtime dispatch. Прямая попытка вызвать скрытый инструмент
также отклоняется. Новая команда без явного capability mapping закрыта по умолчанию.

На macOS доступна только матрица capabilities: identity adapter и полный workflow
ещё требуют отдельной реализации и native приёмки. POSIX file descriptor не
объявляется эквивалентом Windows deny-write/deny-delete retained handle.

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
объявлять полный suite зелёным по одному целевому набору. Новая native 1С/редакторная
приёмка, macOS, portable snapshot import/retained reader, native tools, Companion
и полный Linux offline-kit остаются отдельными этапами.
