# Rust input core: экспериментальный Linux import

Первый нативный Rust срез выполняет чтение и принятие готовой ZIP-выгрузки,
проверку структуры архива, ограниченную декомпрессию и SHA-256. Rust удерживает
собственную immutable session. Python сохраняет local identity, membership,
CLI/IPC orchestration и существующий bounded XML analyzer. Go scanner не меняется.
Компонент опубликован в [экспериментальном Linux x86_64 дополнении Core dev17](https://github.com/DmitrL-dev/1cai-public/releases/tag/core-v0.1.0-dev17).
Это не полный cross-platform release и не замена Windows
retained-source/live-apply/native contracts.
Новый [source-facts CLI](SOURCE-FACTS.md) в candidate Core dev18 повторно
использует этот immutable input boundary, но имеет отдельные Go/Rust observers,
ограниченный handwritten XML profile и незавершённую приёмку. Этот новый маршрут
не входит в опубликованное дополнение dev17.

## Полезный результат

`export-analyze` принимает явный ZIP с Designer XML в корне архива и возвращает:

- количество файлов, распознанных metadata roots, типов объектов и BSL-модулей;
- bounded поиск по имени/синониму/type/path объекта;
- observed UUID с явным `unverified`, хеши и размеры источников;
- отдельные `input_ref` для переданных bytes, без `SnapshotRef` и публикации;
- явную ограниченную coverage. Модули получают только inventory, не callgraph,
  качество кода, диагностику или native acceptance.

Пустой, EDT-only или обёрнутый дополнительным directory ZIP без распознанных
Designer roots отклоняется. Корень не угадывается, base и extension не смешиваются.
Нераспознанные metadata roots в смешанной выгрузке отмечают `format_status: partial`.
Файлы исходников, state, project head и shared drafts не изменяются.

## Запуск

Для опубликованного binary нужны GNU/Linux x86_64, glibc 2.34+, `libgcc_s.so.1`,
Linux kernel с `close_range` (>=5.9), memfd sealing, `/proc/self/fd` и local
filesystem. Дополнение содержит wheel, binary, лицензии и инструкцию;
MCP-зависимости, Go scanner и редактор в него не входят. Linux capture и Companion
не приняты. Sidecar — отдельный executable с известным SHA-256; он не ищется в PATH.
CLI требует уже созданных registry/project/local-account profile из
[PORTABLE-CORE.md](PORTABLE-CORE.md).

```sh
python -m rentgen_core export-analyze \
  --registry /absolute/registry.sqlite3 \
  --identity-profile /absolute/private/identity.json \
  --project <project-uuid> \
  --archive /absolute/export.zip \
  --archive-sha256 <sha256-of-export-zip> \
  --input-core /absolute/rentgen-input-core \
  --input-core-sha256 <sha256-of-the-experimental-binary> \
  --query "Товары" --limit 50
```

Designer paths, например `Configuration.xml` или `Catalogs/...`, располагаются
напрямую от корня ZIP, без автоматически добавленной внешней папки. Сам файл
`Configuration.xml` не обязателен: достаточно распознанного metadata object.
Это не проверка полноты выгрузки. CLI не создаёт архив за пользователя.
Параметры `--query` и `--limit` необязательны; limit 1..200. Этот срез доступен через
CLI, не через MCP file-path arguments. На Windows/macOS команда пока возвращает
`CAPABILITY_UNAVAILABLE`, не ослабляя существующую реализацию.

## Контракт bytes и границы доверия

SHA-256 доказывает совпадение принятых bytes с выбранным expected hash. Он **не**
доказывает доверенное происхождение выгрузки, её полноту относительно живой базы,
одновременный filesystem snapshot или отсутствие любой конкурентной записи.
Linux FD не запрещает другому writer менять файл. Проверки before/after stamp и
точного размера обнаруживают наблюдаемые изменения; expected hash привязывает
полностью принятый буфер. После успешного import дальнейшие запросы читают только
собственные immutable buffers Rust, даже если исходный path позже изменён/удалён.

Rust открывает выбранный архив через no-follow ancestor descriptors и leaf FD,
отклоняет symlink, hardlink и special files. Внутренние ZIP paths никогда не
становятся filesystem locators: нет extract, directory creation или path reopen.
Полная проверка предшествует успешному import; partial inventory не выдаётся.
Unicode/path policy дополнительно проверяется прежним Python source_paths boundary.

Принятый профиль ограничен Stored/Deflate. Encrypted, ZIP64, multipart, special
entries, unsafe/colliding paths, overlapping ranges, несогласованные local/central
headers, неверные CRC/размеры и неполные compressed streams отклоняются. Детальные
ограничения ZIP и IPC зафиксированы в [README Rust crate](../../rust/input-core/README.md).

Предельные budgets: 16 MiB исходный архив, 4096 ZIP entries, 4 MiB файл, 32 MiB
распакованные bytes, 64 KiB frame и 32 KiB read chunk. Python дополнительно
ограничивает stderr, суммарный transport, JSON fields и конечный CLI output.
Rust child ограничивает своё address space 128 MiB, import 10 s и session 60 s.
Эти лимиты не являются обещанием bounded kernel IO на неисправном/stalled filesystem.
Неподтверждённое завершение child не считается успешным результатом.

## Владение процессом и authorization

CLI проверяет `project:read` + `analysis:run` до чтения input и запуска sidecar,
затем вокруг IPC и при выдаче результата/ошибки после JSON serialization.
Отзыв прав исключает прежние source diagnostics из ответа.

Проверенный executable копируется в собственный sealed memfd; исполнение получает
именно эти неизменяемые bytes. В parent нет hash-path-then-exec-path окна. Файл
executable должен быть regular, single-link, account/root-owned и без group/other
write permissions. Отсутствует shell/PATH lookup, environment минимален.

Rust до hello устанавливает parent-death SIGKILL и проверяет parent identity race,
закрывает лишние inherited descriptors, отключает core dump и устанавливает
ресурсные deadlines. Он не запускает других процессов. Python владеет одним child,
обрабатывает cancellation/EOF/timeout, проверяет framing до allocation и после close
ACK дочитывает pipes до EOF, подтверждая exit. Это не общий sandbox и не новый
Windows ProcessOwner adapter. Same-account hostile code/root и изменённый trusted
startup configuration находятся вне данной локальной границы.

## Сборка, зависимости и проверка

Crate: `rust/input-core`, `publish = false`. Cargo.lock закреплён; zip default
features выключены, используется Stored/Deflate с pure-Rust flate2 backend.
`DEPENDENCY_PROVENANCE.json` содержит сравнение registry checksums и проверку cached
vendor files, включая ограничения provenance. Это не утверждение, что архивы всех
crates были независимо заново скачаны и распакованы. Не используйте extract API.

```sh
cargo test --locked --manifest-path rust/input-core/Cargo.toml
cargo build --locked --release --manifest-path rust/input-core/Cargo.toml
RENTGEN_INPUT_CORE_TEST_BINARY="$PWD/rust/input-core/target/release/rentgen-input-core" \
  python -m pytest -q tests/unit/test_rust_input_workflow.py
python scripts/verification/benchmark_portable_input.py \
  --binary "$PWD/rust/input-core/target/release/rentgen-input-core" \
  --output-directory /new/synthetic-benchmark-directory --samples 3
```

Команды Python acceptance tests выше требуют полного repository checkout и
test dependencies: каталог `tests/unit` не входит в sdist. Rust crate tests и
benchmark script входят в sdist; тесты crate можно запускать из распакованного
исходного пакета после установки toolchain и locked dependencies.

Cargo создаёт hardlinked build outputs: для CLI нужен отдельный single-link copy
binary (`cp` в новый file), затем SHA-256 этого copy. Тестовая fixture делает такую
копию сама. Предоставленный experimental binary также должен поставляться как
обычный отдельный файл, с checksum, лицензиями и обозначением платформы.

Приёмка включает byte/hash parity с Python zipfile только как тестовым oracle,
реальный CLI, hostile archives, revocation, malformed IPC, отмену, parent-death с
наблюдаемым reap и чтение прежних bytes после path replacement. Измерения latency/RSS
на synthetic corpus не означают ускорение: Python reference не выполняет эквивалентный
confinement/ownership lifecycle. Полный Windows-oriented Linux suite сохраняет
отдельно классифицированные failures; не смешивайте это с зелёным целевым набором.
